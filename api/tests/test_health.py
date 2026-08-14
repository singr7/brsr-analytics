from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from api.app.core.config import Settings, get_settings
from api.app.main import app


async def _healthy() -> None:
    return None


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    settings = Settings(llm_provider="fake")
    app.dependency_overrides[get_settings] = lambda: settings
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as value:
        yield value
    app.dependency_overrides.clear()


async def test_health_response_contract(
    monkeypatch: pytest.MonkeyPatch, client: AsyncClient
) -> None:
    from api.app.routers import health

    async def fake_health(settings: Settings):  # type: ignore[no-untyped-def]
        from api.app.services.health import get_health

        return await get_health(settings, _healthy, _healthy)

    monkeypatch.setattr(health, "get_health", fake_health)
    response = await client.get("/healthz", headers={"X-Request-ID": "test-request"})
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.headers["X-Request-ID"] == "test-request"


async def test_health_reports_missing_llm_config() -> None:
    from api.app.services.health import get_health

    result = await get_health(Settings(llm_provider="live", llm_api_key=None), _healthy, _healthy)
    assert result.status == "degraded"
    assert result.llm_config.status == "error"
