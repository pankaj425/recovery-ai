"""In-process background webhook worker.

The API processes single webhooks synchronously (sub-millisecond pipeline),
but burst simulations use this queue so ingestion never blocks on ML work.
"""
from __future__ import annotations

import queue
import threading
from typing import Callable

from app.core.database import SessionLocal
from app.utils.logging_config import agent_logger

logger = agent_logger("recoveryai.worker")

_queue: "queue.Queue[Callable[[], None]]" = queue.Queue()
_worker: threading.Thread | None = None


def _run() -> None:
    while True:
        job = _queue.get()
        try:
            job()
        except Exception:  # noqa: BLE001 - worker must survive bad jobs
            logger.exception("webhook_job_failed")
        finally:
            _queue.task_done()


def start_worker() -> None:
    global _worker
    if _worker is None or not _worker.is_alive():
        _worker = threading.Thread(target=_run, name="webhook-worker", daemon=True)
        _worker.start()
        logger.info("webhook_worker_started")


def enqueue(job: Callable[[], None]) -> None:
    start_worker()
    _queue.put(job)


def enqueue_webhook_event(event_dict: dict) -> None:
    """Process a webhook payload off-thread with its own DB session."""

    def job() -> None:
        from app.schemas.webhook import PaymentEventIn
        from app.services.webhook_service import process_event

        db = SessionLocal()
        try:
            process_event(db, PaymentEventIn.model_validate(event_dict))
            db.commit()
        except Exception:  # noqa: BLE001
            db.rollback()
            logger.exception("webhook_processing_failed", extra={"event_id": event_dict.get("event_id")})
        finally:
            db.close()

    enqueue(job)


def queue_depth() -> int:
    return _queue.qsize()
