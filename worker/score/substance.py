from pydantic import BaseModel, Field

from api.app.services.llm import LLMClient


class SubstanceVerdict(BaseModel):
    quantified_target: bool
    dated_commitment: bool
    named_methodology: bool
    confidence: float = Field(ge=0, le=1)


async def llm_substance_verdict(llm: LLMClient, disclosure: str) -> SubstanceVerdict:
    """Second opinion used for ambiguous narratives and live corpus calibration."""
    return await llm.complete(
        "substance_verdict",
        "v1",
        {"disclosure": disclosure},
        SubstanceVerdict,
    )
