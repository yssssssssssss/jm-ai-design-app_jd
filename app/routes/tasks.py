from __future__ import annotations

import json
from sqlite3 import Connection

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse

from app.db import connect
from app.main import ensure_csrf, templates
from app.models import User
from app.pdf_renderer import PdfRenderError, is_current_report_pdf, render_report_pdf
from app.report_renderer import render_report_html
from app.repositories import (
    add_task_image,
    create_task,
    get_task_by_id,
    get_user_by_id,
    list_active_tasks_for_user,
    list_task_images,
    list_tasks_for_user,
    list_unread_successful_task_ids_for_user,
    mark_successful_task_reports_read_for_user,
    mark_task_report_read,
    user_can_access_task,
)
from app.security import CsrfError, ForbiddenError, require_login, verify_csrf
from app.spec_registry import (
    DEFAULT_SPEC_ID,
    get_audit_spec,
    get_audit_specs,
    list_audit_specs,
    serialize_audit_spec_ids,
    validate_audit_spec_ids,
)
from app.storage import (
    UploadValidationError,
    ensure_task_dirs,
    relative_to_data,
    resolve_data_path,
    safe_artifact_path,
    save_upload_file,
    stored_image_name,
    validate_upload_batch,
)
from app.task_queue import enqueue_task


router = APIRouter()


def _current_user_and_conn(request: Request) -> tuple[User, Connection]:
    conn = connect(request.app.state.settings.db_path)
    try:
        user_id = request.session.get("user_id")
        user = get_user_by_id(conn, int(user_id)) if user_id else None
        return require_login(user), conn
    except Exception:
        conn.close()
        raise


def _redirect_to_login() -> RedirectResponse:
    return RedirectResponse("/login", status_code=303)


def _error_response(message: str, status_code: int = 400) -> HTMLResponse:
    return HTMLResponse(message, status_code=status_code)


def _has_history_updates(conn: Connection, user: User) -> bool:
    return bool(list_unread_successful_task_ids_for_user(conn, user))


def _validate_screen_size(
    width: str | None,
    height: str | None,
) -> tuple[int | None, int | None]:
    width_value = (width or "").strip()
    height_value = (height or "").strip()
    if not width_value and not height_value:
        return None, None
    if not width_value or not height_value:
        raise UploadValidationError("截图宽度和高度需要同时填写")
    try:
        parsed_width = int(width_value)
        parsed_height = int(height_value)
    except ValueError:
        raise UploadValidationError("截图宽度和高度必须填写整数")
    if str(parsed_width) != width_value or str(parsed_height) != height_value:
        raise UploadValidationError("截图宽度和高度必须填写整数")
    if not 1 <= parsed_width <= 20000 or not 1 <= parsed_height <= 20000:
        raise UploadValidationError("截图宽度和高度必须在 1 到 20000 px 之间")
    return parsed_width, parsed_height


def _authorized_task(request: Request, task_id: int):
    user, conn = _current_user_and_conn(request)
    try:
        task = get_task_by_id(conn, task_id)
        if task is None or not user_can_access_task(user, task):
            return None, _error_response("Forbidden", status_code=403)
        return task, None
    finally:
        conn.close()


def _authorized_report_path(request: Request, task_id: int):
    user, conn = _current_user_and_conn(request)
    try:
        task = get_task_by_id(conn, task_id)
        if task is None or not user_can_access_task(user, task):
            return None, None, None, _error_response("Forbidden", status_code=403)
        if not task.report_path:
            return user, task, None, _error_response("Report not ready", status_code=404)

        try:
            path = resolve_data_path(request.app.state.settings, task.report_path)
        except UploadValidationError:
            return user, task, None, _error_response("非法文件路径", status_code=400)
        if not path.exists() or not path.is_file():
            return user, task, path, _error_response("Report not found", status_code=404)
        return user, task, path, None
    finally:
        conn.close()


def _html_report_with_pdf_link(path, task_id: int) -> str:
    html = path.read_text(encoding="utf-8")
    pdf_href = f"/tasks/{task_id}/report.pdf"
    if pdf_href in html:
        return html

    back_link = '<a class="back-link" href="/tasks">返回</a>'
    if back_link in html:
        return html.replace(
            back_link,
            f'{back_link}\n      <a class="back-link" href="{pdf_href}">下载 PDF</a>',
            1,
        )
    return html


def _artifact_rel(path: str | None) -> str | None:
    if not path:
        return None
    normalized = path.replace("\\", "/")
    marker = "/artifacts/"
    if marker in normalized:
        return "artifacts/" + normalized.split(marker, 1)[1]
    if normalized.startswith("artifacts/"):
        return normalized
    return normalized


