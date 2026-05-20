import re
import json
from io import BytesIO

from app.db import connect
from app.pdf_renderer import PDF_RENDERER_VERSION
from app.repositories import (
    add_task_image,
    create_task,
    create_user,
    get_task_by_id,
    update_task_image_status,
    update_task_status,
)
from app.security import hash_password
from app.storage import ensure_task_dirs, relative_to_data


def _csrf(html: str) -> str:
    return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)


def _login(client, username: str, password: str):
    page = client.get("/login")
    return client.post(
        "/login",
        data={
            "username": username,
            "password": password,
            "csrf_token": _csrf(page.text),
        },
        follow_redirects=False,
    )


def test_report_requires_task_permission(client, settings):
    conn = connect(settings.db_path)
    alice = create_user(conn, "alice", hash_password("secret123"), "user")
    create_user(conn, "bob", hash_password("secret123"), "user")
    task = create_task(conn, alice.id, "Private report", 1)
    dirs = ensure_task_dirs(settings, task.id)
    dirs.report.write_text("<html>private</html>", encoding="utf-8")
    update_task_status(
        conn,
        task.id,
        "succeeded",
        report_path=relative_to_data(settings, dirs.report),
    )
    conn.close()

    _login(client, "bob", "secret123")
    forbidden = client.get(f"/tasks/{task.id}/report.html")
    assert forbidden.status_code == 403

    client.post(
        "/logout",
        data={"csrf_token": _csrf(client.get("/tasks").text)},
        follow_redirects=False,
    )
    _login(client, "alice", "secret123")
    allowed = client.get(f"/tasks/{task.id}/report.html")
    assert allowed.status_code == 200
    assert "private" in allowed.text


def test_pdf_report_requires_task_permission(client, settings):
    conn = connect(settings.db_path)
    alice = create_user(conn, "alice", hash_password("secret123"), "user")
    create_user(conn, "bob", hash_password("secret123"), "user")
    task = create_task(conn, alice.id, "Private PDF report", 1)
    dirs = ensure_task_dirs(settings, task.id)
    dirs.report.write_text("<html>private</html>", encoding="utf-8")
    dirs.pdf_report.write_bytes(b"%PDF-1.4\nprivate\n")
    dirs.pdf_report.with_name("report.pdf.version").write_text(
        PDF_RENDERER_VERSION,
        encoding="utf-8",
    )
    update_task_status(
        conn,
        task.id,
        "succeeded",
        report_path=relative_to_data(settings, dirs.report),
    )
    conn.close()

    _login(client, "bob", "secret123")
    forbidden = client.get(f"/tasks/{task.id}/report.pdf")
    assert forbidden.status_code == 403

    client.post(
        "/logout",
        data={"csrf_token": _csrf(client.get("/tasks").text)},
        follow_redirects=False,
    )
    _login(client, "alice", "secret123")
    allowed = client.get(f"/tasks/{task.id}/report.pdf")
    assert allowed.status_code == 200
    assert allowed.headers["content-type"] == "application/pdf"
    assert allowed.content.startswith(b"%PDF-1.4")


def test_html_report_injects_pdf_download_for_existing_reports(client, settings):
    conn = connect(settings.db_path)
    alice = create_user(conn, "alice", hash_password("secret123"), "user")
    task = create_task(conn, alice.id, "Old report", 1)
    dirs = ensure_task_dirs(settings, task.id)
    dirs.report.write_text(
        '<html><body><a class="back-link" href="/tasks">返回</a></body></html>',
        encoding="utf-8",
    )
    update_task_status(
        conn,
        task.id,
        "succeeded",
        report_path=relative_to_data(settings, dirs.report),
    )
    conn.close()

    _login(client, "alice", "secret123")
    response = client.get(f"/tasks/{task.id}/report.html")

    assert response.status_code == 200
    assert f'href="/tasks/{task.id}/report.pdf">下载 PDF</a>' in response.text


def test_html_report_rerenders_existing_structured_report(client, settings):
    conn = connect(settings.db_path)
    alice = create_user(conn, "alice", hash_password("secret123"), "user")
    task = create_task(conn, alice.id, "Old structured report", 1)
    image = add_task_image(
        conn,
        task.id,
        filename="image-001.png",
        original_path=f"uploads/{task.id}/originals/image-001.png",
        sort_order=0,
    )
    dirs = ensure_task_dirs(settings, task.id)
    artifact_dir = dirs.artifacts / "image-001"
    artifact_dir.mkdir(parents=True)
    audit_path = artifact_dir / "audit.json"
    audit_path.write_text(
        json.dumps(
            {
                "screen_context": "首页",
                "overall_conclusion": "存在问题",
                "passes": [],
                "issues": [
                    {
                        "id": "color-01",
                        "severity": "中",
                        "category": "色彩",
                        "location": "主按钮",
                        "current_observation": "偏蓝",
                        "recommendation": "Change button to JM AI color token.",
                        "bbox": [1, 2, 3, 4],
                    }
                ],
                "checklist": [],
                "cannot_verify": [],
            }
        ),
        encoding="utf-8",
    )
    crop_path = artifact_dir / "issue-color-01.png"
    crop_path.write_bytes(b"png")
    dirs.report.write_text("<html><body>old report</body></html>", encoding="utf-8")
    update_task_image_status(
        conn,
        image.id,
        "succeeded",
        audit_json_path=relative_to_data(settings, audit_path),
    )
    update_task_status(
        conn,
        task.id,
        "succeeded",
        summary="审核完成",
        report_path=relative_to_data(settings, dirs.report),
    )
    conn.close()

    _login(client, "alice", "secret123")
    response = client.get(f"/tasks/{task.id}/report.html")

    assert response.status_code == 200
    assert "old report" not in response.text
    assert 'class="issue-crop-trigger"' in response.text
    assert "规范色彩令牌" in response.text


