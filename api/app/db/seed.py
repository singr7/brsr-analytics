import asyncio
import hashlib
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from api.app.db.session import create_engine, create_session_factory
from api.app.db.taxonomy import load_form_schema, upsert_field_defs
from api.app.models import (
    Company,
    ExtractedField,
    FieldVersionPin,
    Filing,
    FilingPage,
    Membership,
    Org,
    Plan,
    StudioFiling,
    StudioOrg,
    User,
)
from api.app.services.auth import hash_password

COMPANIES = [
    ("Aster Steel", "ASTSTEEL", "Metals", "Steel", "large"),
    ("Beacon Cement", "BEACEM", "Materials", "Cement", "large"),
    ("Cedar Chemicals", "CEDCHEM", "Chemicals", "Specialty chemicals", "mid"),
    ("Delta Motors", "DELMOT", "Automotive", "Passenger vehicles", "large"),
    ("Eon Mobility", "EONMOB", "Automotive", "Auto components", "small"),
    ("Flux Pharma", "FLUXPH", "Healthcare", "Pharmaceuticals", "mid"),
    ("Green Hospitals", "GRNHOSP", "Healthcare", "Hospitals", "small"),
    ("Helios Power", "HELPOW", "Energy", "Power generation", "large"),
    ("Ion Renewables", "IONREN", "Energy", "Renewable energy", "mid"),
    ("Jade Textiles", "JADETXT", "Consumer", "Textiles", "small"),
    ("Kite Foods", "KITEFOOD", "Consumer", "Packaged foods", "large"),
    ("Lumen Retail", "LUMRET", "Consumer", "Retail", "mid"),
    ("Meridian Mining", "MERMIN", "Metals", "Mining", "large"),
    ("Nova Alloys", "NOVALOY", "Metals", "Non-ferrous metals", "small"),
    ("Orchid Labs", "ORCLAB", "Healthcare", "Diagnostics", "mid"),
    ("Prism Polymers", "PRIPOLY", "Chemicals", "Polymers", "small"),
    ("Quartz Energy", "QUAENE", "Energy", "Oil and gas", "large"),
    ("River Paper", "RIVPAPR", "Materials", "Paper", "mid"),
    ("Solace Appliances", "SOLAPP", "Consumer", "Durables", "mid"),
    ("Terra Tyres", "TERTYRE", "Automotive", "Tyres", "small"),
]
TIERS = ("explore", "pro", "studio", "research")
PLAN_LIMITS = {
    "explore": '{"nlq_monthly": 10, "llm_tokens_monthly": 10000}',
    "pro": '{"nlq_monthly": 500, "llm_tokens_monthly": 500000}',
    "studio": '{"nlq_monthly": 200, "llm_tokens_monthly": 1000000}',
    "research": '{"nlq_monthly": 2000, "llm_tokens_monthly": 2000000}',
}
FISCAL_YEARS = (2024, 2025)


def stable_id(kind: str, key: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"brsrlens/seed/{kind}/{key}")


def _fingerprint(*parts: object) -> int:
    digest = hashlib.sha256("|".join(map(str, parts)).encode()).digest()
    return int.from_bytes(digest[:8], "big")


def synthetic_value(
    company_index: int, fy: int, field: dict[str, Any]
) -> tuple[str, Decimal | None]:
    """Generate repeatable, sector-plausible fixtures with intentional outliers.

    Numeric values trend down for environmental intensity fields and up for workforce
    coverage. Every 17th company/field combination is 4x to exercise outlier handling.
    Missingness is represented by omitted rows in ``seed_extractions``.
    """
    key = str(field["field_key"])
    dtype = str(field["dtype"])
    raw_seed = _fingerprint(company_index, fy, key)
    if dtype == "boolean":
        boolean_value = "true" if raw_seed % 5 else "false"
        return boolean_value, None
    if dtype == "text":
        return f"Synthetic disclosure for {key}", None
    if dtype == "date":
        return f"{fy}-03-31", None
    base = Decimal(raw_seed % 10_000 + 100) / Decimal(10)
    if "pct" in key or field.get("unit") == "percent":
        base = min(Decimal("100"), Decimal(45 + raw_seed % 55) + Decimal(fy - 2024))
    elif "intensity" in key:
        base *= Decimal("0.96") ** (fy - 2024)
    else:
        base *= Decimal(1 + company_index % 7)
    if (company_index + raw_seed) % 17 == 0:
        base *= 4
    numeric_value = base.quantize(Decimal("0.001"))
    if dtype == "integer":
        numeric_value = Decimal(int(numeric_value))
    return format(numeric_value, "f"), numeric_value


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
                "schema_version": "0.1.0",
            }
        ],
        "id",
    )


