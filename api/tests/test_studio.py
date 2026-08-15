from api.app.main import app


def test_phase3_routes_are_registered() -> None:
    paths = set(app.openapi()["paths"])
    assert "/api/studio/schema" in paths
    assert "/api/studio/filings/{filing_id}" in paths
    assert "/api/studio/filings/{filing_id}/exports" in paths
    assert "/api/studio/filings/{filing_id}/exports/{export_id}/download" in paths
