"""RQ job functions executed by the worker."""

from __future__ import annotations

from src.domain.enums import ExecuteResult
from src.logging_conf import get_logger

log = get_logger("queue.jobs")


def run_operation(operation_id: int) -> str:
    """Execute a single operation. On a retryable failure, re-schedule it with
    exponential backoff via the Redis queue."""
    from src.services.operations import OperationService

    service = OperationService()
    outcome = service.execute(operation_id)
    log.info("operation %s -> %s", operation_id, outcome.result.value)

    if outcome.result == ExecuteResult.retry:
        from src.queue.enqueue import enqueue_retry

        enqueue_retry(operation_id, outcome.retry_delay)

    return outcome.result.value