def _existing_artifact_rel(settings, path: str | None) -> str | None:
    if not path:
        return None
    try:
        if not resolve_data_path(settings, path).exists():
            return None
    except UploadValidationError:
        return None
    return _artifact_rel(path)


def _load_json_artifact(settings, relative_path: str | None) -> dict | None:
    if not relative_path:
        return None
    try:
        path = resolve_data_path(settings, relative_path)
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UploadValidationError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _audit_spec_label(specs) -> str:
    return "、".join(spec.label for spec in specs) if specs else get_audit_spec(None).label


def _image_artifact_dirname(sort_order: int) -> str:
    return f"image-{sort_order + 1:03d}"


def _multi_spec_artifact_path(
    task_id: int,
    sort_order: int,
    spec_id: str,
    filename: str,
) -> str:
    image_dir = _image_artifact_dirname(sort_order)
    return f"uploads/{task_id}/artifacts/{image_dir}/{spec_id}/{filename}"


def _legacy_artifact_bundle(settings, image) -> dict:
    return {
        "annotated": _artifact_rel(image.annotated_path),
        "issue_crops": _issue_crop_paths(settings, image.audit_json_path),
        "tokens": _artifact_rel(image.tokens_path),
        "measurements": _artifact_rel(image.measurements_path),
        "issues": _artifact_rel(image.issues_path),
        "audit_json": _artifact_rel(image.audit_json_path),
    }


def _multi_spec_artifact_bundle(
    settings,
    task_id: int,
    sort_order: int,
    spec_id: str,
) -> dict:
    return {
        "annotated": _existing_artifact_rel(
            settings,
            _multi_spec_artifact_path(task_id, sort_order, spec_id, "annotated.png"),
        ),
        "issue_crops": _issue_crop_paths(
            settings,
            _multi_spec_artifact_path(task_id, sort_order, spec_id, "audit.json"),
        ),
        "tokens": _artifact_rel(
            _multi_spec_artifact_path(task_id, sort_order, spec_id, "tokens.json")
        ),
        "measurements": _artifact_rel(
            _multi_spec_artifact_path(task_id, sort_order, spec_id, "measurements.json")
        ),
        "issues": _artifact_rel(
            _multi_spec_artifact_path(task_id, sort_order, spec_id, "issues.json")
        ),
        "audit_json": _artifact_rel(
            _multi_spec_artifact_path(task_id, sort_order, spec_id, "audit.json")
        ),
    }


def _current_report_html(request: Request, task, stored_path) -> str:
    conn = connect(request.app.state.settings.db_path)
    try:
        images = list_task_images(conn, task.id)
    finally:
        conn.close()

    audit_specs = get_audit_specs(task.audit_spec_id)
    image_results = []
    for image in images:
        if len(audit_specs) == 1:
            audit = _load_json_artifact(request.app.state.settings, image.audit_json_path)
            if not audit:
                continue
            image_results.append(
                {
                    "filename": image.filename,
                    "audit_spec_label": audit_specs[0].label,
                    "spec_asset_index_path": audit_specs[0].asset_index_path,
                    "audit": audit,
                    "artifacts": _legacy_artifact_bundle(request.app.state.settings, image),
                }
            )
            continue
        for spec in audit_specs:
            audit_path = _multi_spec_artifact_path(task.id, image.sort_order, spec.id, "audit.json")
            audit = _load_json_artifact(request.app.state.settings, audit_path)
            if not audit:
                continue
            image_results.append(
                {
                    "filename": image.filename,
                    "audit_spec_label": spec.label,
                    "spec_asset_index_path": spec.asset_index_path,
                    "audit": audit,
                    "artifacts": _multi_spec_artifact_bundle(
                        request.app.state.settings,
                        task.id,
                        image.sort_order,
                        spec.id,
                    ),
                }
            )

    if not image_results:
        return _html_report_with_pdf_link(stored_path, task.id)

    html = render_report_html(
        {
            "title": task.title,
            "summary": task.summary,
            "audit_spec_label": _audit_spec_label(audit_specs),
            "screen_width_px": task.screen_width_px,
            "screen_height_px": task.screen_height_px,
        },
        image_results,
        task_id=task.id,
    )
    if stored_path.read_text(encoding="utf-8") != html:
        stored_path.write_text(html, encoding="utf-8")
    return html


