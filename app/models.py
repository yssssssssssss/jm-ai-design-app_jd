from __future__ import annotations

from dataclasses import dataclass


ROLE_ADMIN = "admin"
ROLE_USER = "user"
STATUS_ACTIVE = "active"
STATUS_DISABLED = "disabled"
TASK_QUEUED = "queued"
TASK_RUNNING = "running"
TASK_SUCCEEDED = "succeeded"
TASK_FAILED = "failed"
TASK_STATUS_LABELS = {
    TASK_QUEUED: "排队中",
    TASK_RUNNING: "审核中",
    TASK_SUCCEEDED: "已完成",
    TASK_FAILED: "失败",
}


def task_status_label(status: str) -> str:
    return TASK_STATUS_LABELS.get(status, status)


@dataclass(frozen=True)
class User:
    id: int
    username: str
    password_hash: str
    role: str
    status: str
    created_at: str | None = None
    last_login_at: str | None = None

    @property
    def is_admin(self) -> bool:
        return self.role == ROLE_ADMIN


@dataclass(frozen=True)
class Task:
    id: int
    owner_id: int
    title: str
    status: str
    image_count: int
    audit_spec_id: str
    screen_width_px: int | None
    screen_height_px: int | None
    summary: str | None
    report_path: str | None
    error_message: str | None
    created_at: str | None = None
    updated_at: str | None = None
    completed_at: str | None = None
    owner_username: str | None = None


@dataclass(frozen=True)
class TaskImage:
    id: int
    task_id: int
    filename: str
    original_path: str
    sort_order: int
    status: str
    annotated_path: str | None = None
    tokens_path: str | None = None
    measurements_path: str | None = None
    issues_path: str | None = None
    audit_json_path: str | None = None
    error_message: str | None = None


@dataclass(frozen=True)
class TaskJob:
    id: int
    task_id: int
    status: str
    attempts: int
    locked_at: str | None = None
    locked_by: str | None = None
    error_message: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    finished_at: str | None = None
