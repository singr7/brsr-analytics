from __future__ import annotations

from datetime import UTC, datetime
from pathlib import PurePosixPath
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.app.core.access import CurrentOrg, CurrentUser, ensure_writable
from api.app.core.config import Settings, get_settings
from api.app.db.session import get_db_session
from api.app.db.taxonomy import load_studio_schema
from api.app.models import (
    StudioComment,
    StudioDoc,
    StudioExport,
    StudioFiling,
    StudioOrg,
    StudioProposal,
    StudioTokenUsage,
)
from api.app.schemas.studio import (
    AnswerWrite,
    BulkProposalDecision,
    CommentCreate,
    ExportCreate,
    FilingCreate,
    ProposalDecision,
    StudioResponse,
)
from api.app.services.quotas import enforce_quota
from api.app.services.storage import object_store
from api.app.services.studio import (
    filing_answers,
    generate_exports,
    scoped_filing,
    write_answer,
)
from worker.studio.documents import parse_document
from worker.studio.engine import prior_prefill_candidates, progress, validate_filing
from worker.studio.mapper import (
    Proposal,
    document_gap_report,
    propose_for_section,
)
from worker.studio.schema import schema_stats

router = APIRouter(prefix="/api/studio", tags=["studio"])
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def _plan(context: CurrentOrg) -> None:
    if context.org.plan_tier not in {"studio", "research"}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Studio plan required")


async def _studio_org(session: AsyncSession, context: CurrentOrg) -> StudioOrg:
    _plan(context)
    studio_org = await session.scalar(select(StudioOrg).where(StudioOrg.org_id == context.org.id))
    if studio_org is None:
        studio_org = StudioOrg(org_id=context.org.id, legal_name=context.org.name)
        session.add(studio_org)
        await session.flush()
    return studio_org


@router.get("/schema", response_model=StudioResponse)
async def studio_schema(context: CurrentOrg) -> StudioResponse:
    _plan(context)
    schema = load_studio_schema()
    return StudioResponse(data={**schema, "stats": schema_stats()})


@router.get("/filings", response_model=StudioResponse)
async def list_filings(session: SessionDep, context: CurrentOrg) -> StudioResponse:
    studio_org = await _studio_org(session, context)
    filings = list(
        await session.scalars(
            select(StudioFiling)
            .where(StudioFiling.studio_org_id == studio_org.id)
            .order_by(StudioFiling.fy.desc())
        )
    )
    return StudioResponse(
        data={
            "items": [
                {
                    "id": str(item.id),
                    "fy": item.fy,
                    "status": item.status,
                    "schema_version": item.schema_version,
                    "answers_revision": item.answers_revision,
                }
                for item in filings
            ]
        }
    )


@router.post("/filings", response_model=StudioResponse, status_code=status.HTTP_201_CREATED)
async def create_filing(
    payload: FilingCreate, session: SessionDep, context: CurrentOrg
) -> StudioResponse:
    ensure_writable(context)
    studio_org = await _studio_org(session, context)
    existing = await session.scalar(
        select(StudioFiling).where(
            StudioFiling.studio_org_id == studio_org.id, StudioFiling.fy == payload.fy
        )
    )
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Filing already exists for this year")
    filing = StudioFiling(
        studio_org_id=studio_org.id,
        fy=payload.fy,
        schema_version=str(load_studio_schema()["schema_version"]),
    )
    session.add(filing)
    await session.commit()
    return StudioResponse(data={"id": str(filing.id), "fy": filing.fy})


@router.get("/filings/{filing_id}", response_model=StudioResponse)
async def get_filing(filing_id: UUID, session: SessionDep, context: CurrentOrg) -> StudioResponse:
    filing = await scoped_filing(session, filing_id, context.org.id)
    answers, meta = await filing_answers(session, filing.id)
    proposals = list(
        await session.scalars(
            select(StudioProposal).where(StudioProposal.studio_filing_id == filing.id)
        )
    )
    findings = validate_filing(answers, answer_meta=meta)
    return StudioResponse(
        data={
            "id": str(filing.id),
            "fy": filing.fy,
            "status": filing.status,
            "schema_version": filing.schema_version,
            "answers": answers,
            "answer_meta": meta,
            "progress": progress(answers, meta),
            "findings": [item.as_dict() for item in findings],
            "proposals": [_proposal(item) for item in proposals],
        }
    )


