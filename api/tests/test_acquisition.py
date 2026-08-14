from uuid import uuid4

import pytest
from fastapi import HTTPException

from api.app.models import User
from api.app.routers.acquisition import require_platform_admin
from api.app.services.acquisition import coverage


class FakeResult:
    def all(self) -> list[tuple[str, str, int, int]]:
        return [
            ("Financial Services", "large", 2, 1),
            ("Technology & Communications", "mid", 3, 3),
        ]


class FakeSession:
    async def execute(self, statement: object) -> FakeResult:
        del statement
        return FakeResult()


async def test_coverage_is_correct_by_sector_and_mcap_band() -> None:
    result = await coverage(FakeSession(), 2024)  # type: ignore[arg-type]
    assert result.companies == 5
    assert result.fetched == 4
    assert result.coverage_percent == 80.0
    assert result.groups[0].coverage_percent == 50.0
    assert result.groups[1].coverage_percent == 100.0


def test_acquisition_admin_gate_allows_only_platform_admin() -> None:
    user = User(
        id=uuid4(),
        email="operator@example.test",
        password_hash="unused",
        display_name="Operator",
        email_verified_at=None,
        plan_tier="research",
        is_admin=False,
    )
    with pytest.raises(HTTPException) as denied:
        require_platform_admin(user)
    assert denied.value.status_code == 403
    user.is_admin = True
    assert require_platform_admin(user) is None
