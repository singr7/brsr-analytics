import os
from uuid import uuid4

import httpx
import pytest

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
    return response.json()


async def test_auth_refresh_reuse_org_isolation_beacon_and_privacy() -> None:
    async with httpx.AsyncClient(base_url=API_URL, timeout=10) as client:
        studio = await login(client, "studio")
        auth = {"Authorization": f"Bearer {studio['access_token']}"}
        me = await client.get("/api/auth/me", headers=auth)
        assert me.status_code == 200
        org_id = me.json()["orgs"][0]["id"]

        rotated = await client.post(
            "/api/auth/refresh", json={"refresh_token": studio["refresh_token"]}
        )
        assert rotated.status_code == 200
        reused = await client.post(
            "/api/auth/refresh", json={"refresh_token": studio["refresh_token"]}
        )
        assert reused.status_code == 401
        family_revoked = await client.post(
            "/api/auth/refresh", json={"refresh_token": rotated.json()["refresh_token"]}
        )
        assert family_revoked.status_code == 401

        explore = await login(client, "explore")
        denied = await client.post(
            "/api/orgs/invites",
            headers={
                "Authorization": f"Bearer {explore['access_token']}",
                "X-Org-ID": org_id,
            },
            json={"email": "nobody@example.com", "role": "member"},
        )
        assert denied.status_code == 403

        pageview = await client.post(
            "/api/events",
            headers=auth,
            json={
                "events": [
                    {
                        "name": "page_viewed",
                        "session_id": str(uuid4()),
                        "properties": {"path": "/integration"},
                    }
                ]
            },
        )
        assert pageview.status_code == 202
        assert pageview.json() == {"accepted": 1}
        assert pageview.cookies.get("anon_id")
        exported = await client.get("/api/privacy/export", headers=auth)
        assert any(event["name"] == "page_viewed" for event in exported.json()["events"])
        deleted = await client.delete("/api/privacy/delete", headers=auth)
        assert deleted.status_code == 200

        admin = await login(client, "research")
        changed = await client.patch(
            f"/api/admin/orgs/{org_id}/plan",
            headers={"Authorization": f"Bearer {admin['access_token']}"},
            json={"tier": "studio"},
        )
        assert changed.status_code == 200
        assert changed.json()["plan_tier"] == "studio"