def _issue_crop_paths(settings, anchor_path: str | None) -> list[str]:
    if not anchor_path:
        return []
    try:
        path = resolve_data_path(settings, anchor_path).parent
    except UploadValidationError:
        return []
    if not path.exists() or not path.is_dir():
        return []
    root = settings.data_dir.resolve()
    paths = []
    for candidate in sorted(path.glob("issue-*.png")):
        if not candidate.is_file():
            continue
        resolved = candidate.resolve()
        if root not in resolved.parents and resolved != root:
            continue
        paths.append(resolved.relative_to(root).as_posix())
    return paths


@router.get("/", response_class=HTMLResponse)
def upload_page(request: Request):
    try:
        user, conn = _current_user_and_conn(request)
    except (ForbiddenError, TypeError, ValueError):
        return _redirect_to_login()
    try:
        return templates.TemplateResponse(
            request,
            "upload.html",
            {
                "user": user,
                "csrf_token": ensure_csrf(request),
                "audit_specs": list_audit_specs(),
                "selected_audit_spec_ids": [],
                "error": None,
                "title": "新建任务",
                "nav_active": "new",
                "hide_page_title": True,
                "has_history_updates": _has_history_updates(conn, user),
            },
        )
    finally:
        conn.close()


@router.post("/tasks")
async def create_task_route(
    request: Request,
    title: str = Form(...),
    csrf_token: str = Form(...),
    audit_spec_ids: list[str] | None = Form(None),
    audit_spec_id: str | None = Form(None),
    screen_width_px: str | None = Form(None),
    screen_height_px: str | None = Form(None),
    files: list[UploadFile] = File(...),
):
    try:
        user, conn = _current_user_and_conn(request)
    except (ForbiddenError, TypeError, ValueError):
        return _error_response("Login required", status_code=403)

    try:
        try:
            verify_csrf(request.session, csrf_token)
            if not audit_spec_ids and not audit_spec_id:
                raise UploadValidationError("请选择至少一个审核规范")
            selected_audit_spec_ids = validate_audit_spec_ids(
                audit_spec_ids or audit_spec_id
            )
            stored_audit_spec_id = serialize_audit_spec_ids(selected_audit_spec_ids)
            validate_upload_batch(request.app.state.settings, files)
            screen_width_px, screen_height_px = _validate_screen_size(
                screen_width_px,
                screen_height_px,
            )
        except CsrfError:
            return _error_response("Invalid CSRF token")
        except ValueError:
            return _error_response("未知审核规范")
        except UploadValidationError as exc:
            return _error_response(str(exc))

        clean_title = title.strip() or "未命名审核任务"
        task = create_task(
            conn,
            owner_id=user.id,
            title=clean_title,
            image_count=len(files),
            audit_spec_id=stored_audit_spec_id,
            screen_width_px=screen_width_px,
            screen_height_px=screen_height_px,
        )
        dirs = ensure_task_dirs(request.app.state.settings, task.id)

        for index, upload in enumerate(files):
            filename = stored_image_name(index, upload.filename or "")
            output_path = dirs.originals / filename
            save_upload_file(request.app.state.settings, upload.file, output_path)
            add_task_image(
                conn,
                task_id=task.id,
                filename=filename,
                original_path=relative_to_data(request.app.state.settings, output_path),
                sort_order=index,
            )
        if request.app.state.settings.enqueue_background_tasks:
            enqueue_task(request.app.state.settings, task.id)
    except UploadValidationError as exc:
        return _error_response(str(exc))
    finally:
        conn.close()

    return RedirectResponse(f"/tasks/{task.id}", status_code=303)


@router.get("/tasks", response_class=HTMLResponse)
def task_list(request: Request):
    try:
        user, conn = _current_user_and_conn(request)
    except (ForbiddenError, TypeError, ValueError):
        return _redirect_to_login()
    try:
        mark_successful_task_reports_read_for_user(conn, user)
        return templates.TemplateResponse(
            request,
            "tasks.html",
            {
                "user": user,
                "csrf_token": ensure_csrf(request),
                "tasks": list_tasks_for_user(conn, user),
                "unread_task_ids": set(),
                "has_history_updates": False,
                "title": "历史任务",
                "nav_active": "history",
                "task_mode": "history",
            },
        )
    finally:
        conn.close()


@router.get("/tasks/running", response_class=HTMLResponse)
def running_task_list(request: Request):
    try:
        user, conn = _current_user_and_conn(request)
    except (ForbiddenError, TypeError, ValueError):
        return _redirect_to_login()
    try:
        return templates.TemplateResponse(
            request,
            "tasks.html",
            {
                "user": user,
                "csrf_token": ensure_csrf(request),
                "tasks": list_active_tasks_for_user(conn, user),
                "unread_task_ids": set(),
                "has_history_updates": _has_history_updates(conn, user),
                "title": "正在进行",
                "nav_active": "running",
                "task_mode": "running",
            },
        )
    finally:
        conn.close()


