import json

from app.config import Settings
from app.models import Task, TaskImage
from app.report_renderer import REPORT_RENDERER_VERSION
from app.task_reports import (
    build_report_image_results,
    current_report_html,
    html_report_is_current,
    report_artifacts_are_cached,
    multi_spec_artifact_path,
)


def _settings(tmp_path):
    return Settings(
        openai_api_key="key",
        app_secret_key="secret",
        register_invite_code="invite",
        initial_admin_username="admin",
        initial_admin_password="password123",
        data_dir=tmp_path,
    )


def _task(**overrides):
    values = {
        "id": 42,
        "owner_id": 7,
        "title": "审核任务",
        "status": "succeeded",
        "image_count": 1,
        "audit_spec_id": "jm-ai",
        "screen_width_px": None,
        "screen_height_px": None,
        "summary": "审核完成",
        "report_path": "uploads/42/report.html",
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
        "status": "succeeded",
    }
    values.update(overrides)
    return TaskImage(**values)


def _audit_payload(label: str):
    return {
        "screen_context": label,
        "overall_conclusion": "存在问题",
        "passes": [],
        "issues": [
            {
                "id": f"{label}-01",
                "severity": "中",
                "category": "色彩",
                "location": "主按钮",
                "current_observation": label,
                "recommendation": "Change button to JM AI color token.",
            }
        ],
        "checklist": [],
        "cannot_verify": [],
    }


def test_multi_spec_artifact_path_isolated_by_spec_id():
    assert (
        multi_spec_artifact_path(42, 0, "jm-ai", "audit.json")
        == "uploads/42/artifacts/image-001/jm-ai/audit.json"
    )
    assert (
        multi_spec_artifact_path(42, 0, "b-design", "audit.json")
        == "uploads/42/artifacts/image-001/b-design/audit.json"
    )


def test_build_report_image_results_reads_legacy_single_spec_artifacts(tmp_path):
    settings = _settings(tmp_path)
    audit_path = settings.uploads_dir / "42" / "artifacts" / "image-001" / "audit.json"
    audit_path.parent.mkdir(parents=True)
    audit_path.write_text(json.dumps(_audit_payload("jm")), encoding="utf-8")
    crop_path = audit_path.parent / "issue-jm-01.png"
    crop_path.write_bytes(b"png")
    image = _image(audit_json_path="uploads/42/artifacts/image-001/audit.json")

    results = build_report_image_results(settings, _task(), [image])

    assert len(results) == 1
    assert results[0]["audit_spec_label"] == "JM AI 设计规范"
    assert results[0]["audit"]["screen_context"] == "jm"
    assert results[0]["artifacts"]["audit_json"] == "artifacts/image-001/audit.json"
    assert results[0]["artifacts"]["issue_crops"] == [
        "uploads/42/artifacts/image-001/issue-jm-01.png"
    ]


def test_build_report_image_results_keeps_multi_spec_artifacts_isolated(tmp_path):
    settings = _settings(tmp_path)
    root = settings.uploads_dir / "42" / "artifacts" / "image-001"
    for spec_id, label in [("jm-ai", "jm"), ("b-design", "b")]:
        spec_dir = root / spec_id
        spec_dir.mkdir(parents=True)
        (spec_dir / "audit.json").write_text(
            json.dumps(_audit_payload(label)),
            encoding="utf-8",
        )
        (spec_dir / "annotated.png").write_bytes(b"png")
        (spec_dir / f"issue-{label}-01.png").write_bytes(b"png")

    results = build_report_image_results(
        settings,
        _task(audit_spec_id="jm-ai,b-design"),
        [_image(sort_order=0)],
    )

    assert [result["audit"]["screen_context"] for result in results] == ["jm", "b"]
    assert [result["audit_spec_label"] for result in results] == [
        "JM AI 设计规范",
        "京东 B 端设计规范（B-design Agent 组件规范）",
    ]
    assert results[0]["artifacts"]["annotated"] == "artifacts/image-001/jm-ai/annotated.png"
    assert results[1]["artifacts"]["annotated"] == "artifacts/image-001/b-design/annotated.png"
    assert results[0]["artifacts"]["issue_crops"] == [
        "uploads/42/artifacts/image-001/jm-ai/issue-jm-01.png"
    ]
    assert results[1]["artifacts"]["issue_crops"] == [
        "uploads/42/artifacts/image-001/b-design/issue-b-01.png"
    ]


def test_build_report_image_results_does_not_fallback_between_specs(tmp_path):
    settings = _settings(tmp_path)
    root = settings.uploads_dir / "42" / "artifacts" / "image-001"
    jm_dir = root / "jm-ai"
    jm_dir.mkdir(parents=True)
    (jm_dir / "audit.json").write_text(
        json.dumps(_audit_payload("jm")),
        encoding="utf-8",
    )
    (root / "b-design").mkdir()

    results = build_report_image_results(
        settings,
        _task(audit_spec_id="jm-ai,b-design"),
        [_image(sort_order=0)],
    )

    assert len(results) == 1
    assert results[0]["audit_spec_label"] == "JM AI 设计规范"
    assert results[0]["audit"]["screen_context"] == "jm"


