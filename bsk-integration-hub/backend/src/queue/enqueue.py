"""Enqueue operations onto the queue backend (redis | sync)."""

from __future__ import annotations

from datetime import timedelta

from src.config import get_settings
from src.domain.enums import ExecuteResult
from src.logging_conf import get_logger

log = get_logger("queue.enqueue")


def enqueue_operation(operation_id: int) -> None:
    """Entry point used by the operation service to schedule execution."""
    settings = get_settings()
    if settings.queue_backend == "redis":
        _enqueue_redis(operation_id, delay_seconds=0)
    else:
        _run_sync(operation_id)


def enqueue_retry(operation_id: int, delay_seconds: int) -> None:
    settings = get_settings()
    if settings.queue_backend == "redis":
        _enqueue_redis(operation_id, delay_seconds=delay_seconds)
    # In sync mode retries are handled by the inline loop in ``_run_sync``.


def _enqueue_redis(operation_id: int, delay_seconds: int = 0) -> None:
    from rq import Queue

    from src.queue.connection import get_redis
    from src.queue.jobs import run_operation

    conn = get_redis()
    queue = Queue(get_settings().queue_name, connection=conn)
    if delay_seconds and delay_seconds > 0:
        queue.enqueue_in(timedelta(seconds=delay_seconds), run_operation, operation_id)
        log.info("operation %s re-enqueued in %ss", operation_id, delay_seconds)
    else:
        queue.enqueue(run_operation, operation_id)
        log.info("operation %s enqueued", operation_id)


def _run_sync(operation_id: int) -> None:
    """Execute inline (no worker). Honors retries via a bounded loop without
    real sleeping — intended for local dev and tests."""
    from src.services.operations import OperationService

    service = OperationService()
    settings = get_settings()
    for _ in range(settings.worker_max_retries + 2):
        outcome = service.execute(operation_id)
        if outcome.result != ExecuteResult.retry:
            break
