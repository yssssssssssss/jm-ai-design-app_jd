from app.config import Settings
from app.db import connect, init_db
from app.models import TASK_FAILED, TASK_QUEUED, TASK_RUNNING, TASK_SUCCEEDED
from app.repositories import (
    claim_next_task_job,
    create_task,
    create_task_job,
    create_user,
    get_task_by_id,
    list_task_jobs,
    mark_task_job_succeeded,
    recover_interrupted_task_jobs,
    update_task_status,
)


def _settings(tmp_path):
    return Settings(
        openai_api_key="key",
        app_secret_key="secret",
        register_invite_code="invite",
        initial_admin_username="admin",
        initial_admin_password="password123",
        data_dir=tmp_path,
    )


def test_task_jobs_are_persisted_and_claimed_in_order(tmp_path):
    settings = _settings(tmp_path)
    conn = connect(settings.db_path)
    init_db(conn)
    user = create_user(conn, "alice", "hash-1", "user")
    first = create_task(conn, user.id, "First", 1)
    second = create_task(conn, user.id, "Second", 1)

    create_task_job(conn, first.id)
    create_task_job(conn, second.id)

    claimed = claim_next_task_job(conn, worker_id="worker-1")
    jobs = list_task_jobs(conn)

    assert claimed is not None
    assert claimed.task_id == first.id
    assert claimed.attempts == 1
    assert jobs[0].status == TASK_RUNNING
    assert jobs[0].locked_by == "worker-1"
    assert jobs[1].status == TASK_QUEUED


def test_recover_interrupted_task_jobs_requeues_running_tasks(tmp_path):
    settings = _settings(tmp_path)
    conn = connect(settings.db_path)
    init_db(conn)
    user = create_user(conn, "alice", "hash-1", "user")
    running_task = create_task(conn, user.id, "Interrupted", 1)
    queued_task = create_task(conn, user.id, "Queued", 1)
    create_task_job(conn, running_task.id)
    create_task_job(conn, queued_task.id)
    claim_next_task_job(conn, worker_id="worker-1")
    update_task_status(conn, running_task.id, TASK_RUNNING)

    recovered = recover_interrupted_task_jobs(conn)

    running = get_task_by_id(conn, running_task.id)
    jobs = list_task_jobs(conn)
    assert recovered == 2
    assert running is not None
    assert running.status == TASK_QUEUED
    assert [job.status for job in jobs] == [TASK_QUEUED, TASK_QUEUED]
    assert all(job.locked_at is None and job.locked_by is None for job in jobs)


def test_recover_interrupted_task_jobs_creates_jobs_for_existing_active_tasks(tmp_path):
    settings = _settings(tmp_path)
    conn = connect(settings.db_path)
    init_db(conn)
    user = create_user(conn, "alice", "hash-1", "user")
    queued = create_task(conn, user.id, "Already queued", 1)
    running = create_task(conn, user.id, "Already running", 1)
    update_task_status(conn, running.id, TASK_RUNNING)

    recovered = recover_interrupted_task_jobs(conn)

    jobs = list_task_jobs(conn)
    refreshed_running = get_task_by_id(conn, running.id)
    assert recovered == 2
    assert [job.task_id for job in jobs] == [queued.id, running.id]
    assert [job.status for job in jobs] == [TASK_QUEUED, TASK_QUEUED]
    assert refreshed_running is not None
    assert refreshed_running.status == TASK_QUEUED


def test_mark_task_job_succeeded_finishes_claimed_job(tmp_path):
    settings = _settings(tmp_path)
    conn = connect(settings.db_path)
    init_db(conn)
    user = create_user(conn, "alice", "hash-1", "user")
    task = create_task(conn, user.id, "Audit", 1)
    create_task_job(conn, task.id)
    claimed = claim_next_task_job(conn, worker_id="worker-1")
    assert claimed is not None

    mark_task_job_succeeded(conn, claimed.id)

    [job] = list_task_jobs(conn)
    assert job.status == "succeeded"
    assert job.finished_at is not None


def test_worker_marks_job_failed_when_task_runner_finishes_failed(
    monkeypatch,
    tmp_path,
):
    import app.task_queue as task_queue

    settings = _settings(tmp_path)
    conn = connect(settings.db_path)
    init_db(conn)
    user = create_user(conn, "alice", "hash-1", "user")
    task = create_task(conn, user.id, "Audit", 1)
    create_task_job(conn, task.id)
    claimed = claim_next_task_job(conn, worker_id="worker-1")
    assert claimed is not None

    def fail_task(current_settings, task_id):
        update_task_status(conn, task_id, TASK_FAILED, error_message="全部图片审核失败")

    monkeypatch.setattr(task_queue, "run_task", fail_task)

    task_queue._process_job(settings, claimed)

    [job] = list_task_jobs(conn)
    assert job.status == TASK_FAILED
    assert job.error_message == "全部图片审核失败"
    assert job.finished_at is not None


def test_worker_marks_job_succeeded_when_task_runner_finishes_succeeded(
    monkeypatch,
    tmp_path,
):
    import app.task_queue as task_queue

    settings = _settings(tmp_path)
    conn = connect(settings.db_path)
    init_db(conn)
    user = create_user(conn, "alice", "hash-1", "user")
    task = create_task(conn, user.id, "Audit", 1)
    create_task_job(conn, task.id)
    claimed = claim_next_task_job(conn, worker_id="worker-1")
    assert claimed is not None

    def succeed_task(current_settings, task_id):
        update_task_status(conn, task_id, TASK_SUCCEEDED, summary="审核完成")

    monkeypatch.setattr(task_queue, "run_task", succeed_task)

    task_queue._process_job(settings, claimed)

    [job] = list_task_jobs(conn)
    assert job.status == TASK_SUCCEEDED
    assert job.error_message is None
    assert job.finished_at is not None
