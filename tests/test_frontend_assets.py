from pathlib import Path


APP_JS = Path(__file__).resolve().parents[1] / "app" / "static" / "app.js"
TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "app" / "templates"


def test_app_js_keeps_page_behaviors_in_small_initializers():
    source = APP_JS.read_text(encoding="utf-8")

    for name in [
        "initUploadComposer",
        "initTaskDetailPolling",
        "initRunningTaskListPolling",
        "initSpecSearch",
    ]:
        assert f"const {name} = () =>" in source
        assert f"{name}();" in source


def test_upload_file_list_shows_validation_statuses():
    source = APP_JS.read_text(encoding="utf-8")

    assert "formatFileSize" in source
    assert 'className = "file-item-name"' in source
    assert 'className = "file-item-meta"' in source
    assert 'classList.toggle("is-invalid"' in source
    assert 'setAttribute("data-file-status", "invalid")' in source
    assert "文件类型不支持" in source
    assert "文件过大" in source


def test_task_detail_polling_slows_when_page_is_hidden():
    source = APP_JS.read_text(encoding="utf-8")

    assert "visiblePollIntervalMs" in source
    assert "hiddenPollIntervalMs" in source
    assert "document.hidden" in source
    assert 'document.addEventListener("visibilitychange"' in source
    assert "poll({ force: true })" in source
    assert source.count("poll({ force: true })") >= 2


def test_running_task_list_retires_completed_rows_without_immediate_reload():
    source = APP_JS.read_text(encoding="utf-8")

    assert "retireCompletedTaskRows" in source
    assert "已转入历史任务" in source
    assert "is-retiring" in source
    assert "data-task-retired" in source
    assert ".remove()" in source
    assert "hasUnexpectedRunningListChange" in source
    assert "window.location.reload()" in source


def test_task_detail_polling_updates_failure_actions():
    source = APP_JS.read_text(encoding="utf-8")

    assert "updateFailureActions" in source
    assert "#task-failure-actions" in source
    assert "failure_actions" in source
    assert 'className = "task-action-link"' in source


def test_page_scripts_are_deferred():
    for template_name in ["upload.html", "spec_search.html", "task_detail.html", "tasks.html"]:
        source = (TEMPLATES_DIR / template_name).read_text(encoding="utf-8")
        assert 'src="{{ url_for(' in source
        assert "app.js" in source
        assert " defer" in source


def test_page_navigation_avoids_global_transition_state():
    js_source = APP_JS.read_text(encoding="utf-8")
    css_source = (APP_JS.parent / "app.css").read_text(encoding="utf-8")

    assert "is-navigating" not in js_source
    assert "initPageMotion" not in js_source
    assert ".motion-ready .page" not in css_source
