from __future__ import annotations

import logging
import socket
import threading
import time

from app.config import Settings
from app.db import connect
from app.repositories import (
    claim_next_task_job,
    create_task_job,
    get_task_by_id,
    mark_task_job_failed,
    mark_task_job_succeeded,
    recover_interrupted_task_jobs,
)
from app.task_runner import run_task


logger = logging.getLogger(__name__)
_worker_started = False
_worker_lock = threading.Lock()
_worker_id = f"{socket.gethostname()}:{threading.get_ident()}:audit-task-worker"


def enqueue_task(settings: Settings, task_id: int) -> None:
    conn = connect(settings.db_path)
    try:
        create_task_job(conn, task_id)
    finally:
        conn.close()
    _ensure_worker(settings)


def start_worker(settings: Settings) -> None:
    _ensure_worker(settings)


def recover_interrupted_jobs(settings: Settings) -> int:
    conn = connect(settings.db_path)
    try:
        return recover_interrupted_task_jobs(conn)
    finally:
        conn.close()


def worker_state() -> dict[str, object]:
    return {
        "worker_started": _worker_started,
        "worker_id": _worker_id if _worker_started else None,
    }


def _ensure_worker(settings: Settings) -> None:
    global _worker_started
    if _worker_started:
        return
    with _worker_lock:
        if _worker_started:
            return
        thread = threading.Thread(
            target=_worker_loop,
            args=(settings,),
            name="audit-task-worker",
            daemon=True,
        )
        thread.start()
        _worker_started = True


def _worker_loop(settings: Settings) -> None:
    while True:
        job = _claim_next(settings)
        if job is None:
            time.sleep(1.0)
            continue
        _process_job(settings, job)


def _process_job(settings: Settings, job) -> None:
    try:
        run_task(settings, job.task_id)
        task = _get_task(settings, job.task_id)
        if task is not None and task.status == "failed":
            _mark_failed(settings, job.id, task.error_message or "任务执行失败")
            return
        _mark_succeeded(settings, job.id)
    except Exception:  # noqa: BLE001 - keep the worker alive for later jobs.
        logger.exception("Audit task worker failed for task_id=%s", job.task_id)
        _mark_failed(settings, job.id, "任务执行异常")


def _claim_next(settings: Settings):
    conn = connect(settings.db_path)
    try:
        return claim_next_task_job(conn, _worker_id)
    finally:
        conn.close()


def _get_task(settings: Settings, task_id: int):
    conn = connect(settings.db_path)
    try:
        return get_task_by_id(conn, task_id)
    finally:
        conn.close()


def _mark_succeeded(settings: Settings, job_id: int) -> None:
    conn = connect(settings.db_path)
    try:
        mark_task_job_succeeded(conn, job_id)
    finally:
        conn.close()


def _mark_failed(settings: Settings, job_id: int, error_message: str) -> None:
    conn = connect(settings.db_path)
    try:
        mark_task_job_failed(conn, job_id, error_message)
    finally:
        conn.close()
