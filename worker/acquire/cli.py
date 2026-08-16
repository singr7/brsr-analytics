from __future__ import annotations

import argparse
import asyncio

from api.app.core.config import get_settings
from api.app.db.session import create_engine, create_session_factory
from api.app.services.storage import object_store
from worker.acquire.nse import ingest_nse_batch


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description="Ingest official NSE BRSR XBRL filings")
    subcommands = command.add_subparsers(dest="mode", required=True)
    for mode, default_limit in (("initial", 25), ("next", 10), ("refresh", 50)):
        item = subcommands.add_parser(mode)
        item.add_argument("--fy", type=int)
        item.add_argument("--limit", type=int, default=default_limit)
        item.add_argument("--start", type=int)
        if mode == "initial":
            item.add_argument("--replace-synthetic", action="store_true")
    return command


async def run(args: argparse.Namespace) -> None:
    settings = get_settings()
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    try:
        async with factory() as session:
            result = await ingest_nse_batch(
                session,
                object_store(settings),
                settings,
                mode=str(args.mode),
                target_fy=args.fy or settings.nse_brsr_default_fy,
                limit=args.limit,
                start=args.start,
                replace_synthetic=bool(getattr(args, "replace_synthetic", False)),
            )
            print(
                f"run={result.id} status={result.status} discovered={result.discovered_count} "
                f"fetched={result.fetched_count} parsed={result.parsed_count} "
                f"missing={result.missing_count} errors={result.error_count}"
            )
            if result.error_summary:
                print(result.error_summary)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run(parser().parse_args()))