@router.put("/filings/{filing_id}/answers/{field_key:path}", response_model=StudioResponse)
async def put_answer(
    filing_id: UUID,
    field_key: str,
    payload: AnswerWrite,
    session: SessionDep,
    context: CurrentOrg,
    user: CurrentUser,
) -> StudioResponse:
    ensure_writable(context)
    filing = await scoped_filing(session, filing_id, context.org.id)
    answer = await write_answer(session, filing, user, field_key, payload.value, payload.unit)
    await session.commit()
    return StudioResponse(data={"id": str(answer.id), "field_key": field_key, "saved": True})


@router.post("/filings/{filing_id}/validate", response_model=StudioResponse)
async def run_validation(
    filing_id: UUID, session: SessionDep, context: CurrentOrg
) -> StudioResponse:
    filing = await scoped_filing(session, filing_id, context.org.id)
    answers, meta = await filing_answers(session, filing.id)
    findings = validate_filing(answers, answer_meta=meta)
    return StudioResponse(data={"findings": [item.as_dict() for item in findings]})


@router.post("/filings/{filing_id}/comments", response_model=StudioResponse)
async def add_comment(
    filing_id: UUID,
    payload: CommentCreate,
    session: SessionDep,
    context: CurrentOrg,
    user: CurrentUser,
) -> StudioResponse:
    ensure_writable(context)
    await scoped_filing(session, filing_id, context.org.id)
    comment = StudioComment(
        studio_filing_id=filing_id, field_key=payload.field_key, user_id=user.id, body=payload.body
    )
    session.add(comment)
    await session.commit()
    return StudioResponse(data={"id": str(comment.id)})


@router.get("/filings/{filing_id}/prior-candidates", response_model=StudioResponse)
async def prior_candidates(
    filing_id: UUID, session: SessionDep, context: CurrentOrg
) -> StudioResponse:
    filing = await scoped_filing(session, filing_id, context.org.id)
    current, _ = await filing_answers(session, filing.id)
    previous = await session.scalar(
        select(StudioFiling)
        .where(StudioFiling.studio_org_id == filing.studio_org_id, StudioFiling.fy < filing.fy)
        .order_by(StudioFiling.fy.desc())
    )
    prior = (await filing_answers(session, previous.id))[0] if previous else {}
    return StudioResponse(data={"items": prior_prefill_candidates(current, prior)})


@router.post("/filings/{filing_id}/documents", response_model=StudioResponse)
async def upload_document(
    filing_id: UUID,
    request: Request,
    session: SessionDep,
    context: CurrentOrg,
    settings: SettingsDep,
    filename: Annotated[str, Query(min_length=1, max_length=255)],
) -> StudioResponse:
    ensure_writable(context)
    filing = await scoped_filing(session, filing_id, context.org.id)
    studio_org = await session.get(StudioOrg, filing.studio_org_id)
    assert studio_org is not None
    content = await request.body()
    content_type = request.headers.get("content-type", "application/octet-stream")
    parsed = parse_document(filename, content_type, content, settings.studio_document_max_bytes)
    store = object_store(settings)
    key = str(
        PurePosixPath(
            "studio-docs", str(studio_org.id), f"{datetime.now(UTC).timestamp()}-{filename}"
        )
    )
    uri = store.put(key, content, content_type)
    document = StudioDoc(
        studio_org_id=studio_org.id,
        kind=parsed.kind,
        s3_uri=uri,
        parsed_json={"pages": parsed.pages},
        filename=filename,
        content_type=content_type,
        size_bytes=len(content),
    )
    session.add(document)
    await session.commit()
    return StudioResponse(
        data={"id": str(document.id), "kind": document.kind, "pages": len(parsed.pages)}
    )


