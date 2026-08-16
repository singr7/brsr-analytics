import asyncio
from datetime import UTC, datetime
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from api.app.db.session import create_engine, create_session_factory
from api.app.db.taxonomy import load_form_schema, upsert_field_defs
from api.app.models import (
    Membership,
    Org,
    Plan,
    StudioFiling,
    StudioOrg,
    User,
)
from api.app.services.auth import hash_password

TIERS = ("explore", "pro", "studio", "research")
PLAN_LIMITS = {
    "explore": '{"nlq_monthly": 10, "llm_tokens_monthly": 10000}',
    "pro": '{"nlq_monthly": 500, "llm_tokens_monthly": 500000}',
    "studio": '{"nlq_monthly": 200, "llm_tokens_monthly": 1000000}',
    "research": '{"nlq_monthly": 2000, "llm_tokens_monthly": 2000000}',
}
def stable_id(kind: str, key: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"brsrlens/seed/{kind}/{key}")


async def _upsert(
    session: AsyncSession, model: type[Any], rows: list[dict[str, Any]], key: str
) -> None:
    if not rows:
        return
    for start in range(0, len(rows), 400):
        statement = insert(model).values(rows[start : start + 400])
        updates = {
            column.name: getattr(statement.excluded, column.name)
            for column in model.__table__.columns
            if column.name not in {key, "created_at"}
        }
        await session.execute(
            statement.on_conflict_do_update(index_elements=[getattr(model, key)], set_=updates)
        )


async def seed_access(session: AsyncSession) -> None:
    await _upsert(
        session,
        Plan,
        [{"tier": tier, "name": tier.title(), "limits_json": PLAN_LIMITS[tier]} for tier in TIERS],
        "tier",
    )
    users = [
        {
            "id": stable_id("user", tier),
            "email": f"demo+{tier}@brsrlens.local",
            "password_hash": hash_password("DemoPassword123!"),
            "display_name": f"{tier.title()} Demo",
            "email_verified_at": datetime.now(UTC),
            "plan_tier": tier,
            "is_admin": tier == "research",
        }
        for tier in TIERS
    ]
    await _upsert(session, User, users, "id")
    org_id = stable_id("org", "demo-studio")
    await _upsert(
        session,
        Org,
        [{"id": org_id, "name": "Demo Studio Ltd", "slug": "demo-studio", "plan_tier": "studio"}],
        "id",
    )
    await _upsert(
        session,
        Membership,
        [
            {
                "id": stable_id("membership", "studio-owner"),
                "org_id": org_id,
                "user_id": stable_id("user", "studio"),
                "role": "owner",
            }
        ],
        "id",
    )
    studio_org_id = stable_id("studio-org", "demo-studio")
    await _upsert(
        session,
        StudioOrg,
        [
            {
                "id": studio_org_id,
                "org_id": org_id,
                "legal_name": "Demo Studio Limited",
                "cin": "U00000MH2020PLC000001",
            }
        ],
        "id",
    )
    await _upsert(
        session,
        StudioFiling,
        [
            {
                "id": stable_id("studio-filing", "demo-2025"),
                "studio_org_id": studio_org_id,
                "fy": 2025,
                "status": "draft",
                "schema_version": "1.0.0",
            }
        ],
        "id",
    )


async def seed() -> None:
    engine = create_engine()
    factory = create_session_factory(engine)
    _, fields = load_form_schema()
    async with factory() as session, session.begin():
        await upsert_field_defs(session)
        await seed_access(session)
    await engine.dispose()
    print(f"Seeded access fixtures and {len(fields)} field definitions; no corpus data added.")


if __name__ == "__main__":
    asyncio.run(seed())
