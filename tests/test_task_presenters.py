from app.models import (
    TASK_FAILED,
    TASK_QUEUED,
    TASK_RUNNING,
    TASK_SUCCEEDED,
    Task,
    TaskImage,
)
from app.task_presenters import (
    image_status_payload,
    running_task_payload,
    status_fields,
    task_back_link,
    task_failure_actions,
    task_status_payload,
)


def _task(**overrides):
    values = {
        "id": 42,
        "owner_id": 7,
        "title": "审核任务",
        "status": TASK_QUEUED,
        "image_count": 1,
        "audit_spec_id": "jm-ai",
        "screen_width_px": None,
        "screen_height_px": None,
        "summary": None,
        "report_path": None,
        "error_message": None,
    }
    values.update(overrides)
    return Task(**values)


def _image(**overrides):
    values = {
        "id": 9,
        "task_id": 42,
        "filename": "screen.png",
        "original_path": "uploads/42/originals/screen.png",
        "sort_order": 0,
        "status": TASK_RUNNING,
    }
    values.update(overrides)
    return TaskImage(**values)


def test_status_fields_keep_raw_status_and_add_chinese_label():
    assert status_fields(TASK_RUNNING) == {
        "status": "running",
        "status_label": "审核中",
    }


def test_status_fields_fall_back_to_raw_unknown_status():
    assert status_fields("paused") == {
        "status": "paused",
        "status_label": "paused",
    }


def test_task_back_link_routes_active_tasks_to_running_list():
    assert task_back_link(TASK_QUEUED) == {
        "href": "/tasks/running",
        "label": "返回正在进行",
    }
    assert task_back_link(TASK_RUNNING) == {
        "href": "/tasks/running",
        "label": "返回正在进行",
    }


def test_task_back_link_routes_finished_tasks_to_history():
    assert task_back_link(TASK_SUCCEEDED) == {
        "href": "/tasks",
        "label": "返回历史任务",
    }
    assert task_back_link(TASK_FAILED) == {
        "href": "/tasks",
        "label": "返回历史任务",
    }


def test_running_task_payload_contains_list_update_fields():
    assert running_task_payload(_task(id=3, status=TASK_RUNNING)) == {
        "id": 3,
        "status": "running",
        "status_label": "审核中",
    }


def test_image_status_payload_contains_detail_update_fields():
    assert image_status_payload(
        _image(status=TASK_FAILED, error_message="截图审核失败")
    ) == {
        "id": 9,
        "filename": "screen.png",
        "status": "failed",
        "status_label": "失败",
        "error_message": "截图审核失败",
    }


def test_task_status_payload_includes_report_links_when_ready():
    payload = task_status_payload(
        _task(
            id=42,
            status=TASK_SUCCEEDED,
            summary="审核完成",
            report_path="uploads/42/report.html",
        ),
        [_image(id=11, status=TASK_SUCCEEDED, error_message=None)],
    )

    assert payload == {
        "id": 42,
        "status": "succeeded",
        "status_label": "已完成",
        "back_link": {"href": "/tasks", "label": "返回历史任务"},
        "summary": "审核完成",
        "error_message": None,
        "failure_actions": [],
        "report": {
            "html": "/tasks/42/report.html",
            "pdf": "/tasks/42/report.pdf",
        },
        "images": [
            {
                "id": 11,
                "filename": "screen.png",
                "status": "succeeded",
                "status_label": "已完成",
                "error_message": None,
            }
        ],
    }


def test_task_status_payload_omits_report_links_until_ready():
    payload = task_status_payload(_task(status=TASK_RUNNING), [])

    assert payload["report"] is None
    assert payload["back_link"] == {
        "href": "/tasks/running",
        "label": "返回正在进行",
    }


def test_failed_task_payload_includes_recovery_actions():
    payload = task_status_payload(
        _task(status=TASK_FAILED, error_message="模型调用失败"),
        [],
    )

    assert task_failure_actions(TASK_FAILED) == [
        {"href": "/", "label": "重新上传"},
        {"href": "/", "label": "返回新建任务"},
    ]
    assert payload["failure_actions"] == [
        {"href": "/", "label": "重新上传"},
        {"href": "/", "label": "返回新建任务"},
    ]


def test_non_failed_task_payload_has_no_recovery_actions():
    assert task_failure_actions(TASK_RUNNING) == []
    assert task_status_payload(_task(status=TASK_RUNNING), [])["failure_actions"] == []
