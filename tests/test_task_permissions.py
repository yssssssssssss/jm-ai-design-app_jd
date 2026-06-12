import logging
import re
from dataclasses import replace

from PIL import Image

from app.db import connect
from app.main import create_app
from app.repositories import (
    create_task,
    get_task_by_id,
    get_user_by_username,
    list_task_jobs,
    list_tasks_for_user,
    update_task_status,
)
from app.storage import ensure_task_dirs, relative_to_data


def _csrf(html: str) -> str:
    return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)


def _register(client, username: str):
    page = client.get("/register")
    client.post(
        "/register",
        data={
            "username": username,
            "password": "secret123",
            "invite_code": "invite-123",
            "csrf_token": _csrf(page.text),
        },
        follow_redirects=False,
    )


def _png_bytes(tmp_path, name: str):
    path = tmp_path / name
    Image.new("RGB", (16, 16), color=(107, 54, 250)).save(path)
    return path.read_bytes()


def _current_user(settings, username: str):
    conn = connect(settings.db_path)
    try:
        user = get_user_by_username(conn, username)
        assert user is not None
        return user
    finally:
        conn.close()


def _make_task(settings, user, title: str, status: str, report: bool = False):
    conn = connect(settings.db_path)
    try:
        task = create_task(conn, user.id, title, 1)
        if status != "queued":
            report_path = None
            if report:
                dirs = ensure_task_dirs(settings, task.id)
                dirs.report.write_text(f"<html>{title}</html>", encoding="utf-8")
                report_path = relative_to_data(settings, dirs.report)
            update_task_status(conn, task.id, status, report_path=report_path)
        return task
    finally:
        conn.close()


def _uploads_dir_empty(settings) -> bool:
    return not settings.uploads_dir.exists() or not any(settings.uploads_dir.iterdir())


def test_upload_creates_task_and_lists_only_owner_tasks(client, tmp_path):
    _register(client, "alice")
    page = client.get("/")
    response = client.post(
        "/tasks",
        data={
            "title": "Alice audit",
            "audit_spec_ids": "jm-ai",
            "csrf_token": _csrf(page.text),
        },
        files=[
            ("files", ("a.png", _png_bytes(tmp_path, "a.png"), "image/png")),
            ("files", ("b.png", _png_bytes(tmp_path, "b.png"), "image/png")),
        ],
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].startswith("/tasks/")

    tasks_page = client.get("/tasks/running")
    assert "Alice audit" in tasks_page.text

    client.post(
        "/logout",
        data={"csrf_token": _csrf(client.get("/tasks").text)},
        follow_redirects=False,
    )
    _register(client, "bob")
    bob_tasks = client.get("/tasks/running")
    assert "Alice audit" not in bob_tasks.text


def test_upload_page_hides_declared_screen_size_inputs(client):
    _register(client, "alice")

    page = client.get("/")

    assert page.status_code == 200
    assert "screen_width_px" not in page.text
    assert "screen_height_px" not in page.text
    assert "稿件尺寸" not in page.text


def test_upload_page_uses_checkbox_audit_spec_selection(client):
    _register(client, "alice")

    page = client.get("/")

    assert page.status_code == 200
    assert "<select" not in page.text
    assert 'type="radio"' not in page.text
    assert 'type="checkbox"' in page.text
    assert 'name="audit_spec_ids"' in page.text
    assert "checked" not in page.text
    assert "JM AI 设计规范" in page.text
    assert "京东 B 端设计规范" in page.text
    assert "导航类-底部导航栏规范" in page.text


def test_upload_page_exposes_submit_state_targets(client):
    _register(client, "alice")

    page = client.get("/")

    assert page.status_code == 200
    assert 'id="audit-composer"' in page.text
    assert 'id="submit-task-button"' in page.text
    assert 'data-pending-text="提交中..."' in page.text


def test_upload_page_exposes_client_validation_targets(client):
    _register(client, "alice")

    page = client.get("/")

    assert page.status_code == 200
    assert 'id="upload-client-error"' in page.text
    assert 'role="alert"' in page.text
    assert 'hidden' in page.text
    assert "novalidate" in page.text
    assert 'data-message-no-spec="请选择至少一个审核规范"' in page.text
    assert 'data-message-no-file="请至少上传 1 张图片"' in page.text
    assert 'data-max-upload-files="8"' in page.text
    assert 'data-max-upload-mb-per-file="10"' in page.text
    assert 'data-message-too-many-files="最多上传 8 张图片"' in page.text
    assert 'data-message-bad-file="仅支持 PNG/JPG/JPEG/WEBP 图片"' in page.text
    assert 'data-message-too-large-file="单张图片不能超过 10MB"' in page.text