async def seed_corpus(session: AsyncSession, fields: list[dict[str, Any]]) -> None:
    companies: list[dict[str, Any]] = []
    filings: list[dict[str, Any]] = []
    pages: list[dict[str, Any]] = []
    extracted: list[dict[str, Any]] = []
    pins: list[dict[str, Any]] = []
    for index, (name, ticker, sector, industry, band) in enumerate(COMPANIES, start=1):
        company_id = stable_id("company", ticker)
        companies.append(
            {
                "id": company_id,
                "cin": f"L{index:05d}MH2000PLC{index:06d}",
                "name": name,
                "ticker": ticker,
                "exchange": "NSE",
                "sector": sector,
                "industry": industry,
                "mcap_band": band,
            }
        )
        for fy in FISCAL_YEARS:
            filing_id = stable_id("filing", f"{ticker}-{fy}")
            filings.append(
                {
                    "id": filing_id,
                    "company_id": company_id,
                    "fy": fy,
                    "source": "xbrl",
                    "s3_raw": f"s3://brsrlens-fixtures/{ticker}/{fy}.xhtml",
                    "status": "parsed",
                    "acquired_at": datetime(fy, 7, 1, tzinfo=UTC),
                }
            )
            pages.append(
                {
                    "id": stable_id("page", f"{ticker}-{fy}-1"),
                    "filing_id": filing_id,
                    "page_no": 1,
                    "text": f"Synthetic BRSR source page for {name}, FY {fy}.",
                    "s3_image": None,
                }
            )
            for field in fields:
                key = str(field["field_key"])
                # Deliberate gaps (~5%) exercise completeness scoring later.
                if _fingerprint(index, fy, key, "missing") % 20 == 0:
                    continue
                raw, numeric = synthetic_value(index, fy, field)
                extracted_id = stable_id("extracted", f"{ticker}-{fy}-{key}-v1")
                extracted.append(
                    {
                        "id": extracted_id,
                        "filing_id": filing_id,
                        "field_key": key,
                        "value_raw": raw,
                        "value_num": numeric,
                        "value_date": None,
                        "unit": field.get("unit"),
                        "confidence": Decimal("0.99"),
                        "method": "xbrl",
                        "source_page": 1,
                        "source_span": {"start": 0, "end": len(raw)},
                        "qa_status": "sampled_ok",
                        "version": 1,
                    }
                )
                pins.append(
                    {
                        "id": stable_id("pin", f"{ticker}-{fy}-{key}"),
                        "filing_id": filing_id,
                        "field_key": key,
                        "extracted_field_id": extracted_id,
                        "pinned_at": datetime.now(UTC),
                        "pinned_by_user_id": None,
                    }
                )
            # Version 2 intentionally remains unreviewed and therefore unpinned.
            key = "p6.e1.energy_total_gj"
            if any(row["field_key"] == key and row["filing_id"] == filing_id for row in extracted):
                raw, numeric = synthetic_value(
                    index, fy, next(f for f in fields if f["field_key"] == key)
                )
                extracted.append(
                    {
                        "id": stable_id("extracted", f"{ticker}-{fy}-{key}-v2"),
                        "filing_id": filing_id,
                        "field_key": key,
                        "value_raw": raw,
                        "value_num": (numeric or Decimal(0)) + 1,
                        "value_date": None,
                        "unit": "GJ",
                        "confidence": Decimal("0.75"),
                        "method": "llm",
                        "source_page": 1,
                        "source_span": {"start": 0, "end": len(raw)},
                        "qa_status": "unreviewed",
                        "version": 2,
                    }
                )
    await _upsert(session, Company, companies, "id")
    await _upsert(session, Filing, filings, "id")
    await _upsert(session, FilingPage, pages, "id")
    await _upsert(session, ExtractedField, extracted, "id")
    await _upsert(session, FieldVersionPin, pins, "id")


async def seed() -> None:
    engine = create_engine()
    factory = create_session_factory(engine)
    _, fields = load_form_schema()
    async with factory() as session, session.begin():
        await upsert_field_defs(session)
        await seed_access(session)
        await seed_corpus(session, fields)
    await engine.dispose()
    summary = (
        f"Seeded {len(COMPANIES)} companies, {len(COMPANIES) * 2} filings, "
        f"and {len(fields)} field definitions."
    )
    print(summary)


if __name__ == "__main__":
    asyncio.run(seed())
