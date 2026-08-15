import asyncio

from worker.score.tasks import run_rebuild


def main() -> None:
    metrics, scores = asyncio.run(run_rebuild())
    print(f"Materialized {metrics} metrics and {scores} scores.")


if __name__ == "__main__":
    main()
