from typing import Literal

from pydantic import BaseModel


class DependencyHealth(BaseModel):
    status: Literal["ok", "error"]
    detail: str | None = None


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    database: DependencyHealth
    redis: DependencyHealth
    llm_config: DependencyHealth

