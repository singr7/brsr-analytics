from worker.celery_app import healthcheck


def test_worker_healthcheck() -> None:
    assert healthcheck.run() == "ok"