def test_current_report_html_falls_back_to_existing_report_with_pdf_link(tmp_path):
    settings = _settings(tmp_path)
    report_path = tmp_path / "uploads" / "42" / "report.html"
    report_path.parent.mkdir(parents=True)
    report_path.write_text(
        '<html><body><a class="back-link" href="/tasks">返回</a></body></html>',
        encoding="utf-8",
    )

    html = current_report_html(settings, _task(), [], report_path)

    assert 'href="/tasks/42/report.pdf">下载 PDF</a>' in html


def test_html_report_is_current_requires_renderer_version_marker(tmp_path):
    report_path = tmp_path / "report.html"
    report_path.write_text("<html>old</html>", encoding="utf-8")

    assert not html_report_is_current(report_path)

    report_path.write_text(
        f'<meta name="jm-report-renderer" content="{REPORT_RENDERER_VERSION}">',
        encoding="utf-8",
    )

    assert html_report_is_current(report_path)


def test_report_artifacts_are_cached_when_report_is_newer_than_audit_json(tmp_path):
    settings = _settings(tmp_path)
    report_path = tmp_path / "uploads" / "42" / "report.html"
    audit_path = tmp_path / "uploads" / "42" / "artifacts" / "image-001" / "audit.json"
    audit_path.parent.mkdir(parents=True)
    audit_path.write_text(json.dumps(_audit_payload("jm")), encoding="utf-8")
    report_path.write_text(
        f'<meta name="jm-report-renderer" content="{REPORT_RENDERER_VERSION}">cached',
        encoding="utf-8",
    )

    assert report_artifacts_are_cached(
        settings,
        _task(),
        [_image(audit_json_path="uploads/42/artifacts/image-001/audit.json")],
        report_path,
    )


def test_report_artifacts_are_not_cached_when_audit_json_is_newer(tmp_path):
    settings = _settings(tmp_path)
    report_path = tmp_path / "uploads" / "42" / "report.html"
    audit_path = tmp_path / "uploads" / "42" / "artifacts" / "image-001" / "audit.json"
    audit_path.parent.mkdir(parents=True)
    audit_path.write_text(json.dumps(_audit_payload("jm")), encoding="utf-8")
    report_path.write_text(
        f'<meta name="jm-report-renderer" content="{REPORT_RENDERER_VERSION}">cached',
        encoding="utf-8",
    )
    audit_path.touch()

    assert not report_artifacts_are_cached(
        settings,
        _task(),
        [_image(audit_json_path="uploads/42/artifacts/image-001/audit.json")],
        report_path,
    )


def test_report_artifacts_are_not_cached_when_issue_crop_is_newer(tmp_path):
    settings = _settings(tmp_path)
    report_path = tmp_path / "uploads" / "42" / "report.html"
    audit_path = tmp_path / "uploads" / "42" / "artifacts" / "image-001" / "audit.json"
    audit_path.parent.mkdir(parents=True)
    audit_path.write_text(json.dumps(_audit_payload("jm")), encoding="utf-8")
    report_path.write_text(
        f'<meta name="jm-report-renderer" content="{REPORT_RENDERER_VERSION}">cached',
        encoding="utf-8",
    )
    crop_path = audit_path.parent / "issue-jm-01.png"
    crop_path.write_bytes(b"png")
    crop_path.touch()

    assert not report_artifacts_are_cached(
        settings,
        _task(),
        [_image(audit_json_path="uploads/42/artifacts/image-001/audit.json")],
        report_path,
    )


def test_current_report_html_uses_cached_report_without_re_rendering(
    monkeypatch,
    tmp_path,
):
    settings = _settings(tmp_path)
    report_path = tmp_path / "uploads" / "42" / "report.html"
    audit_path = tmp_path / "uploads" / "42" / "artifacts" / "image-001" / "audit.json"
    audit_path.parent.mkdir(parents=True)
    audit_path.write_text(json.dumps(_audit_payload("jm")), encoding="utf-8")
    report_path.write_text(
        f'<html><head><meta name="jm-report-renderer" content="{REPORT_RENDERER_VERSION}"></head>'
        '<body><a class="back-link" href="/tasks">返回</a>cached</body></html>',
        encoding="utf-8",
    )

    def fail_render(*args, **kwargs):
        raise AssertionError("cached reports should not be rendered again")

    monkeypatch.setattr("app.task_reports.render_report_html", fail_render)

    html = current_report_html(
        settings,
        _task(),
        [_image(audit_json_path="uploads/42/artifacts/image-001/audit.json")],
        report_path,
    )

    assert "cached" in html
    assert 'href="/tasks/42/report.pdf">下载 PDF</a>' in html
