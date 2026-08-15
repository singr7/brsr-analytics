from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, func, select
from sqlalchemy.orm import aliased

from api.app.core.access import SessionDep
from api.app.models import Score
from api.app.routers.acquisition import require_platform_admin
from api.app.schemas.scoring import ScoreDriftItem, ScoreDriftResponse

router = APIRouter(
    prefix="/api/admin", tags=["scoring"], dependencies=[Depends(require_platform_admin)]
)


@router.get("/score-drift", response_model=ScoreDriftResponse)
async def score_drift(
    session: SessionDep,
    from_version: Annotated[str, Query(min_length=1)],
    to_version: Annotated[str, Query(min_length=1)],
) -> ScoreDriftResponse:
    old = aliased(Score)
    new = aliased(Score)
    difference = func.abs(new.value - old.value)
    rows = (
        await session.execute(
            select(
                old.score_key,
                func.count(),
                func.avg(difference),
                func.max(difference),
            )
            .join(
                new,
                and_(
                    new.company_id == old.company_id,
                    new.fy == old.fy,
                    new.score_key == old.score_key,
                    new.method_version == to_version,
                ),
            )
            .where(old.method_version == from_version)
            .group_by(old.score_key)
            .order_by(old.score_key)
        )
    ).all()
    return ScoreDriftResponse(
        from_version=from_version,
        to_version=to_version,
        scores=[
            ScoreDriftItem(
                score_key=key,
                compared=count,
                mean_absolute_drift=mean_drift,
                maximum_absolute_drift=max_drift,
            )
            for key, count, mean_drift, max_drift in rows
        ],
    )
