from app.db import connect
from app.repositories import create_task, create_task_job, get_user_by_username


def test_healthz_reports_database_and_worker_state(client):
    response = client.get("/healthz")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["database"]["ok"] is True
    assert payload["database"]["schema_version"] >= 1
    assert "worker_started" in payload["worker"]
    assert payload["jobs"] == {
        "queued": 0,
        "running": 0,
        "succeeded": 0,
        "failed": 0,
    }


def test_healthz_reports_task_job_counts(client, settings):
    conn = connect(settings.db_path)
    try:
        user = get_user_by_username(conn, settings.initial_admin_username)
        assert user is not None
        task = create_task(conn, user.id, "Audit", 1)
        create_task_job(conn, task.id)
    finally:
        conn.close()

    response = client.get("/healthz")

    assert response.status_code == 200
    payload = response.json()
    assert payload["jobs"] == {
        "queued": 1,
        "running": 0,
        "succeeded": 0,
        "failed": 0,
    }
