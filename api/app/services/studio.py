from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import PurePosixPath
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.app.models import (
    StudioAnswer,
    StudioEditorLock,
    StudioExport,
    StudioFiling,
    StudioOrg,
    User,
)
from api.app.services.storage import ObjectStore
from worker.exportgen.documents import gap_report_data, render_docx, render_gap_pdf, render_pdf
from worker.exportgen.xbrl import arelle_validate, export_gate, generate_instance
from worker.studio.engine import field_catalog, validate_value


async def scoped_filing(session: AsyncSession, filing_id: UUID, org_id: UUID) -> StudioFiling:
    filing = await session.scalar(
        select(StudioFiling)
        .join(StudioOrg, StudioOrg.id == StudioFiling.studio_org_id)
        .where(StudioFiling.id == filing_id, StudioOrg.org_id == org_id)
    )
    if filing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Studio filing not found")
    return filing


async def acquire_lock(session: AsyncSession, filing: StudioFiling, user: User) -> StudioEditorLock:
    now = datetime.now(UTC)
    lock = await session.scalar(
        select(StudioEditorLock)
        .where(StudioEditorLock.studio_filing_id == filing.id)
        .with_for_update()
    )
    if lock and lock.user_id != user.id and lock.expires_at > now:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"code": "editor_locked", "expires_at": lock.expires_at.isoformat()},
        )
    if lock:
        lock.user_id = user.id
        lock.expires_at = now + timedelta(minutes=5)
    else:
        lock = StudioEditorLock(
            studio_filing_id=filing.id,
            user_id=user.id,
            expires_at=now + timedelta(minutes=5),
        )
        session.add(lock)
    return lock


async def filing_answers(
    session: AsyncSession, filing_id: UUID
) -> tuple[dict[str, str], dict[str, dict[str, Any]]]:
    rows = list(
        await session.scalars(
            select(StudioAnswer).where(StudioAnswer.studio_filing_id == filing_id)
        )
    )
    return (
        {row.field_key: row.value_raw for row in rows},
        {
            row.field_key: {
                "author": row.author,
                "review_status": row.review_status,
                "unit": row.unit,
                "evidence_doc_id": str(row.evidence_doc_id) if row.evidence_doc_id else None,
                "evidence_page": row.evidence_page,
                "evidence_quote": row.evidence_quote,
            }
            for row in rows
        },
    )


async def write_answer(
    session: AsyncSession,
    filing: StudioFiling,
    user: User,
    field_key: str,
    value: str,
    unit: str | None,
) -> StudioAnswer:
    catalog = field_catalog()
    if field_key not in catalog:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown schema field")
    try:
        normalized = validate_value(catalog[field_key], value, unit)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    await acquire_lock(session, filing, user)
    answer = await session.scalar(
        select(StudioAnswer).where(
            StudioAnswer.studio_filing_id == filing.id, StudioAnswer.field_key == field_key
        )
    )
    if answer:
        answer.value_raw = normalized
        answer.unit = unit
        answer.author = "user"
        answer.review_status = "accepted"
    else:
        answer = StudioAnswer(
            studio_filing_id=filing.id,
            field_key=field_key,
            value_raw=normalized,
            unit=unit,
            author="user",
            review_status="accepted",
        )
        session.add(answer)
    filing.answers_revision += 1
    await session.execute(
        update(StudioExport).where(StudioExport.studio_filing_id == filing.id).values(stale=True)
    )
    return answer


async def generate_exports(
    session: AsyncSession,
    filing: StudioFiling,
    kinds: Sequence[str],
    store: ObjectStore,
    legal_name: str,
    cin: str,
) -> list[StudioExport]:
    answers, meta = await filing_answers(session, filing.id)
    instance = generate_instance(answers, entity_identifier=cin, fy=filing.fy)
    arelle_findings = arelle_validate(instance)
    gate = export_gate(answers, meta, arelle_findings)
    latest = await session.scalar(
        select(func.max(StudioExport.version)).where(StudioExport.studio_filing_id == filing.id)
    )
    version = int(latest or 0) + 1
    trail = [{"field_key": key, **value} for key, value in meta.items()]
    gap_data = gap_report_data(answers, gate.findings, meta)
    payloads = {
        "xbrl": (instance, "application/xml", "xbrl"),
        "docx": (
            render_docx(
                answers, title=f"{legal_name} BRSR FY{filing.fy}", status=filing.status, trail=trail
            ),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "docx",
        ),
        "pdf": (
            render_pdf(
                answers, title=f"{legal_name} BRSR FY{filing.fy}", status=filing.status, trail=trail
            ),
            "application/pdf",
            "pdf",
        ),
        "gap_pdf": (render_gap_pdf(gap_data), "application/pdf", "gap.pdf"),
    }
    exports = []
    for kind in kinds:
        blocked = not gate.allowed and kind in {"xbrl", "docx", "pdf"}
        artifact_uri = None
        if not blocked:
            content, content_type, extension = payloads[kind]
            key = str(PurePosixPath("studio", str(filing.id), f"v{version}", f"brsr.{extension}"))
            artifact_uri = store.put(key, content, content_type)
        export = StudioExport(
            studio_filing_id=filing.id,
            kind=kind,
            version=version,
            answers_revision=filing.answers_revision,
            status="blocked" if blocked else "ready",
            artifact_uri=artifact_uri,
            findings_json=[item.as_dict() for item in gate.findings],
        )
        session.add(export)
        exports.append(export)
    return exports
