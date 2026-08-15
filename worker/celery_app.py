from celery import Celery  # type: ignore[import-untyped]

from api.app.core.config import get_settings

settings = get_settings()
celery_app = Celery("brsrlens", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(task_serializer="json", result_serializer="json", accept_content=["json"])
celery_app.conf.beat_schedule = {
    "nightly-metrics-rebuild": {
        "task": "worker.score.rebuild",
        "schedule": 24 * 60 * 60,
    }
}
celery_app.autodiscover_tasks(["worker.acquire", "worker.parse", "worker.extract", "worker.score"])


@celery_app.task(name="worker.healthcheck")  # type: ignore[untyped-decorator]
def healthcheck() -> str:
    return "ok"
