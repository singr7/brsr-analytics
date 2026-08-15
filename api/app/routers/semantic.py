import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.app.core.access import optional_user
from api.app.db.session import get_db_session
from api.app.models import Membership, Org, User
from api.app.schemas.semantic import SemanticQuery, SemanticResponse
from api.app.services.quotas import consume_redis_quota
from api.app.services.semantic import (
    SemanticError,
    execute_query,
    load_catalog,
    query_cache_key,
)

router = APIRouter(tags=["semantic"])
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


async def resolve_tier(session: AsyncSession, user: User | None, org_id: UUID | None) -> str:
    if org_id is not None and user is not None:
        org = await session.scalar(
            select(Org)
            .join(Membership, Membership.org_id == Org.id)
            .where(Org.id == org_id, Membership.user_id == user.id)
        )
        if org is not None:
            return org.plan_tier
    return user.plan_tier if user is not None else "explore"


@router.get("/api/catalog")
async def semantic_catalog() -> dict[str, object]:
    catalog = load_catalog()
    return {
        "version": catalog.version,
        "minimum_cohort_size": catalog.minimum_cohort_size,
        "measures": catalog.measures,
        "dimensions": catalog.dimensions,
        "filters": catalog.filters,
        "shapes": catalog.shapes,
    }


@router.post("/api/query", response_model=SemanticResponse)
@router.post("/query", response_model=SemanticResponse, include_in_schema=False)
async def semantic_query(
    payload: SemanticQuery,
    request: Request,
    session: SessionDep,
    user: Annotated[User | None, Depends(optional_user)],
    x_org_id: Annotated[UUID | None, Header()] = None,
) -> SemanticResponse:
    catalog = load_catalog()
    tier = await resolve_tier(session, user, x_org_id)
    key = query_cache_key(payload, tier)
    cached = await request.app.state.redis.get(key)
    if cached:
        response = SemanticResponse.model_validate_json(cached)
        response.cache_hit = True
        return response
    try:
        data, lineage, policy = await execute_query(session, payload, tier, catalog)
    except SemanticError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    response = SemanticResponse(
        data=data,
        lineage_refs=lineage,
        applied_policy=policy,
        catalog_version=catalog.version,
    )
    await request.app.state.redis.setex(
        key, 300, json.dumps(jsonable_encoder(response.model_dump()))
    )
    return response


async def invalidate_semantic_cache(redis_client: object) -> int:
    """Delete materialisation-dependent entries without using Redis KEYS."""
    deleted = 0
    cursor = 0
    while True:
        cursor, keys = await redis_client.scan(cursor, match="semantic:v*:*", count=250)  # type: ignore[attr-defined]
        if keys:
            deleted += int(await redis_client.delete(*keys))  # type: ignore[attr-defined]
        if cursor == 0:
            return deleted


@router.post("/api/exports/peer-board")
async def peer_board_pdf(
    payload: SemanticQuery,
    request: Request,
    session: SessionDep,
    user: Annotated[User | None, Depends(optional_user)],
    x_org_id: Annotated[UUID | None, Header()] = None,
) -> Response:
    tier = await resolve_tier(session, user, x_org_id)
    if tier not in {"pro", "studio", "research"}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Pro plan required for board PDF export")
    identity = str(user.id) if user else "anonymous"
    quota = await consume_redis_quota(
        request.app.state.redis,
        tier=tier,
        identity=identity,
        name="exports_per_month",
    )
    catalog = load_catalog()
    data, _, policy = await execute_query(session, payload, tier, catalog)
    import fitz  # type: ignore[import-untyped]

    document = fitz.open()
    page = document.new_page(width=595, height=842)
    page.draw_rect(fitz.Rect(0, 0, 595, 112), color=(0.09, 0.31, 0.24), fill=(0.09, 0.31, 0.24))
    page.insert_text((48, 55), "BRSR LENS", fontsize=9, color=(0.95, 0.74, 0.43))
    page.insert_text((48, 83), "Peer benchmark brief", fontsize=21, color=(1, 1, 1))
    page.insert_text(
        (48, 103),
        f"Catalog {catalog.version}  ·  Governed materialisations",
        fontsize=8,
        color=(0.85, 0.9, 0.87),
    )
    y = 145
    for row in data[:24]:
        label = str(row.get("company") or row.get("sector") or row.get("cohort") or "Cohort")
        page.insert_text((48, y), label[:42], fontsize=10, color=(0.1, 0.16, 0.13))
        page.insert_text((470, y), str(row.get("value", "suppressed")), fontsize=10)
        page.draw_line((48, y + 7), (540, y + 7), color=(0.85, 0.83, 0.78), width=0.4)
        y += 22
    if policy:
        page.insert_text((48, 720), "Applied policy", fontsize=11)
        y = 740
        for notice in policy[:4]:
            page.insert_text((48, y), f"- {notice.message[:86]}", fontsize=8)
            y += 14
    content = document.tobytes(garbage=4, deflate=True)
    document.close()
    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": "attachment; filename=brsrlens-peer-board.pdf",
            "X-Quota-Remaining": str(quota.remaining),
            "X-Quota-Warning": str(quota.warning).lower(),
        },
    )