@router.get("/tasks/{task_id}/report.html")
def report_html(request: Request, task_id: int):
    try:
        user, task, path, error = _authorized_report_path(request, task_id)
    except (ForbiddenError, TypeError, ValueError):
        return _error_response("Login required", status_code=401)
    if error:
        return error
    conn = connect(request.app.state.settings.db_path)
    try:
        mark_task_report_read(conn, user.id, task.id)
    finally:
        conn.close()
    return HTMLResponse(_current_report_html(request, task, path))


@router.get("/tasks/{task_id}/report.pdf")
def report_pdf(request: Request, task_id: int):
    try:
        user, task, html_path, error = _authorized_report_path(request, task_id)
    except (ForbiddenError, TypeError, ValueError):
        return _error_response("Login required", status_code=401)
    if error:
        return error

    dirs = ensure_task_dirs(request.app.state.settings, task.id)
    _current_report_html(request, task, html_path)
    pdf_is_stale = (
        dirs.pdf_report.exists()
        and html_path.exists()
        and dirs.pdf_report.stat().st_mtime < html_path.stat().st_mtime
    )
    if pdf_is_stale or not is_current_report_pdf(dirs.pdf_report):
        try:
            render_report_pdf(request.app.state.settings, task.id, html_path, dirs.pdf_report)
        except PdfRenderError as exc:
            return _error_response(f"PDF 生成失败：{exc}", status_code=503)

    conn = connect(request.app.state.settings.db_path)
    try:
        mark_task_report_read(conn, user.id, task.id)
    finally:
        conn.close()
    return FileResponse(
        dirs.pdf_report,
        media_type="application/pdf",
        filename=f"task-{task.id}-report.pdf",
    )


@router.get("/tasks/{task_id}", response_class=HTMLResponse)
def task_detail(request: Request, task_id: int):
    try:
        user, conn = _current_user_and_conn(request)
    except (ForbiddenError, TypeError, ValueError):
        return _redirect_to_login()
    try:
        task = get_task_by_id(conn, task_id)
        if task is None or not user_can_access_task(user, task):
            return _error_response("Forbidden", status_code=403)
        audit_specs = get_audit_specs(task.audit_spec_id)
        return templates.TemplateResponse(
            request,
            "task_detail.html",
            {
                "user": user,
                "csrf_token": ensure_csrf(request),
                "task": task,
                "audit_specs": audit_specs,
                "images": list_task_images(conn, task.id),
                "title": task.title,
                "nav_active": "running"
                if task.status in {"queued", "running"}
                else "history",
                "has_history_updates": _has_history_updates(conn, user),
            },
        )
    finally:
        conn.close()


@router.get("/artifacts/{task_id}/{artifact_path:path}")
def artifact_file(request: Request, task_id: int, artifact_path: str):
    try:
        _, error = _authorized_task(request, task_id)
    except (ForbiddenError, TypeError, ValueError):
        return _error_response("Login required", status_code=401)
    if error:
        return error

    dirs = ensure_task_dirs(request.app.state.settings, task_id)
    try:
        path = safe_artifact_path(dirs, artifact_path)
    except UploadValidationError:
        return _error_response("非法文件路径", status_code=400)
    if not path.exists() or not path.is_file():
        return _error_response("Not found", status_code=404)
    return FileResponse(path)


@router.get("/artifacts/{artifact_path:path}")
def malformed_artifact_file(artifact_path: str):
    return _error_response("Not found", status_code=404)


@router.get("/tasks/{task_id}/status")
def task_status(request: Request, task_id: int):
    try:
        user, conn = _current_user_and_conn(request)
    except (ForbiddenError, TypeError, ValueError):
        return JSONResponse({"error": "login required"}, status_code=401)
    try:
        task = get_task_by_id(conn, task_id)
        if task is None or not user_can_access_task(user, task):
            return JSONResponse({"error": "forbidden"}, status_code=403)
        images = list_task_images(conn, task.id)
        return {
            "id": task.id,
            "status": task.status,
            "summary": task.summary,
            "error_message": task.error_message,
            "images": [
                {
                    "id": image.id,
                    "filename": image.filename,
                    "status": image.status,
                    "error_message": image.error_message,
                }
                for image in images
            ],
        }
    finally:
        conn.close()
