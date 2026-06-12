from __future__ import annotations

from app.models import (
    TASK_FAILED,
    TASK_QUEUED,
    TASK_RUNNING,
    Task,
    TaskImage,
    task_status_label,
)


def task_back_link(status: str) -> dict[str, str]:
    if status in {TASK_QUEUED, TASK_RUNNING}:
        return {"href": "/tasks/running", "label": "返回正在进行"}
    return {"href": "/tasks", "label": "返回历史任务"}


def status_fields(status: str) -> dict[str, str]:
    return {"status": status, "status_label": task_status_label(status)}


def task_failure_actions(status: str) -> list[dict[str, str]]:
    if status != TASK_FAILED:
        return []
    return [
        {"href": "/", "label": "重新上传"},
        {"href": "/", "label": "返回新建任务"},
    ]


def running_task_payload(task: Task) -> dict:
    return {
        "id": task.id,
        **status_fields(task.status),
    }


def image_status_payload(image: TaskImage) -> dict:
    return {
        "id": image.id,
        "filename": image.filename,
        **status_fields(image.status),
        "error_message": image.error_message,
    }


def task_status_payload(task: Task, images: list[TaskImage]) -> dict:
    return {
        "id": task.id,
        **status_fields(task.status),
        "back_link": task_back_link(task.status),
        "summary": task.summary,
        "error_message": task.error_message,
        "failure_actions": task_failure_actions(task.status),
        "report": {
            "html": f"/tasks/{task.id}/report.html",
            "pdf": f"/tasks/{task.id}/report.pdf",
        }
        if task.report_path
        else None,
        "images": [image_status_payload(image) for image in images],
    }
