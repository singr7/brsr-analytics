from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from uuid import UUID

from api.app.core.config import get_settings
from api.app.db.session import create_engine, create_session_factory
from api.app.models import Company
from api.app.services.acquisition import store_filing
from api.app.services.storage import object_store


async def upload(company_id: UUID, fy: int, path: Path) -> None:
    settings = get_settings()
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    try:
        async with factory() as session:
            company = await session.get(Company, company_id)
            if company is None:
                raise ValueError("Company not found")
            filing, stored = await store_filing(
                session,
                object_store(settings),
                company=company,
                fy=fy,
                filename=path.name,
                content=await asyncio.to_thread(path.read_bytes),
                source="manual",
                source_adapter="manual_cli",
            )
            print(f"{filing.id} {stored.uri} deduplicated={stored.deduplicated}")
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Attach a lawful filing artifact")
    parser.add_argument("--company-id", required=True, type=UUID)
    parser.add_argument("--fy", required=True, type=int)
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    asyncio.run(upload(args.company_id, args.fy, args.path))


if __name__ == "__main__":
    main()
