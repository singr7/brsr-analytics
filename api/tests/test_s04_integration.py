import os

import httpx
import pytest

from api.app.db.seed import stable_id

API_URL = os.getenv("BRSRLENS_API_TEST_URL")
pytestmark = pytest.mark.skipif(
    not API_URL,
    reason="set BRSRLENS_API_TEST_URL against the running migrated API",
)


async def login(client: httpx.AsyncClient, tier: str) -> dict[str, str]:
    response = await client.post(
        "/api/auth/login",
        json={"email": f"demo+{tier}@brsrlens.local", "password": "DemoPassword123!"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def test_manual_upload_dedupe_admin_gate_and_coverage() -> None:
    company_id = stable_id("company", "ASTSTEEL")
    content = b"%PDF-1.4\n% synthetic live upload\n%%EOF\n"
    async with httpx.AsyncClient(base_url=API_URL, timeout=30) as client:
        non_admin = await login(client, "studio")
        denied = await client.put(
            f"/api/admin/filings/{company_id}/2199",
            headers={**non_admin, "X-Filename": "fixture.pdf"},
            content=content,
        )
        assert denied.status_code == 403

        admin = await login(client, "research")
        uploaded = await client.put(
            f"/api/admin/filings/{company_id}/2199",
            headers={**admin, "X-Filename": "fixture.pdf"},
            content=content,
        )
        assert uploaded.status_code == 200, uploaded.text
        assert uploaded.json()["status"] == "fetched"
        assert not uploaded.json()["deduplicated"]

        repeated = await client.put(
            f"/api/admin/filings/{company_id}/2199",
            headers={**admin, "X-Filename": "fixture.pdf"},
            content=content,
        )
        assert repeated.status_code == 200
        assert repeated.json()["deduplicated"]

        report = await client.get("/api/admin/coverage?fy=2199", headers=admin)
        assert report.status_code == 200
        assert report.json()["companies"] == 20
        assert report.json()["fetched"] == 1
