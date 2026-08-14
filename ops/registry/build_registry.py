"""Build the governed company registry from an operator-supplied constituent export.

Input columns: cin,name,ticker,exchange,nic_code,industry,market_cap. The script ranks by
market_cap, retains the requested limit (1,000 by default), maps NIC divisions through the
committed taxonomy, and upserts on CIN. Source/licence provenance belongs in the input's
adjacent operator record; this script never downloads a constituent list.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
from decimal import Decimal
from pathlib import Path

import yaml
from sqlalchemy.dialects.postgresql import insert

from api.app.core.config import get_settings
from api.app.db.session import create_engine, create_session_factory
from api.app.models import Company


def load_sector_map(path: Path) -> tuple[dict[int, str], str]:
    document = yaml.safe_load(path.read_text())
    mapping: dict[int, str] = {}
    for group in document["groups"]:
        for division in group["nic_divisions"]:
            if division in mapping:
                raise ValueError(f"NIC division {division} appears in more than one group")
            mapping[int(division)] = str(group["label"])
    return mapping, str(document["fallback"]["label"])


def build_rows(source: Path, taxonomy: Path, limit: int = 1000) -> list[dict[str, object]]:
    mapping, fallback = load_sector_map(taxonomy)
    with source.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    required = {"cin", "name", "ticker", "exchange", "nic_code", "industry", "market_cap"}
    if not rows or not required.issubset(rows[0]):
        raise ValueError(f"Registry input requires columns: {', '.join(sorted(required))}")
    ranked = sorted(rows, key=lambda row: Decimal(row["market_cap"]), reverse=True)[:limit]
    if len({row["cin"] for row in ranked}) != len(ranked):
        raise ValueError("Duplicate CIN in ranked registry")
    result: list[dict[str, object]] = []
    for rank, row in enumerate(ranked, start=1):
        division = int(row["nic_code"][:2])
        mcap_band = "large" if rank <= 100 else "mid" if rank <= 250 else "small"
        result.append(
            {
                "cin": row["cin"].strip(),
                "name": row["name"].strip(),
                "ticker": row["ticker"].strip().upper(),
                "exchange": row["exchange"].strip().upper(),
                "sector": mapping.get(division, fallback),
                "industry": row["industry"].strip(),
                "mcap_band": mcap_band,
                "ir_url": row.get("ir_url", "").strip() or None,
            }
        )
    return result


async def upsert(rows: list[dict[str, object]]) -> None:
    engine = create_engine(get_settings())
    factory = create_session_factory(engine)
    try:
        async with factory() as session:
            statement = insert(Company).values(rows)
            statement = statement.on_conflict_do_update(
                index_elements=[Company.cin],
                set_={key: getattr(statement.excluded, key) for key in rows[0] if key != "cin"},
            )
            await session.execute(statement)
            await session.commit()
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--taxonomy", type=Path, default=Path("taxonomy/sectors.yaml"))
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    rows = build_rows(args.source, args.taxonomy, args.limit)
    if not args.dry_run:
        asyncio.run(upsert(rows))
    print(f"validated {len(rows)} companies; write={'no' if args.dry_run else 'yes'}")


if __name__ == "__main__":
    main()
