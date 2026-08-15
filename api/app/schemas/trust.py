from uuid import UUID

from pydantic import BaseModel, Field


class IssueCreate(BaseModel):
    pin_id: UUID
    description: str = Field(min_length=10, max_length=2000)


class AnnotationCreate(BaseModel):
    company_id: UUID
    pin_id: UUID
    body: str = Field(min_length=3, max_length=4000)


class PatternCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    pattern_note: str = Field(min_length=10, max_length=10000)
    topic: str = Field(min_length=2, max_length=100)
    is_published: bool = False
