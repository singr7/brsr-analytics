from fastapi import APIRouter, Depends, Response, status

from api.app.core.config import Settings, get_settings
from api.app.schemas.health import HealthResponse
from api.app.services.health import get_health

router = APIRouter(tags=["health"])


@router.get("/healthz", response_model=HealthResponse)
async def healthz(response: Response, settings: Settings = Depends(get_settings)) -> HealthResponse:
    result = await get_health(settings)
    if result.status == "degraded":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return result
