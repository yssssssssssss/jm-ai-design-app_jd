from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.config import Settings, load_settings
from app.db import SCHEMA_VERSION, connect, init_db
from app.models import task_status_label
from app.repositories import count_active_admins, count_task_jobs_by_status, create_user
from app.security import hash_password, new_csrf_token
from app.task_queue import recover_interrupted_jobs, start_worker, worker_state


APP_DIR = Path(__file__).resolve().parent
ROOT_DIR = APP_DIR.parent
STATIC_ASSET_VERSION = "20260602-6"
templates = Jinja2Templates(directory=APP_DIR / "templates")
templates.env.filters["task_status_label"] = task_status_label
templates.env.globals["static_asset_version"] = STATIC_ASSET_VERSION


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)

    conn = connect(settings.db_path)
    try:
        init_db(conn)
        if count_active_admins(conn) == 0:
            create_user(
                conn,
                settings.initial_admin_username,
                hash_password(settings.initial_admin_password),
                "admin",
            )
        recovered_jobs = recover_interrupted_jobs(settings)
    finally:
        conn.close()

    app = FastAPI()
    app.state.settings = settings
    if settings.enqueue_background_tasks and recovered_jobs:
        start_worker(settings)

    @app.get("/healthz")
    def healthz():
        conn = connect(settings.db_path)
        try:
            schema_version = int(conn.execute("pragma user_version").fetchone()[0])
            db_ok = schema_version == SCHEMA_VERSION
            jobs = count_task_jobs_by_status(conn)
        finally:
            conn.close()
        return {
            "status": "ok" if db_ok else "degraded",
            "database": {
                "ok": db_ok,
                "schema_version": schema_version,
            },
            "worker": worker_state(),
            "jobs": jobs,
        }
    app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
    app.mount("/spec-assets", StaticFiles(directory=ROOT_DIR / "assets" / "spec-images"), name="spec_assets")
    app.mount(
        "/spec-snippets",
        StaticFiles(directory=ROOT_DIR / "assets" / "spec-snippets"),
        name="spec_snippets",
    )
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.app_secret_key,
        https_only=settings.secure_cookies,
        same_site="lax",
        max_age=60 * 60 * 12,
    )

    from app.routes import admin, auth, spec_search, tasks

    app.include_router(auth.router)
    app.include_router(spec_search.router)
    app.include_router(tasks.router)
    app.include_router(admin.router)
    return app


def ensure_csrf(request: Request) -> str:
    token = request.session.get("csrf_token")
    if not token:
        token = new_csrf_token()
        request.session["csrf_token"] = token
    return token
