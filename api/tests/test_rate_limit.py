from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from api.app.core.config import Settings
from api.app.services.rate_limit import enforce_rate_limit


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, int] = {}

    async def incr(self, key: str) -> int:
        self.values[key] = self.values.get(key, 0) + 1
        return self.values[key]

    async def expire(self, key: str, seconds: int) -> bool:
        return bool(key and seconds == 60)


async def test_rate_limit_is_scoped_by_identity() -> None:
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(redis=FakeRedis())))
    settings = Settings()
    await enforce_rate_limit(request, settings, "public", "one", 1)  # type: ignore[arg-type]
    await enforce_rate_limit(request, settings, "public", "two", 1)  # type: ignore[arg-type]
    with pytest.raises(HTTPException) as denied:
        await enforce_rate_limit(request, settings, "public", "one", 1)  # type: ignore[arg-type]
    assert denied.value.status_code == 429
