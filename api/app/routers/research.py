from __future__ import annotations

import csv
import hashlib
import hmac
import io
import secrets
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.app.core.access import CurrentOrg, CurrentUser
from api.app.db.session import get_db_session
from api.app.models import ApiKey, Company, Score
from api.app.schemas.billing import ApiKeyCreate, ApiKeyCreated, ApiKeySummary
from api.app.schemas.semantic import SemanticQuery, SemanticResponse
from api.app.services.plans import licence_state
from api.app.services.quotas import consume_redis_quota
from api.app.services.semantic import SemanticError, execute_query, load_catalog
from api.app.services.track import persist_events

router = APIRouter(tags=["research"])
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
PUBLIC_API_MEASURES = frozenset({"completeness", "substance", "assurance_readiness"})
LICENCE_HEADER = (
    "BRSR Lens Research dataset; aggregate public-tier materialisations only; "
    "redistribution and re-identification prohibited; "
    "full-corpus licences require manual fulfilment"
)


def _hash_key(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


async def research_owner(context: CurrentOrg) -> None:
    if context.membership.role != "owner" or context.org.plan_tier != "research":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Research owner access required")
    if (
        licence_state(context.org.licence_expires_at, context.org.licence_grace_until)
        == "read_only"
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail={"code": "licence_read_only"})


async def authenticate_api_key(
    session: SessionDep,
    request: Request,
    x_api_key: Annotated[str | None, Header()] = None,
) -> ApiKey:
    if not x_api_key or not x_api_key.startswith("brsrl_"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "X-API-Key is required")
    prefix = x_api_key[:15]
    candidates = (
        await session.scalars(
            select(ApiKey).where(ApiKey.key_prefix == prefix, ApiKey.revoked_at.is_(None))
        )
    ).all()
    key_hash = _hash_key(x_api_key)
    key = next((item for item in candidates if hmac.compare_digest(item.key_hash, key_hash)), None)
    if key is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid API key")
    from api.app.models import Org

    org = await session.get(Org, key.org_id)
    if org is None or org.plan_tier != "research":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Research licence required")
    if licence_state(org.licence_expires_at, org.licence_grace_until) == "read_only":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail={"code": "licence_read_only"})
    await consume_redis_quota(
        request.app.state.redis,
        tier="research",
        identity=str(key.id),
        name="api_queries_per_minute",
    )
    key.last_used_at = datetime.now(UTC)
    return key


ApiKeyDep = Annotated[ApiKey, Depends(authenticate_api_key)]


def require_scope(key: ApiKey, scope: str) -> None:
    if scope not in key.scopes_json:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail={"code": "scope_required", "scope": scope},
        )


@router.post("/api/research/keys", response_model=ApiKeyCreated, status_code=201)
async def issue_key(
    payload: ApiKeyCreate,
    context: CurrentOrg,
    user: CurrentUser,
    session: SessionDep,
) -> ApiKeyCreated:
    await research_owner(context)
    secret = "brsrl_" + secrets.token_urlsafe(32)
    row = ApiKey(
        org_id=context.org.id,
        name=payload.name,
        key_prefix=secret[:15],
        key_hash=_hash_key(secret),
        scopes_json=list(dict.fromkeys(payload.scopes)),
    )
    session.add(row)
    await persist_events(
        session,
        [
            {
                "name": "api_key_issued",
                "session_id": user.id,
                "properties": {"org_id": str(context.org.id), "scopes": row.scopes_json},
            }
        ],
        anon_id=None,
        user_id=user.id,
    )
    await session.commit()
    return ApiKeyCreated(
        id=row.id, name=row.name, key_prefix=row.key_prefix, scopes=row.scopes_json, secret=secret
    )


@router.get("/api/research/keys", response_model=list[ApiKeySummary])
async def list_keys(context: CurrentOrg, session: SessionDep) -> list[ApiKeySummary]:
    await research_owner(context)
    rows = (
        await session.scalars(
            select(ApiKey).where(ApiKey.org_id == context.org.id).order_by(ApiKey.created_at.desc())
        )
    ).all()
    return [
        ApiKeySummary(
            id=row.id,
            name=row.name,
            key_prefix=row.key_prefix,
            scopes=row.scopes_json,
            created_at=row.created_at,
            last_used_at=row.last_used_at,
            revoked_at=row.revoked_at,
        )
        for row in rows
    ]


