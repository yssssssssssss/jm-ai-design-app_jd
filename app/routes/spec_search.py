from __future__ import annotations

from sqlite3 import Connection

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from app.db import connect
from app.main import ensure_csrf, templates
from app.models import User
from app.repositories import get_user_by_id, list_unread_successful_task_ids_for_user
from app.security import ForbiddenError, require_login
from app.spec_search import MAX_QUERY_LENGTH, search_specs


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


def _has_history_updates(conn: Connection, user: User) -> bool:
    return bool(list_unread_successful_task_ids_for_user(conn, user))


@router.get("/spec-search", response_class=HTMLResponse)
def spec_search_page(request: Request):
    try:
        user, conn = _current_user_and_conn(request)
    except (ForbiddenError, TypeError, ValueError):
        return _redirect_to_login()
    try:
        return templates.TemplateResponse(
            request,
            "spec_search.html",
            {
                "user": user,
                "csrf_token": ensure_csrf(request),
                "title": "规范搜索",
                "nav_active": "spec-search",
                "hide_page_title": True,
                "has_history_updates": _has_history_updates(conn, user),
                "max_query_length": MAX_QUERY_LENGTH,
            },
        )
    finally:
        conn.close()


@router.post("/spec-search/query")
def spec_search_query(request: Request, query: str = Form(...)):
    try:
        _, conn = _current_user_and_conn(request)
    except (ForbiddenError, TypeError, ValueError):
        return JSONResponse({"error": "Login required"}, status_code=403)
    finally:
        if "conn" in locals():
            conn.close()

    try:
        payload = search_specs(query)
    except ValueError as exc:
        message = str(exc)
        if message == "empty query":
            return JSONResponse({"error": "请输入要检索的规范问题"}, status_code=400)
        if message == "query too long":
            return JSONResponse({"error": f"检索内容不能超过 {MAX_QUERY_LENGTH} 个字符"}, status_code=400)
        return JSONResponse({"error": "检索请求无效"}, status_code=400)

    return JSONResponse(payload)
