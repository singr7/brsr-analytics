from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

Shape = Literal["distribution", "ranking", "timeseries", "comparison", "single"]
Operator = Literal["eq", "in", "gte", "lte", "between", "score_band", "top_n", "bottom_n"]


class QueryFilter(BaseModel):
    dimension: str
    operator: Operator = "eq"
    value: str | int | float | list[str | int | float]


class QuerySort(BaseModel):
    by: str = "value"
    direction: Literal["asc", "desc"] = "desc"


class SemanticQuery(BaseModel):
    measures: Annotated[list[str], Field(min_length=1, max_length=5)]
    dimensions: Annotated[list[str], Field(default_factory=list, max_length=4)]
    filters: Annotated[list[QueryFilter], Field(default_factory=list, max_length=12)]
    shape: Shape
    sort: QuerySort | None = None
    limit: Annotated[int, Field(default=25, ge=1, le=250)]

    @field_validator("measures", "dimensions")
    @classmethod
    def unique_keys(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("keys must be unique")
        return value

    @model_validator(mode="after")
    def shape_contract(self) -> "SemanticQuery":
        if self.shape == "timeseries" and "fy" not in self.dimensions:
            raise ValueError("timeseries queries require the fy dimension")
        if self.shape == "ranking" and "company" not in self.dimensions:
            raise ValueError("ranking queries require the company dimension")
        return self


class LineageRef(BaseModel):
    pin_id: str
    filing_id: str | None = None
    field_key: str | None = None
    source_page: int | None = None


class PolicyNotice(BaseModel):
    code: str
    message: str
    measure: str | None = None


class SemanticResponse(BaseModel):
    data: list[dict[str, object]]
    lineage_refs: dict[str, list[LineageRef]]
    applied_policy: list[PolicyNotice]
    catalog_version: str
    cache_hit: bool = False