def test_upload_missing_spec_preserves_form_and_shows_field_error(client, tmp_path):
    _register(client, "alice")
    page = client.get("/")

    response = client.post(
        "/tasks",
        data={
            "title": "Keep this title",
            "csrf_token": _csrf(page.text),
        },
        files=[("files", ("a.png", _png_bytes(tmp_path, "a.png"), "image/png"))],
    )

    assert response.status_code == 400
    assert 'value="Keep this title"' in response.text
    assert 'data-field-error="audit_spec_ids"' in response.text
    assert "请选择至少一个审核规范" in response.text
    assert "checked" not in response.text


def test_upload_screen_size_error_preserves_fields_and_spec_selection(client, tmp_path):
    _register(client, "alice")
    page = client.get("/")

    response = client.post(
        "/tasks",
        data={
            "title": "Bad size",
            "screen_width_px": "1440",
            "screen_height_px": "",
            "audit_spec_ids": "b-design",
            "csrf_token": _csrf(page.text),
        },
        files=[("files", ("a.png", _png_bytes(tmp_path, "a.png"), "image/png"))],
    )

    assert response.status_code == 400
    assert 'value="Bad size"' in response.text
    assert 'name="screen_width_px" value="1440"' in response.text
    assert 'name="screen_height_px" value=""' in response.text
    assert 'value="b-design"\n              checked' in response.text
    assert 'data-field-error="screen_size"' in response.text
    assert "截图宽度和高度需要同时填写" in response.text


def test_upload_file_error_preserves_form_and_shows_file_error(client):
    _register(client, "alice")
    page = client.get("/")

    response = client.post(
        "/tasks",
        data={
            "title": "Bad file",
            "audit_spec_ids": "jm-ai",
            "csrf_token": _csrf(page.text),
        },
        files=[("files", ("a.txt", b"text", "text/plain"))],
    )

    assert response.status_code == 400
    assert 'value="Bad file"' in response.text
    assert 'value="jm-ai"\n              checked' in response.text
    assert 'data-field-error="files"' in response.text
    assert "仅支持 PNG/JPG/JPEG/WEBP 图片" in response.text


def test_upload_persists_declared_screen_size(client, settings, tmp_path):
    _register(client, "alice")
    page = client.get("/")
    response = client.post(
        "/tasks",
        data={
            "title": "Desktop audit",
            "screen_width_px": "1440",
            "screen_height_px": "900",
            "audit_spec_ids": "jm-ai",
            "csrf_token": _csrf(page.text),
        },
        files=[("files", ("a.png", _png_bytes(tmp_path, "a.png"), "image/png"))],
        follow_redirects=False,
    )

    assert response.status_code == 303
    task_id = int(response.headers["location"].rsplit("/", 1)[1])
    conn = connect(settings.db_path)
    try:
        task = get_task_by_id(conn, task_id)
    finally:
        conn.close()

    assert task is not None
    assert task.screen_width_px == 1440
    assert task.screen_height_px == 900


def test_upload_enqueues_task_without_running_audit(monkeypatch, settings, tmp_path):
    settings = replace(settings, enqueue_background_tasks=True)
    app = create_app(settings)
    calls = []
    monkeypatch.setattr(
        "app.routes.tasks.start_worker",
        lambda queued_settings: calls.append(queued_settings),
    )

    from fastapi.testclient import TestClient

    with TestClient(app) as local_client:
        _register(local_client, "alice")
        page = local_client.get("/")
        response = local_client.post(
            "/tasks",
            data={
                "title": "Queued audit",
                "audit_spec_ids": "jm-ai",
                "csrf_token": _csrf(page.text),
            },
            files=[("files", ("a.png", _png_bytes(tmp_path, "a.png"), "image/png"))],
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert len(calls) == 1
    task_id = int(response.headers["location"].rsplit("/", 1)[1])
    assert calls[0] == settings
    conn = connect(settings.db_path)
    try:
        task = get_task_by_id(conn, task_id)
        jobs = list_task_jobs(conn)
    finally:
        conn.close()
    assert task is not None
    assert task.status == "queued"
    assert [job.task_id for job in jobs] == [task_id]


def test_upload_job_insert_failure_cleans_task_and_files(
    monkeypatch, settings, tmp_path
):
    settings = replace(settings, enqueue_background_tasks=True)
    app = create_app(settings)
    monkeypatch.setattr(
        "app.routes.tasks.create_task_job",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("queue failed")),
    )

    from fastapi.testclient import TestClient

    with TestClient(app) as local_client:
        _register(local_client, "alice")
        page = local_client.get("/")
        response = local_client.post(
            "/tasks",
            data={
                "title": "Queue broken",
                "audit_spec_ids": "jm-ai",
                "csrf_token": _csrf(page.text),
            },
            files=[("files", ("a.png", _png_bytes(tmp_path, "a.png"), "image/png"))],
        )

    user = _current_user(settings, "alice")
    conn = connect(settings.db_path)
    try:
        tasks = list_tasks_for_user(conn, user)
        jobs = list_task_jobs(conn)
    finally:
        conn.close()

    assert response.status_code == 400
    assert "上传失败" in response.text
    assert tasks == []
    assert jobs == []
    assert _uploads_dir_empty(settings)


