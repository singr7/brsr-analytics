from pydantic import BaseModel, Field

from api.app.schemas.semantic import SemanticQuery, SemanticResponse


class NLQRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)


class UnresolvedTerm(BaseModel):
    term: str
    choices: list[str]


class NLQTranslation(BaseModel):
    dsl: SemanticQuery | None = None
    interpretation: str
    confidence: float = Field(ge=0, le=1)
    unresolved_terms: list[UnresolvedTerm] = Field(default_factory=list)
    refusal: str | None = None

class NLQResponse(BaseModel):
    dsl: SemanticQuery | None
    interpretation: str
    confidence: float
    unresolved_terms: list[UnresolvedTerm]
    result: SemanticResponse | None
    suggested_refinements: list[str]
    refusal: str | None = None
