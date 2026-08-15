import json
from datetime import UTC, datetime
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
from api.app.services.semantic import SemanticError, execute_query, load_catalog

router = APIRouter(prefix="/api", tags=["nlq"])
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
OUT_OF_SCOPE = ("stock tip", "share price", "buy stock", "sell stock", "weather", "cricket")
QUOTAS = {"explore": 10, "pro": 500, "studio": 200, "research": 2000}


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
    month = datetime.now(UTC).strftime("%Y-%m")
    quota_key = f"nlq:{tier}:{identity}:{month}"
    usage = int(await request.app.state.redis.incr(quota_key))
    if usage == 1:
        await request.app.state.redis.expire(quota_key, 2_678_400)
    if usage > QUOTAS[tier]:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "NLQ monthly quota exceeded")
    if any(term in payload.question.lower() for term in OUT_OF_SCOPE):
        return NLQResponse(
            dsl=None,
            interpretation="This asks for advice or data outside the BRSR disclosure corpus.",
            confidence=1,
            unresolved_terms=[],
            result=None,
            suggested_refinements=["Ask about a BRSR metric, score, sector, company, or year."],
            refusal="I can analyse BRSR disclosures, but not provide stock tips or unrelated data.",
        )
    context = json.dumps(
        {
            "measures": catalog.measures,
            "dimensions": catalog.dimensions,
            "filters": catalog.filters,
            "shapes": catalog.shapes,
        },
        sort_keys=True,
    )
    try:
        translated = await get_llm(settings).complete(
            "nlq", "v1", {"catalog_context": context, "question": payload.question}, NLQTranslation
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
    try:
        data, lineage, policy = await execute_query(session, translated.dsl, tier, catalog)
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
    return NLQResponse(
        **translated.model_dump(),
        result=result,
        suggested_refinements=["Change the year", "Add a sector", "Compare another measure"],
    )