@router.post("/filings/{filing_id}/map/{section}", response_model=StudioResponse)
async def map_section(
    filing_id: UUID,
    section: str,
    session: SessionDep,
    context: CurrentOrg,
    settings: SettingsDep,
) -> StudioResponse:
    ensure_writable(context)
    filing = await scoped_filing(session, filing_id, context.org.id)
    month_start = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    used = await session.scalar(
        select(
            func.coalesce(
                func.sum(StudioTokenUsage.input_tokens + StudioTokenUsage.output_tokens), 0
            )
        ).where(
            StudioTokenUsage.studio_org_id == filing.studio_org_id,
            StudioTokenUsage.created_at >= month_start,
        )
    )
    documents = list(
        await session.scalars(
            select(StudioDoc).where(StudioDoc.studio_org_id == filing.studio_org_id)
        )
    )
    estimated = sum(document.size_bytes for document in documents) // 4
    quota = enforce_quota(
        context.org.plan_tier,
        "studio_tokens_per_month",
        int(used or 0),
        estimated,
    )
    answers, meta = await filing_answers(session, filing.id)
    source_docs = [
        {
            "id": str(document.id),
            "studio_org_id": str(document.studio_org_id),
            "pages": (document.parsed_json or {}).get("pages", []),
        }
        for document in documents
    ]
    proposals = propose_for_section(
        section,
        source_docs,
        studio_org_id=str(filing.studio_org_id),
        existing_user_fields={key for key, item in meta.items() if item["author"] == "user"},
    )
    rows = []
    for item in proposals:
        row = StudioProposal(
            studio_filing_id=filing.id,
            field_key=item.field_key,
            value_raw=item.proposed_value,
            unit=item.unit,
            evidence_doc_id=UUID(item.doc_id),
            evidence_page=item.page,
            evidence_quote=item.quote,
            confidence=item.confidence,
        )
        session.add(row)
        rows.append(row)
    session.add(
        StudioTokenUsage(
            studio_org_id=filing.studio_org_id,
            prompt_key="studio_map_section@v1",
            input_tokens=estimated,
            output_tokens=len(proposals) * 80,
        )
    )
    await session.commit()
    return StudioResponse(
        data={
            "items": [_proposal(item) for item in rows],
            "quota": {
                "used": quota.used,
                "limit": quota.limit,
                "remaining": quota.remaining,
                "warning": quota.warning,
            },
        }
    )


@router.patch("/filings/{filing_id}/proposals/{proposal_id}", response_model=StudioResponse)
async def decide_proposal(
    filing_id: UUID,
    proposal_id: UUID,
    payload: ProposalDecision,
    session: SessionDep,
    context: CurrentOrg,
    user: CurrentUser,
) -> StudioResponse:
    ensure_writable(context)
    filing = await scoped_filing(session, filing_id, context.org.id)
    proposal = await session.scalar(
        select(StudioProposal).where(
            StudioProposal.id == proposal_id, StudioProposal.studio_filing_id == filing.id
        )
    )
    if proposal is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Proposal not found")
    proposal.review_status = payload.decision
    proposal.decision_by_user_id = user.id
    if payload.decision != "rejected":
        value = payload.value if payload.decision == "edited" else proposal.value_raw
        answer = await write_answer(
            session, filing, user, proposal.field_key, value or "", proposal.unit
        )
        answer.author = "ai" if payload.decision == "accepted" else "user"
        answer.review_status = payload.decision
        answer.evidence_doc_id = proposal.evidence_doc_id
        answer.evidence_page = proposal.evidence_page
        answer.evidence_quote = proposal.evidence_quote
    await session.commit()
    return StudioResponse(data={"id": str(proposal.id), "review_status": proposal.review_status})


