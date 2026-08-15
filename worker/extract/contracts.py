from pydantic import BaseModel, Field, model_validator


class ExtractionItem(BaseModel):
    field_key: str
    value: str | int | float | bool | None = None
    unit: str | None = None
    source_page: int | None = None
    source_quote: str | None = None
    confidence: float = Field(ge=0, le=1)
    not_found: bool = False

    @model_validator(mode="after")
    def found_values_have_lineage(self) -> "ExtractionItem":
        if not self.not_found and (self.value is None or self.source_page is None):
            raise ValueError("Found values require a value and source page")
        return self


class ExtractionResponse(BaseModel):
    fields: list[ExtractionItem]
