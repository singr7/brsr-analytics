from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class FilingCreate(BaseModel):
    fy: int = Field(ge=2020, le=2100)


class AnswerWrite(BaseModel):
    value: str = Field(min_length=1, max_length=100_000)
    unit: str | None = Field(default=None, max_length=32)


class ProposalDecision(BaseModel):
    decision: Literal["accepted", "edited", "rejected"]
    value: str | None = Field(default=None, max_length=100_000)


class BulkProposalDecision(BaseModel):
    proposal_ids: list[UUID] = Field(min_length=1, max_length=100)


class CommentCreate(BaseModel):
    field_key: str = Field(min_length=3, max_length=160)
    body: str = Field(min_length=1, max_length=4000)


class ExportCreate(BaseModel):
    kinds: list[Literal["xbrl", "docx", "pdf", "gap_pdf"]] = Field(
        default=["xbrl", "docx", "pdf", "gap_pdf"], min_length=1
    )


class StudioResponse(BaseModel):
    data: dict[str, Any]