def test_task_detail_shows_selected_audit_spec(client, settings):
    conn = connect(settings.db_path)
    alice = create_user(conn, "alice", hash_password("secret123"), "user")
    task = create_task(conn, alice.id, "B-design detail", 1, audit_spec_id="b-design")
    conn.close()

    _login(client, "alice", "secret123")
    response = client.get(f"/tasks/{task.id}")

    assert response.status_code == 200
    assert "审核规范" in response.text
    assert "京东 B 端设计规范" in response.text


def test_task_detail_shows_multiple_selected_audit_specs(client, settings):
    conn = connect(settings.db_path)
    alice = create_user(conn, "alice", hash_password("secret123"), "user")
    task = create_task(
        conn,
        alice.id,
        "Multi spec detail",
        1,
        audit_spec_id=["jm-ai", "b-design"],
    )
    conn.close()

    _login(client, "alice", "secret123")
    response = client.get(f"/tasks/{task.id}")

    assert response.status_code == 200
    assert "审核规范" in response.text
    assert "JM AI 设计规范" in response.text
    assert "京东 B 端设计规范" in response.text


def test_create_task_accepts_b_design_spec_selection(client, settings):
    conn = connect(settings.db_path)
    create_user(conn, "alice", hash_password("secret123"), "user")
    conn.close()

    _login(client, "alice", "secret123")
    upload_page = client.get("/")
    response = client.post(
        "/tasks",
        data={
            "title": "B-design upload",
            "audit_spec_id": "b-design",
            "csrf_token": _csrf(upload_page.text),
        },
        files={"files": ("screen.png", BytesIO(b"png"), "image/png")},
        follow_redirects=False,
    )

    assert response.status_code == 303
    task_id = int(response.headers["location"].rsplit("/", 1)[1])
    conn = connect(settings.db_path)
    try:
        task = get_task_by_id(conn, task_id)
        assert task.audit_spec_id == "b-design"
    finally:
        conn.close()


def test_create_task_accepts_multiple_audit_specs(client, settings):
    conn = connect(settings.db_path)
    create_user(conn, "alice", hash_password("secret123"), "user")
    conn.close()

    _login(client, "alice", "secret123")
    upload_page = client.get("/")
    response = client.post(
        "/tasks",
        data={
            "title": "Multi spec upload",
            "audit_spec_ids": ["jm-ai", "b-design"],
            "csrf_token": _csrf(upload_page.text),
        },
        files={"files": ("screen.png", BytesIO(b"png"), "image/png")},
        follow_redirects=False,
    )

    assert response.status_code == 303
    task_id = int(response.headers["location"].rsplit("/", 1)[1])
    conn = connect(settings.db_path)
    try:
        task = get_task_by_id(conn, task_id)
        assert task.audit_spec_id == "jm-ai,b-design"
    finally:
        conn.close()


def test_create_task_rejects_unknown_audit_spec(client, settings):
    conn = connect(settings.db_path)
    create_user(conn, "alice", hash_password("secret123"), "user")
    conn.close()

    _login(client, "alice", "secret123")
    upload_page = client.get("/")
    response = client.post(
        "/tasks",
        data={
            "title": "Unknown spec",
            "audit_spec_id": "unknown",
            "csrf_token": _csrf(upload_page.text),
        },
        files={"files": ("screen.png", BytesIO(b"png"), "image/png")},
        follow_redirects=False,
    )

    assert response.status_code == 400
    assert "未知审核规范" in response.text


def test_artifact_path_traversal_is_rejected(client, settings):
    conn = connect(settings.db_path)
    alice = create_user(conn, "alice", hash_password("secret123"), "user")
    task = create_task(conn, alice.id, "Private report", 1)
    conn.close()
    _login(client, "alice", "secret123")

    response = client.get(f"/artifacts/{task.id}/../app.db")
    assert response.status_code in {400, 404}


def test_artifact_requires_task_permission(client, settings):
    conn = connect(settings.db_path)
    alice = create_user(conn, "alice", hash_password("secret123"), "user")
    create_user(conn, "bob", hash_password("secret123"), "user")
    task = create_task(conn, alice.id, "Private artifacts", 1)
    dirs = ensure_task_dirs(settings, task.id)
    artifact = dirs.artifacts / "image-001" / "tokens.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text('{"private": true}', encoding="utf-8")
    conn.close()

    _login(client, "bob", "secret123")
    forbidden = client.get(f"/artifacts/{task.id}/image-001/tokens.json")
    assert forbidden.status_code == 403

    client.post(
        "/logout",
        data={"csrf_token": _csrf(client.get("/tasks").text)},
        follow_redirects=False,
    )
    _login(client, "alice", "secret123")
    allowed = client.get(f"/artifacts/{task.id}/image-001/tokens.json")
    assert allowed.status_code == 200
    assert allowed.json() == {"private": True}
