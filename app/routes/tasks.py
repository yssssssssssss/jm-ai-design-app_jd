from __future__ import annotations

import logging
from sqlite3 import Connection

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse

from app.db import connect
from app.main import ensure_csrf, templates
from app.models import User
from app.pdf_renderer import PdfRenderError, is_current_report_pdf, render_report_pdf
from app.repositories import (
    add_task_image,
    create_task,
    create_task_job,
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
from app.security import CsrfError, ForbiddenError, new_csrf_token, require_login, verify_csrf
from app.spec_registry import get_audit_specs, list_audit_specs
from app.storage import (
    UploadValidationError,
    ensure_task_dirs,
    relative_to_data,
    remove_tree,
    resolve_data_path,
    safe_artifact_path,
    save_upload_file,
    stored_image_name,
    task_root,
)
from app.task_reports import current_report_html
from app.task_presenters import (
    running_task_payload,
    task_back_link,
    task_failure_actions,
    task_status_payload,
)
from app.task_queue import start_worker
from app.upload_validation import validate_upload_form


router = APIRouter()
logger = logging.getLogger(__name__)
HISTORY_TASK_LIMIT = 100


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


def _selected_audit_spec_ids(
    audit_spec_ids: list[str] | None,
    audit_spec_id: str | None,
) -> list[str]:
    raw_values = audit_spec_ids or ([audit_spec_id] if audit_spec_id else [])
    selected = []
    for raw in raw_values:
        for part in str(raw or "").split(","):
            spec_id = part.strip()
            if spec_id and spec_id not in selected:
                selected.append(spec_id)
    return selected


def _upload_error_field(message: str) -> str:
    if message in {"请选择至少一个审核规范", "未知审核规范"}:
        return "audit_spec_ids"
    if message.startswith("截图宽度和高度") or "px" in message:
        return "screen_size"
    if "上传" in message or "图片" in message:
        return "files"
    return "form"


def _upload_form_response(
    request: Request,
    conn: Connection,
    user: User,
    *,
    title: str,
    audit_spec_ids: list[str] | None,
    audit_spec_id: str | None,
    screen_width_px: str | None,
    screen_height_px: str | None,
    error: str,
) -> HTMLResponse:
    field = _upload_error_field(error)
    field_errors = {field: error} if field != "form" else {}
    return templates.TemplateResponse(
        request,
        "upload.html",
        {
            "user": user,
            "csrf_token": ensure_csrf(request),
            "audit_specs": list_audit_specs(),
            "selected_audit_spec_ids": _selected_audit_spec_ids(
                audit_spec_ids,
                audit_spec_id,
            ),
            "max_upload_files": request.app.state.settings.max_upload_files,
            "max_upload_mb_per_file": request.app.state.settings.max_upload_mb_per_file,
            "error": error if field == "form" else None,
            "field_errors": field_errors,
            "form_title": title,
            "form_screen_width_px": screen_width_px or "",
            "form_screen_height_px": screen_height_px or "",
            "title": "新建任务",
            "nav_active": "new",
            "hide_page_title": True,
            "has_history_updates": _has_history_updates(conn, user),
        },
        status_code=400,
    )


def _authorized_task(request: Request, task_id: int):
    user, conn = _current_user_and_conn(request)
    try:
        task = get_task_by_id(conn, task_id)
        if task is None or not user_can_access_task(user, task):
            return None, _error_response("Forbidden", status_code=403)
        return task, None
    finally:
        conn.close()


def _report_context(request: Request, task_id: int, *, mark_read: bool = False):
    user, conn = _current_user_and_conn(request)
    try:
        task = get_task_by_id(conn, task_id)
        if task is None or not user_can_access_task(user, task):
            return None, None, None, None, _error_response("Forbidden", status_code=403)
        if not task.report_path:
            return user, task, None, None, _error_response(
                "Report not ready", status_code=404
            )

        try:
            path = resolve_data_path(request.app.state.settings, task.report_path)
        except UploadValidationError:
            return user, task, None, None, _error_response("非法文件路径", status_code=400)
        if not path.exists() or not path.is_file():
            return user, task, path, None, _error_response(
                "Report not found", status_code=404
            )
        images = list_task_images(conn, task.id)
        if mark_read:
            mark_task_report_read(conn, user.id, task.id)
        return user, task, path, images, None
    finally:
        conn.close()


def _temp_upload_dir(settings, user_id: int) -> Path:
    return settings.data_dir / "_tmp_uploads" / f"user-{user_id}-{new_csrf_token()}"


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
                "max_upload_files": request.app.state.settings.max_upload_files,
                "max_upload_mb_per_file": request.app.state.settings.max_upload_mb_per_file,
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

    temp_dir = None
    task_id_for_cleanup = None
    try:
        try:
            verify_csrf(request.session, csrf_token)
            upload_form = validate_upload_form(
                settings=request.app.state.settings,
                title=title,
                audit_spec_ids=audit_spec_ids,
                audit_spec_id=audit_spec_id,
                screen_width_px=screen_width_px,
                screen_height_px=screen_height_px,
                files=files,
            )
        except CsrfError:
            return _error_response("Invalid CSRF token")
        except UploadValidationError as exc:
            return _upload_form_response(
                request,
                conn,
                user,
                title=title,
                audit_spec_ids=audit_spec_ids,
                audit_spec_id=audit_spec_id,
                screen_width_px=screen_width_px,
                screen_height_px=screen_height_px,
                error=str(exc),
            )

        temp_dir = _temp_upload_dir(request.app.state.settings, user.id)
        temp_dir.mkdir(parents=True, exist_ok=False)
        saved_uploads = []
        for index, upload in enumerate(files):
            filename = stored_image_name(index, upload.filename or "")
            temp_path = temp_dir / filename
            save_upload_file(request.app.state.settings, upload.file, temp_path)
            saved_uploads.append((filename, temp_path))

        conn.execute("begin immediate")
        try:
            task = create_task(
                conn,
                owner_id=user.id,
                title=upload_form.title,
                image_count=len(files),
                audit_spec_id=upload_form.stored_audit_spec_id,
                screen_width_px=upload_form.screen_width_px,
                screen_height_px=upload_form.screen_height_px,
                commit=False,
            )
            task_id_for_cleanup = task.id
            dirs = ensure_task_dirs(request.app.state.settings, task.id)
            for index, (filename, temp_path) in enumerate(saved_uploads):
                output_path = dirs.originals / filename
                temp_path.replace(output_path)
                add_task_image(
                    conn,
                    task_id=task.id,
                    filename=filename,
                    original_path=relative_to_data(request.app.state.settings, output_path),
                    sort_order=index,
                    commit=False,
                )
            if request.app.state.settings.enqueue_background_tasks:
                create_task_job(conn, task.id, commit=False)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            if temp_dir:
                remove_tree(temp_dir)
        if request.app.state.settings.enqueue_background_tasks:
            try:
                start_worker(request.app.state.settings)
            except Exception:
                logger.exception("Failed to start audit task worker for task_id=%s", task.id)
    except UploadValidationError as exc:
        if temp_dir:
            remove_tree(temp_dir)
        if task_id_for_cleanup:
            remove_tree(task_root(request.app.state.settings, task_id_for_cleanup))
        return _error_response(str(exc))
    except Exception:
        if temp_dir:
            remove_tree(temp_dir)
        if task_id_for_cleanup:
            remove_tree(task_root(request.app.state.settings, task_id_for_cleanup))
        return _error_response("上传失败，请重试")
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
        tasks = list_tasks_for_user(conn, user, limit=HISTORY_TASK_LIMIT + 1)
        has_more_tasks = len(tasks) > HISTORY_TASK_LIMIT
        return templates.TemplateResponse(
            request,
            "tasks.html",
            {
                "user": user,
                "csrf_token": ensure_csrf(request),
                "tasks": tasks[:HISTORY_TASK_LIMIT],
                "history_task_limit": HISTORY_TASK_LIMIT,
                "has_more_tasks": has_more_tasks,
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


@router.get("/tasks/running/status")
def running_task_status(request: Request):
    try:
        user, conn = _current_user_and_conn(request)
    except (ForbiddenError, TypeError, ValueError):
        return JSONResponse({"error": "login required"}, status_code=401)
    try:
        return {
            "tasks": [
                running_task_payload(task)
                for task in list_active_tasks_for_user(conn, user)
            ],
        }
    finally:
        conn.close()


@router.get("/tasks/{task_id}/report.html")
def report_html(request: Request, task_id: int):
    try:
        _, task, path, images, error = _report_context(request, task_id, mark_read=True)
    except (ForbiddenError, TypeError, ValueError):
        return _error_response("Login required", status_code=401)
    if error:
        return error
    return HTMLResponse(
        current_report_html(request.app.state.settings, task, images, path)
    )


@router.get("/tasks/{task_id}/report.pdf")
def report_pdf(request: Request, task_id: int):
    try:
        user, task, html_path, images, error = _report_context(request, task_id)
    except (ForbiddenError, TypeError, ValueError):
        return _error_response("Login required", status_code=401)
    if error:
        return error

    dirs = ensure_task_dirs(request.app.state.settings, task.id)
    current_report_html(request.app.state.settings, task, images, html_path)
    pdf_is_stale = (
        dirs.pdf_report.exists()
        and html_path.exists()
        and dirs.pdf_report.stat().st_mtime < html_path.stat().st_mtime
    )
    if pdf_is_stale or not is_current_report_pdf(dirs.pdf_report):
        try:
            render_report_pdf(
                request.app.state.settings,
                task.id,
                html_path,
                dirs.pdf_report,
            )
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
                "back_link": task_back_link(task.status),
                "failure_actions": task_failure_actions(task.status),
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
        return task_status_payload(task, images)
    finally:
        conn.close()
