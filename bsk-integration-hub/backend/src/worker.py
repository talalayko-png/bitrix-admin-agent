"""RQ worker entrypoint: ``python -m src.worker``."""

from __future__ import annotations

from src.config import get_settings
from src.db.base import init_db
from src.logging_conf import get_logger, setup_logging


def main() -> None:
    setup_logging()
    init_db()
    settings = get_settings()
    log = get_logger("worker")

    from rq import Queue, Worker

    from src.queue.connection import get_redis

    conn = get_redis()
    queue = Queue(settings.queue_name, connection=conn)
    log.info(
        "worker starting (queue=%s, redis=%s, dry_run=%s)",
        settings.queue_name,
        settings.redis_url,
        settings.dry_run,
    )
    worker = Worker([queue], connection=conn)
    worker.work(with_scheduler=True)


if __name__ == "__main__":
    main()
