from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from api.app.core.access import OrgContext, ensure_writable
from api.app.main import app
from api.app.routers.research import LICENCE_HEADER, dataset_csv, dataset_parquet, require_scope
from api.app.services.billing import invoice_plan_sheet
from api.app.services.plans import licence_state, load_plans, public_plans
from api.app.services.quotas import QuotaName, enforce_quota, quota_limit, quota_status


def test_expiry_state_machine_and_read_only_guard() -> None:
    now = datetime(2026, 8, 15, tzinfo=UTC)
    assert licence_state(now + timedelta(days=1), None, now=now) == "active"
    assert licence_state(now - timedelta(days=1), now + timedelta(days=2), now=now) == "grace"
    assert licence_state(now - timedelta(days=3), now - timedelta(days=1), now=now) == "read_only"
    context = OrgContext(
        org=SimpleNamespace(
            licence_expires_at=now - timedelta(days=3),
            licence_grace_until=now - timedelta(days=1),
        ),  # type: ignore[arg-type]
        membership=SimpleNamespace(role="owner"),  # type: ignore[arg-type]
    )
    with pytest.raises(HTTPException) as denied:
        ensure_writable(context)
    assert denied.value.detail["code"] == "licence_read_only"


@pytest.mark.parametrize("tier", ["explore", "pro", "studio", "research"])
@pytest.mark.parametrize(
    "name",
    ["nlq_per_day", "studio_tokens_per_month", "exports_per_month", "api_queries_per_minute"],
)
def test_every_plan_quota_uses_one_matrix(tier: str, name: QuotaName) -> None:
    limit = quota_limit(tier, name)
    assert limit >= 0
    if limit:
        warning = quota_status(tier, name, max(1, int(limit * 0.8)))
        assert warning.warning
        with pytest.raises(HTTPException):
            enforce_quota(tier, name, limit)
    else:
        with pytest.raises(HTTPException):
            enforce_quota(tier, name, 0)


def test_pricing_and_invoice_sheet_share_plan_config() -> None:
    config = load_plans()
    public = public_plans()
    assert public["tiers"] == config["tiers"]
    sheet = invoice_plan_sheet("pro", 7, 12, "billing@example.com")
    assert config["tiers"]["pro"]["price_label"] in sheet
    assert "Seats: 7" in sheet


def test_dataset_csv_has_embedded_licence_golden() -> None:
    content = dataset_csv([("Energy", 2025, "substance", 12, "72.1250")]).decode()
    assert content == (
        f"# licence: {LICENCE_HEADER}\n"
        "# methodology: /methodology; licence_terms: /licence\n"
        "sector,financial_year,measure,company_count,average_value\n"
        "Energy,2025,substance,12,72.1250\n"
    )


def test_dataset_parquet_has_embedded_licence_metadata() -> None:
    import io

    import pyarrow.parquet as pq

    content = dataset_parquet([("Energy", 2025, "substance", 12, 72.125)])
    metadata = pq.read_metadata(io.BytesIO(content)).metadata
    assert metadata is not None
    assert metadata[b"brsrlens.licence"].decode() == LICENCE_HEADER


def test_api_scope_and_s17_routes() -> None:
    key = SimpleNamespace(scopes_json=["query:read"])
    require_scope(key, "query:read")  # type: ignore[arg-type]
    with pytest.raises(HTTPException) as denied:
        require_scope(key, "dataset:read")  # type: ignore[arg-type]
    assert denied.value.detail == {"code": "scope_required", "scope": "dataset:read"}
    paths = app.openapi()["paths"]
    assert "/api/v1/query" in paths
    assert "/api/export/dataset" in paths
    assert "/api/admin/orgs/{org_id}/licence" in paths
    assert "/api/research/keys" in paths
