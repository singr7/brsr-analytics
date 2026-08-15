from decimal import Decimal

from pydantic import BaseModel


class ScoreDriftItem(BaseModel):
    score_key: str
    compared: int
    mean_absolute_drift: Decimal
    maximum_absolute_drift: Decimal


class ScoreDriftResponse(BaseModel):
    from_version: str
    to_version: str
    scores: list[ScoreDriftItem]
