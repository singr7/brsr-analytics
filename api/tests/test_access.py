from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException

from api.app.core.access import OrgContext, require_plan, require_role


def context(role: str, tier: str) -> OrgContext:
    return OrgContext(
        org=SimpleNamespace(plan_tier=tier),  # type: ignore[arg-type]
        membership=SimpleNamespace(role=role),  # type: ignore[arg-type]
    )


async def invoke(dependency: object, value: OrgContext) -> OrgContext:
    call = dependency.dependency
    return await call(value)  # type: ignore[no-any-return]


@pytest.mark.parametrize(
    ("tier", "allowed"),
    [("explore", False), ("pro", True), ("studio", False), ("research", True)],
)
async def test_plan_gate_denies_unlisted_tiers(tier: str, allowed: bool) -> None:
    dependency: Any = require_plan("pro", "research")
    if allowed:
        assert (await invoke(dependency, context("member", tier))).org.plan_tier == tier
    else:
        with pytest.raises(HTTPException) as denied:
            await invoke(dependency, context("member", tier))
        assert denied.value.status_code == 403


async def test_owner_role_gate_denies_member() -> None:
    with pytest.raises(HTTPException) as denied:
        await invoke(require_role("owner"), context("member", "studio"))
    assert denied.value.status_code == 403