def test_upload_worker_start_failure_keeps_persisted_job(
    monkeypatch, caplog, settings, tmp_path
):
    settings = replace(settings, enqueue_background_tasks=True)
    app = create_app(settings)
    monkeypatch.setattr(
        "app.routes.tasks.start_worker",
        lambda queued_settings: (_ for _ in ()).throw(RuntimeError("worker down")),
    )

    from fastapi.testclient import TestClient

    with caplog.at_level(logging.ERROR, logger="app.routes.tasks"):
        with TestClient(app) as local_client:
            _register(local_client, "alice")
            page = local_client.get("/")
            response = local_client.post(
                "/tasks",
                data={
                    "title": "Worker delayed",
                    "audit_spec_ids": "jm-ai",
                    "csrf_token": _csrf(page.text),
                },
                files=[("files", ("a.png", _png_bytes(tmp_path, "a.png"), "image/png"))],
                follow_redirects=False,
            )

    assert response.status_code == 303
    task_id = int(response.headers["location"].rsplit("/", 1)[1])
    conn = connect(settings.db_path)
    try:
        task = get_task_by_id(conn, task_id)
        jobs = list_task_jobs(conn)
    finally:
        conn.close()
    assert task is not None
    assert task.status == "queued"
    assert [job.task_id for job in jobs] == [task_id]
    assert f"task_id={task_id}" in caplog.text


def test_upload_save_failure_leaves_no_task_or_upload_files(
    monkeypatch, client, settings, tmp_path
):
    _register(client, "alice")
    page = client.get("/")
    calls = 0

    def fail_on_second_file(current_settings, file_obj, output_path):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("disk full")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"partial")

    monkeypatch.setattr("app.routes.tasks.save_upload_file", fail_on_second_file)

    response = client.post(
        "/tasks",
        data={
            "title": "Broken audit",
            "audit_spec_ids": "jm-ai",
            "csrf_token": _csrf(page.text),
        },
        files=[
            ("files", ("a.png", _png_bytes(tmp_path, "a.png"), "image/png")),
            ("files", ("b.png", _png_bytes(tmp_path, "b.png"), "image/png")),
        ],
    )

    user = _current_user(settings, "alice")
    conn = connect(settings.db_path)
    try:
        tasks = list_tasks_for_user(conn, user)
    finally:
        conn.close()

    assert response.status_code == 400
    assert "上传失败" in response.text
    assert tasks == []
    assert _uploads_dir_empty(settings)