@router.post("/filings/{filing_id}/bulk-proposals/accept", response_model=StudioResponse)
async def bulk_accept(
    filing_id: UUID,
    payload: BulkProposalDecision,
    session: SessionDep,
    context: CurrentOrg,
    settings: SettingsDep,
    user: CurrentUser,
) -> StudioResponse:
    ensure_writable(context)
    accepted = []
    for proposal_id in payload.proposal_ids:
        proposal = await session.scalar(
            select(StudioProposal).where(
                StudioProposal.id == proposal_id,
                StudioProposal.studio_filing_id == filing_id,
                StudioProposal.confidence >= settings.studio_bulk_accept_confidence,
                StudioProposal.review_status == "unreviewed",
            )
        )
        if proposal:
            await decide_proposal(
                filing_id,
                proposal.id,
                ProposalDecision(decision="accepted"),
                session,
                context,
                user,
            )
            accepted.append(str(proposal.id))
    return StudioResponse(data={"accepted": accepted})


@router.get("/filings/{filing_id}/document-gaps", response_model=StudioResponse)
async def document_gaps(
    filing_id: UUID, session: SessionDep, context: CurrentOrg
) -> StudioResponse:
    filing = await scoped_filing(session, filing_id, context.org.id)
    proposals = list(
        await session.scalars(
            select(StudioProposal).where(StudioProposal.studio_filing_id == filing.id)
        )
    )
    _, meta = await filing_answers(session, filing.id)
    mapped = [
        Proposal(
            item.field_key,
            item.value_raw,
            item.unit,
            str(item.evidence_doc_id),
            item.evidence_page,
            item.evidence_quote,
            float(item.confidence),
        )
        for item in proposals
    ]
    report = document_gap_report(
        mapped, {key for key, item in meta.items() if item.get("evidence_doc_id")}
    )
    return StudioResponse(data=report)


@router.post("/filings/{filing_id}/exports", response_model=StudioResponse)
async def create_exports(
    filing_id: UUID,
    payload: ExportCreate,
    session: SessionDep,
    context: CurrentOrg,
    settings: SettingsDep,
) -> StudioResponse:
    ensure_writable(context)
    filing = await scoped_filing(session, filing_id, context.org.id)
    studio_org = await session.get(StudioOrg, filing.studio_org_id)
    assert studio_org is not None
    exports = await generate_exports(
        session,
        filing,
        payload.kinds,
        object_store(settings),
        studio_org.legal_name,
        studio_org.cin or "UNKNOWN",
    )
    await session.commit()
    return StudioResponse(data={"items": [_export(item) for item in exports]})


@router.get("/filings/{filing_id}/exports", response_model=StudioResponse)
async def export_history(
    filing_id: UUID, session: SessionDep, context: CurrentOrg
) -> StudioResponse:
    filing = await scoped_filing(session, filing_id, context.org.id)
    rows = list(
        await session.scalars(
            select(StudioExport)
            .where(StudioExport.studio_filing_id == filing.id)
            .order_by(StudioExport.created_at.desc())
        )
    )
    return StudioResponse(data={"items": [_export(item) for item in rows]})


@router.get("/filings/{filing_id}/exports/{export_id}/download")
async def download_export(
    filing_id: UUID,
    export_id: UUID,
    session: SessionDep,
    context: CurrentOrg,
    settings: SettingsDep,
) -> Response:
    filing = await scoped_filing(session, filing_id, context.org.id)
    artifact = await session.scalar(
        select(StudioExport).where(
            StudioExport.id == export_id, StudioExport.studio_filing_id == filing.id
        )
    )
    if artifact is None or artifact.status != "ready" or not artifact.artifact_uri:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Export artifact is not available")
    content_type = "application/pdf" if "pdf" in artifact.kind else "application/octet-stream"
    return Response(object_store(settings).get(artifact.artifact_uri), media_type=content_type)


def _proposal(item: StudioProposal) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "field_key": item.field_key,
        "value": item.value_raw,
        "unit": item.unit,
        "confidence": float(item.confidence),
        "review_status": item.review_status,
        "evidence": {
            "doc_id": str(item.evidence_doc_id),
            "page": item.evidence_page,
            "quote": item.evidence_quote,
        },
    }


def _export(item: StudioExport) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "kind": item.kind,
        "version": item.version,
        "status": item.status,
        "stale": item.stale,
        "findings": item.findings_json,
    }
