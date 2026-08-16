from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query, status

from api.app.core.access import CurrentUser, SessionDep
from api.app.core.config import Settings, get_settings
from api.app.models import Company
from api.app.schemas.acquisition import (
    CoverageResponse,
    FilingUploadResponse,
    IngestionInventoryResponse,
)
from api.app.services.acquisition import coverage, ingestion_inventory, store_filing
from api.app.services.storage import object_store

router = APIRouter(prefix="/api/admin", tags=["acquisition"])


def require_platform_admin(user: CurrentUser) -> None:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Platform administrator required")


@router.put(
    "/filings/{company_id}/{fy}",
    response_model=FilingUploadResponse,
    dependencies=[Depends(require_platform_admin)],
)
async def upload_filing(
    company_id: UUID,
    fy: int,
    content: Annotated[bytes, Body(media_type="application/octet-stream")],
    filename: Annotated[str, Header(alias="X-Filename")],
    session: SessionDep,
    settings: Annotated[Settings, Depends(get_settings)],
) -> FilingUploadResponse:
    if not 2000 <= fy <= 2200:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid financial year")
    if not content or len(content) > settings.manual_upload_max_bytes:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Invalid upload size")
    company = await session.get(Company, company_id)
    if company is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Company not found")
    try:
        filing, stored = await store_filing(
            session,
            object_store(settings),
            company=company,
            fy=fy,
            filename=filename,
            content=content,
            source="manual",
            source_adapter="manual_upload",
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    if filing.acquired_at is None:
        raise RuntimeError("Fetched filing has no acquisition timestamp")
    return FilingUploadResponse(
        filing_id=filing.id,
        company_id=company.id,
        fy=fy,
        status=filing.status,
        source=filing.source,
        object_uri=stored.uri,
        checksum_sha256=stored.checksum_sha256,
        deduplicated=stored.deduplicated,
        acquired_at=filing.acquired_at,
    )


@router.get(
    "/coverage",
    response_model=CoverageResponse,
    dependencies=[Depends(require_platform_admin)],
)
async def get_coverage(
    session: SessionDep,
    fy: Annotated[int, Query(ge=2000, le=2200)],
) -> CoverageResponse:
    return await coverage(session, fy)


@router.get(
    "/ingestion",
    response_model=IngestionInventoryResponse,
    dependencies=[Depends(require_platform_admin)],
)
async def get_ingestion_inventory(
    session: SessionDep,
    settings: Annotated[Settings, Depends(get_settings)],
) -> IngestionInventoryResponse:
    return await ingestion_inventory(session, settings)