@router.delete("/api/research/keys/{key_id}", status_code=204)
async def revoke_key(key_id: UUID, context: CurrentOrg, session: SessionDep) -> Response:
    await research_owner(context)
    row = await session.scalar(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.org_id == context.org.id)
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "API key not found")
    row.revoked_at = datetime.now(UTC)
    await session.commit()
    return Response(status_code=204)


@router.post("/api/v1/query", response_model=SemanticResponse, tags=["Research API"])
async def public_api_query(
    payload: SemanticQuery, key: ApiKeyDep, session: SessionDep
) -> SemanticResponse:
    require_scope(key, "query:read")
    if not set(payload.measures) <= PUBLIC_API_MEASURES:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "public_measure_subset", "allowed": sorted(PUBLIC_API_MEASURES)},
        )
    catalog = load_catalog()
    try:
        data, lineage, policy = await execute_query(session, payload, "research", catalog)
    except SemanticError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    await session.commit()
    return SemanticResponse(
        data=data, lineage_refs=lineage, applied_policy=policy, catalog_version=catalog.version
    )


def dataset_csv(rows: list[tuple[object, ...]]) -> bytes:
    output = io.StringIO()
    output.write(f"# licence: {LICENCE_HEADER}\n")
    output.write("# methodology: /methodology; licence_terms: /licence\n")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(["sector", "financial_year", "measure", "company_count", "average_value"])
    writer.writerows(rows)
    return output.getvalue().encode()


def dataset_parquet(rows: list[tuple[object, ...]]) -> bytes:
    import pyarrow as pa  # type: ignore[import-untyped]
    import pyarrow.parquet as pq  # type: ignore[import-untyped]

    names = ["sector", "financial_year", "measure", "company_count", "average_value"]
    columns = list(zip(*rows, strict=True)) if rows else [(), (), (), (), ()]
    table = pa.table({name: list(values) for name, values in zip(names, columns, strict=True)})
    metadata = {
        **(table.schema.metadata or {}),
        b"brsrlens.licence": LICENCE_HEADER.encode(),
        b"brsrlens.methodology": b"/methodology",
        b"brsrlens.licence_terms": b"/licence",
    }
    output = io.BytesIO()
    pq.write_table(table.replace_schema_metadata(metadata), output, compression="snappy")
    return output.getvalue()


@router.get("/api/export/dataset")
async def export_dataset(
    request: Request,
    key: ApiKeyDep,
    session: SessionDep,
    format: str = "csv",
) -> Response:
    require_scope(key, "dataset:read")
    await consume_redis_quota(
        request.app.state.redis,
        tier="research",
        identity=str(key.id),
        name="exports_per_month",
    )
    if format not in {"csv", "parquet"}:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Supported formats: csv, parquet")
    rows = (
        await session.execute(
            select(
                Company.sector,
                Score.fy,
                Score.score_key,
                func.count(Score.id),
                func.round(func.avg(Score.value), 4),
            )
            .join(Company, Company.id == Score.company_id)
            .where(Score.score_key.in_(PUBLIC_API_MEASURES))
            .group_by(Company.sector, Score.fy, Score.score_key)
            .having(func.count(Score.id) >= load_catalog().minimum_cohort_size)
            .order_by(Company.sector, Score.fy, Score.score_key)
        )
    ).all()
    await session.commit()
    values = [tuple(row) for row in rows]
    content = dataset_csv(values) if format == "csv" else dataset_parquet(values)
    media_type = "text/csv" if format == "csv" else "application/vnd.apache.parquet"
    extension = "csv" if format == "csv" else "parquet"
    return Response(
        content,
        media_type=media_type,
        headers={
            "Content-Disposition": (f"attachment; filename=brsrlens-public-aggregates.{extension}"),
            "X-Licence-Note": "Full-corpus licences require manual fulfilment",
        },
    )