def test_upload_image_insert_failure_cleans_task_and_files(
    monkeypatch, client, settings, tmp_path
):
    _register(client, "alice")
    page = client.get("/")
    calls = 0

    def fail_on_second_image(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("db write failed")
        return original_add_task_image(*args, **kwargs)

    from app.routes import tasks as task_routes

    original_add_task_image = task_routes.add_task_image
    monkeypatch.setattr("app.routes.tasks.add_task_image", fail_on_second_image)

    response = client.post(
        "/tasks",
        data={
            "title": "Broken audit",
            "audit_spec_ids": "jm-ai",
            "csrf_token": _csrf(page.text),
        },
        files=[
            ("files", ("a.png", _png_bytes(tmp_path, "a.png"), "image/png")),
            ("files", ("b.png", _png_bytes(tmp_path, "b.png"), "image/png")),
        ],
    )

    user = _current_user(settings, "alice")
    conn = connect(settings.db_path)
    try:
        tasks = list_tasks_for_user(conn, user)
    finally:
        conn.close()

    assert response.status_code == 400
    assert "上传失败" in response.text
    assert tasks == []
    assert _uploads_dir_empty(settings)


def test_upload_rejects_partial_or_non_integer_screen_size(client, tmp_path):
    _register(client, "alice")
    page = client.get("/")
    partial = client.post(
        "/tasks",
        data={
            "title": "Bad audit",
            "screen_width_px": "1440",
            "screen_height_px": "",
            "audit_spec_ids": "jm-ai",
            "csrf_token": _csrf(page.text),
        },
        files=[("files", ("a.png", _png_bytes(tmp_path, "a.png"), "image/png"))],
    )
    decimal = client.post(
        "/tasks",
        data={
            "title": "Bad audit",
            "screen_width_px": "1440.5",
            "screen_height_px": "900",
            "audit_spec_ids": "jm-ai",
            "csrf_token": _csrf(page.text),
        },
        files=[("files", ("b.png", _png_bytes(tmp_path, "b.png"), "image/png"))],
    )

    assert partial.status_code == 400
    assert "截图宽度和高度需要同时填写" in partial.text
    assert decimal.status_code == 400
    assert "截图宽度和高度必须填写整数" in decimal.text


def test_task_navigation_shows_active_view_and_full_history(client, settings):
    _register(client, "alice")
    alice = _current_user(settings, "alice")
    _make_task(settings, alice, "Queued audit", "queued")
    _make_task(settings, alice, "Running audit", "running")
    _make_task(settings, alice, "Failed audit", "failed")
    _make_task(settings, alice, "Successful audit", "succeeded", report=True)

    history = client.get("/tasks")
    assert history.status_code == 200
    assert "历史任务" in history.text
    assert "Successful audit" in history.text
    assert "Queued audit" in history.text
    assert "Running audit" in history.text
    assert "Failed audit" in history.text
    assert 'class="section-heading"' not in history.text

    running = client.get("/tasks/running")
    assert running.status_code == 200
    assert "正在进行" in running.text
    assert "Queued audit" in running.text
    assert "Running audit" in running.text
    assert "Successful audit" not in running.text
    assert "Failed audit" not in running.text


def test_history_task_list_is_limited_to_recent_tasks(client, settings):
    _register(client, "alice")
    alice = _current_user(settings, "alice")
    for index in range(105):
        _make_task(settings, alice, f"History audit {index:03d}", "succeeded")

    history = client.get("/tasks")

    assert history.status_code == 200
    assert history.text.count('class="task-row"') == 100
    assert "仅显示最近 100 条历史任务" in history.text


def test_running_task_list_exposes_update_targets(client, settings):
    _register(client, "alice")
    alice = _current_user(settings, "alice")
    task = _make_task(settings, alice, "Queued audit", "queued")

    response = client.get("/tasks/running")

    assert response.status_code == 200
    assert 'data-task-list="running"' in response.text
    assert f'data-task-row="{task.id}"' in response.text
    assert f'data-task-status="{task.id}"' in response.text
    assert ">排队中</span>" in response.text
    assert "/static/app.js?v=" in response.text


def test_running_task_status_returns_visible_active_tasks(client, settings):
    _register(client, "alice")
    alice = _current_user(settings, "alice")
    queued = _make_task(settings, alice, "Queued audit", "queued")
    running = _make_task(settings, alice, "Running audit", "running")
    _make_task(settings, alice, "Done audit", "succeeded", report=True)

    response = client.get("/tasks/running/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "tasks": [
            {"id": running.id, "status": "running", "status_label": "审核中"},
            {"id": queued.id, "status": "queued", "status_label": "排队中"},
        ]
    }


def test_running_task_status_requires_task_permission(client, settings):
    _register(client, "alice")
    alice = _current_user(settings, "alice")
    _make_task(settings, alice, "Alice audit", "queued")
    client.post(
        "/logout",
        data={"csrf_token": _csrf(client.get("/tasks").text)},
        follow_redirects=False,
    )
    _register(client, "bob")

    response = client.get("/tasks/running/status")

    assert response.status_code == 200
    assert response.json() == {"tasks": []}


def test_history_tab_shows_dot_for_new_completed_task_until_history_is_opened(
    client, settings
):
    _register(client, "alice")
    alice = _current_user(settings, "alice")
    _make_task(settings, alice, "Unread report", "succeeded", report=True)

    running = client.get("/tasks/running")
    assert '<span class="nav-dot"' in running.text

    history = client.get("/tasks")
    assert '<span class="nav-dot"' not in history.text

    running_after_read = client.get("/tasks/running")
    assert '<span class="nav-dot"' not in running_after_read.text


def test_normal_user_cannot_open_other_user_task(client, tmp_path):
    _register(client, "alice")
    page = client.get("/")
    response = client.post(
        "/tasks",
        data={
            "title": "Alice private",
            "audit_spec_ids": "jm-ai",
            "csrf_token": _csrf(page.text),
        },
        files=[("files", ("a.png", _png_bytes(tmp_path, "a.png"), "image/png"))],
        follow_redirects=False,
    )
    task_url = response.headers["location"]
    client.post(
        "/logout",
        data={"csrf_token": _csrf(client.get("/tasks").text)},
        follow_redirects=False,
    )

    _register(client, "bob")
    forbidden = client.get(task_url)

    assert forbidden.status_code == 403
