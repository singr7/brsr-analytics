import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.app.core.access import optional_user
from api.app.core.config import Settings, get_settings
from api.app.db.session import get_db_session
from api.app.models import User
from api.app.routers.semantic import resolve_tier
from api.app.schemas.nlq import NLQRequest, NLQResponse, NLQTranslation
from api.app.schemas.semantic import SemanticResponse
from api.app.services.llm import LLMError, get_llm
from api.app.services.nlq import merge_context
from api.app.services.quotas import consume_redis_quota, period_key
from api.app.services.semantic import SemanticError, execute_query, load_catalog
from api.app.services.track import persist_events

router = APIRouter(prefix="/api", tags=["nlq"])
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
OUT_OF_SCOPE = ("stock tip", "share price", "buy stock", "sell stock", "weather", "cricket")


@router.post("/nlq", response_model=NLQResponse)
async def natural_language_query(
    payload: NLQRequest,
    request: Request,
    session: SessionDep,
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[User | None, Depends(optional_user)],
    x_org_id: Annotated[UUID | None, Header()] = None,
) -> NLQResponse:
    catalog = load_catalog()
    tier = await resolve_tier(session, user, x_org_id)
    identity = str(user.id) if user else request.client.host if request.client else "anonymous"
    quota = await consume_redis_quota(
        request.app.state.redis,
        tier=tier,
        identity=identity,
        name="nlq_per_day",
    )
    if quota.warning and user is not None:
        period, ttl = period_key("nlq_per_day")
        first_warning = await request.app.state.redis.set(
            f"quota-warning:nlq:{user.id}:{period}", "1", ex=ttl, nx=True
        )
        if first_warning:
            await persist_events(
                session,
                [
                    {
                        "name": "quota_headroom_viewed",
                        "session_id": user.id,
                        "properties": {
                            "quota": "nlq_per_day",
                            "tier": tier,
                            "remaining": quota.remaining,
                        },
                    }
                ],
                anon_id=None,
                user_id=user.id,
            )
            await session.commit()
    if any(term in payload.question.lower() for term in OUT_OF_SCOPE):
        response = NLQResponse(
            dsl=None,
            interpretation="This asks for advice or data outside the BRSR disclosure corpus.",
            confidence=1,
            unresolved_terms=[],
            result=None,
            suggested_refinements=["Ask about a BRSR metric, score, sector, company, or year."],
            refusal="I can analyse BRSR disclosures, but not provide stock tips or unrelated data.",
        )
        return response
    context = json.dumps(
        {
            "measures": catalog.measures,
            "dimensions": catalog.dimensions,
            "filters": catalog.filters,
            "shapes": catalog.shapes,
        },
        sort_keys=True,
    )
    base_context = (
        payload.base_dsl.model_dump_json(exclude_none=True)
        if payload.base_dsl is not None
        else "No inherited analytical context."
    )
    try:
        translated = await get_llm(settings).complete(
            "nlq",
            "v1",
            {
                "catalog_context": context,
                "base_context": base_context,
                "question": payload.question,
            },
            NLQTranslation,
        )
    except (LLMError, ValueError) as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, f"Unable to interpret: {exc}"
        ) from exc
    if translated.dsl is None or translated.refusal:
        return NLQResponse(
            **translated.model_dump(),
            result=None,
            suggested_refinements=["Name a measure, grouping, and financial year."],
        )
    merged_dsl, provenance = merge_context(payload.base_dsl, translated.dsl)
    try:
        data, lineage, policy = await execute_query(session, merged_dsl, tier, catalog)
    except SemanticError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            {"code": "invalid_translation", "validator_errors": str(exc)},
        ) from exc
    result = SemanticResponse(
        data=data,
        lineage_refs=lineage,
        applied_policy=policy,
        catalog_version=catalog.version,
    )
    response = NLQResponse(
        **translated.model_dump(exclude={"dsl"}),
        dsl=merged_dsl,
        result=result,
        suggested_refinements=["Change the year", "Add a sector", "Compare another measure"],
        context=provenance,
    )
    if quota.warning:
        response.suggested_refinements.append(
            f"Plan headroom: {quota.remaining} NLQ requests remain today."
        )
    return response
