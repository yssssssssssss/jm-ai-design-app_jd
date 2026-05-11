import json

from PIL import Image

from app.config import Settings
from app.db import connect, init_db
from app.repositories import (
    add_task_image,
    create_task,
    create_user,
    get_task_by_id,
    list_task_images,
)
from app.security import hash_password
from app.storage import ensure_task_dirs, relative_to_data
import app.task_runner as task_runner
from app.task_runner import run_task


def _issue_audit(model: str) -> dict:
    return {
        "model": model,
        "screen_context": "测试页",
        "overall_conclusion": "存在问题",
        "major_issues": [],
        "passes": [],
        "issues": [
            {
                "severity": "中",
                "location": "主按钮",
                "bbox": [2, 2, 8, 8],
                "current_observation": "主按钮颜色偏离 JM AI 主色",
                "spec_expectation": "使用 JM AI 规范主色 token",
                "recommendation": "改为 JM AI 主色 token",
            }
        ],
        "sample_points": [],
        "regions": [],
        "distances": [],
        "checklist": [],
        "cannot_verify": [],
    }


def _empty_audit() -> dict:
    return {
        "screen_context": "测试页",
        "overall_conclusion": "基本符合",
        "major_issues": [],
        "passes": [],
        "issues": [],
        "sample_points": [],
        "regions": [],
        "distances": [],
        "checklist": [],
        "cannot_verify": [],
    }


def test_run_task_generates_report_for_successful_images(tmp_path):
    settings = Settings(
        openai_api_key="key",
        app_secret_key="secret",
        register_invite_code="invite",
        initial_admin_username="admin",
        initial_admin_password="password123",
        data_dir=tmp_path,
    )
    conn = connect(settings.db_path)
    init_db(conn)
    user = create_user(conn, "alice", hash_password("secret123"), "user")
    task = create_task(conn, user.id, "Audit", 1)
    dirs = ensure_task_dirs(settings, task.id)
    image_path = dirs.originals / "image-001.png"
    Image.new("RGB", (20, 20), color=(107, 54, 250)).save(image_path)
    add_task_image(conn, task.id, "image-001.png", relative_to_data(settings, image_path), 0)

    def fake_auditor(path):
        return {
            "screen_context": "测试页",
            "overall_conclusion": "基本符合",
            "major_issues": [],
            "passes": ["主色接近规范"],
            "issues": [],
            "sample_points": [{"label": "center", "x": 10, "y": 10}],
            "regions": [],
            "distances": [],
            "checklist": [{"item": "AI 主色", "status": "通过", "evidence": ""}],
            "cannot_verify": [],
        }

    run_task(settings, task.id, auditor=fake_auditor)

    refreshed = get_task_by_id(conn, task.id)
    images = list_task_images(conn, task.id)

    assert refreshed is not None
    assert refreshed.status == "succeeded"
    assert refreshed.report_path == "uploads/1/report.html"
    assert (tmp_path / refreshed.report_path).exists()
    assert images[0].status == "succeeded"
    assert images[0].tokens_path.endswith("tokens.json")


def test_run_task_dual_mode_writes_model_artifacts_and_merged_audit(monkeypatch, tmp_path):
    settings = Settings(
        openai_api_key="key",
        app_secret_key="secret",
        register_invite_code="invite",
        initial_admin_username="admin",
        initial_admin_password="password123",
        data_dir=tmp_path,
        audit_model_provider="jdcloud",
        audit_mode="dual",
        jdcloud_openai_api_key="jd-key",
        jdcloud_openai_base_url="https://modelservice.jdcloud.com/v1/",
        jdcloud_openai_audit_model="GPT-5.5",
        jdcloud_openai_audit_models=["GPT-5.5", "Kimi-K2.6"],
    )
    conn = connect(settings.db_path)
    init_db(conn)
    user = create_user(conn, "alice", hash_password("secret123"), "user")
    task = create_task(conn, user.id, "Audit", 1)
    dirs = ensure_task_dirs(settings, task.id)
    image_path = dirs.originals / "image-001.png"
    Image.new("RGB", (20, 20), color=(107, 54, 250)).save(image_path)
    add_task_image(conn, task.id, "image-001.png", relative_to_data(settings, image_path), 0)

    seen_models = []

    class FakeClient:
        def __init__(self, **kwargs):
            pass

    def fake_chat_audit(
        client,
        model,
        image_path,
        spec_text,
        reasoning_effort=None,
        declared_screen_size=None,
        scale_context=None,
    ):
        seen_models.append(model)
        return _issue_audit(model)

    monkeypatch.setattr(task_runner, "OpenAI", FakeClient)
    monkeypatch.setattr(task_runner, "audit_image_with_chat", fake_chat_audit)
    spec_path = tmp_path / "spec.md"
    spec_path.write_text("spec", encoding="utf-8")
    monkeypatch.setattr(task_runner, "SPEC_PATH", spec_path)

    run_task(settings, task.id)

    artifact_dir = dirs.artifacts / "image-001"
    assert (artifact_dir / "audit-01-gpt-5.5.json").exists()
    assert (artifact_dir / "audit-02-kimi-k2.6.json").exists()
    assert (artifact_dir / "audit.json").exists()
    assert (artifact_dir / "annotated.png").exists()
    merged_audit = json.loads((artifact_dir / "audit.json").read_text(encoding="utf-8"))
    assert merged_audit["issues"][0]["agreement"] == "both"
    assert merged_audit["model_comparison"]["models"] == ["GPT-5.5", "Kimi-K2.6"]
    assert seen_models == ["GPT-5.5", "Kimi-K2.6"]


def test_run_task_dual_mode_merges_scaled_model_bboxes_before_screenshots(monkeypatch, tmp_path):
    settings = Settings(
        openai_api_key="key",
        app_secret_key="secret",
        register_invite_code="invite",
        initial_admin_username="admin",
        initial_admin_password="password123",
        data_dir=tmp_path,
        audit_model_provider="jdcloud",
        audit_mode="dual",
        jdcloud_openai_api_key="jd-key",
        jdcloud_openai_base_url="https://modelservice.jdcloud.com/v1/",
        jdcloud_openai_audit_model="GPT-5.5",
        jdcloud_openai_audit_models=["GPT-5.5", "Kimi-K2.6"],
    )
    conn = connect(settings.db_path)
    init_db(conn)
    user = create_user(conn, "alice", hash_password("secret123"), "user")
    task = create_task(conn, user.id, "Audit", 1)
    dirs = ensure_task_dirs(settings, task.id)
    image_path = dirs.originals / "image-001.png"
    Image.new("RGB", (3184, 1736), color=(255, 255, 255)).save(image_path)
    add_task_image(conn, task.id, "image-001.png", relative_to_data(settings, image_path), 0)

    class FakeClient:
        def __init__(self, **kwargs):
            pass

    def fake_chat_audit(
        client,
        model,
        image_path,
        spec_text,
        reasoning_effort=None,
        declared_screen_size=None,
        scale_context=None,
    ):
        if model == "GPT-5.5":
            return _issue_audit(model) | {
                "issues": [
                    {
                        "category": "颜色和品牌",
                        "severity": "高",
                        "location": "顶部右上角“邀好友赚套餐”营销按钮",
                        "current_observation": "该营销按钮使用明显橙色渐变或橙色填充。",
                        "bbox": [2609.0, 18.0, 226.0, 63.0],
                    }
                ]
            }
        return _issue_audit(model) | {
            "issues": [
                {
                    "category": "Brand/logo/accent color inventory",
                    "severity": "高",
                    "location": "顶部右上角操作区-邀好友赚套餐按钮",
                    "current_observation": '按钮使用橙红色渐变背景，内有礼物图标和白色文字"邀好友赚套餐"',
                    "bbox": [1177.0, 21.0, 139.0, 36.0],
                }
            ]
        }

    monkeypatch.setattr(task_runner, "OpenAI", FakeClient)
    monkeypatch.setattr(task_runner, "audit_image_with_chat", fake_chat_audit)
    spec_path = tmp_path / "spec.md"
    spec_path.write_text("spec", encoding="utf-8")
    monkeypatch.setattr(task_runner, "SPEC_PATH", spec_path)

    run_task(settings, task.id)

    artifact_dir = dirs.artifacts / "image-001"
    merged_audit = json.loads((artifact_dir / "audit.json").read_text(encoding="utf-8"))
    issues_json = json.loads((artifact_dir / "issues.json").read_text(encoding="utf-8"))
    assert len(merged_audit["issues"]) == 1
    assert merged_audit["issues"][0]["agreement"] == "both"
    assert issues_json[0]["bbox"] == [2609.0, 18.0, 226.0, 63.0]


def test_run_task_dual_mode_model_slug_collision_does_not_overwrite(monkeypatch, tmp_path):
    settings = Settings(
        openai_api_key="key",
        app_secret_key="secret",
        register_invite_code="invite",
        initial_admin_username="admin",
        initial_admin_password="password123",
        data_dir=tmp_path,
        audit_model_provider="jdcloud",
        audit_mode="dual",
        jdcloud_openai_api_key="jd-key",
        jdcloud_openai_base_url="https://modelservice.jdcloud.com/v1/",
        jdcloud_openai_audit_model="A/B",
        jdcloud_openai_audit_models=["A/B", "A B"],
    )
    conn = connect(settings.db_path)
    init_db(conn)
    user = create_user(conn, "alice", hash_password("secret123"), "user")
    task = create_task(conn, user.id, "Audit", 1)
    dirs = ensure_task_dirs(settings, task.id)
    image_path = dirs.originals / "image-001.png"
    Image.new("RGB", (20, 20), color=(107, 54, 250)).save(image_path)
    add_task_image(conn, task.id, "image-001.png", relative_to_data(settings, image_path), 0)

    class FakeClient:
        def __init__(self, **kwargs):
            pass

    def fake_chat_audit(
        client,
        model,
        image_path,
        spec_text,
        reasoning_effort=None,
        declared_screen_size=None,
        scale_context=None,
    ):
        return {**_empty_audit(), "model": model}

    monkeypatch.setattr(task_runner, "OpenAI", FakeClient)
    monkeypatch.setattr(task_runner, "audit_image_with_chat", fake_chat_audit)
    spec_path = tmp_path / "spec.md"
    spec_path.write_text("spec", encoding="utf-8")
    monkeypatch.setattr(task_runner, "SPEC_PATH", spec_path)

    run_task(settings, task.id)

    artifact_dir = dirs.artifacts / "image-001"
    first = artifact_dir / "audit-01-a-b.json"
    second = artifact_dir / "audit-02-a-b.json"
    assert first.exists()
    assert second.exists()
    assert json.loads(first.read_text(encoding="utf-8"))["model"] == "A/B"
    assert json.loads(second.read_text(encoding="utf-8"))["model"] == "A B"


def test_run_task_dual_mode_succeeds_when_one_model_fails(monkeypatch, tmp_path):
    settings = Settings(
        openai_api_key="key",
        app_secret_key="secret",
        register_invite_code="invite",
        initial_admin_username="admin",
        initial_admin_password="password123",
        data_dir=tmp_path,
        audit_model_provider="jdcloud",
        audit_mode="dual",
        jdcloud_openai_api_key="jd-key",
        jdcloud_openai_base_url="https://modelservice.jdcloud.com/v1/",
        jdcloud_openai_audit_model="GPT-5.5",
        jdcloud_openai_audit_models=["GPT-5.5", "Kimi-K2.6"],
    )
    conn = connect(settings.db_path)
    init_db(conn)
    user = create_user(conn, "alice", hash_password("secret123"), "user")
    task = create_task(conn, user.id, "Audit", 1)
    dirs = ensure_task_dirs(settings, task.id)
    image_path = dirs.originals / "image-001.png"
    Image.new("RGB", (20, 20), color=(107, 54, 250)).save(image_path)
    add_task_image(conn, task.id, "image-001.png", relative_to_data(settings, image_path), 0)

    class FakeClient:
        def __init__(self, **kwargs):
            pass

    def fake_chat_audit(
        client,
        model,
        image_path,
        spec_text,
        reasoning_effort=None,
        declared_screen_size=None,
        scale_context=None,
    ):
        if model == "Kimi-K2.6":
            raise RuntimeError("timeout")
        return _issue_audit(model)

    monkeypatch.setattr(task_runner, "OpenAI", FakeClient)
    monkeypatch.setattr(task_runner, "audit_image_with_chat", fake_chat_audit)
    spec_path = tmp_path / "spec.md"
    spec_path.write_text("spec", encoding="utf-8")
    monkeypatch.setattr(task_runner, "SPEC_PATH", spec_path)

    run_task(settings, task.id)

    refreshed = get_task_by_id(conn, task.id)
    artifact_dir = dirs.artifacts / "image-001"
    merged_audit = json.loads((artifact_dir / "audit.json").read_text(encoding="utf-8"))
    assert refreshed is not None
    assert refreshed.status == "succeeded"
    assert merged_audit["issues"][0]["agreement"] == "gpt_only"
    assert merged_audit["model_comparison"]["model_failures"] == [
        {"model": "Kimi-K2.6", "error": "timeout"}
    ]


def test_run_task_dual_mode_passes_same_scale_context_to_both_models(monkeypatch, tmp_path):
    settings = Settings(
        openai_api_key="key",
        app_secret_key="secret",
        register_invite_code="invite",
        initial_admin_username="admin",
        initial_admin_password="password123",
        data_dir=tmp_path,
        audit_model_provider="jdcloud",
        audit_mode="dual",
        jdcloud_openai_api_key="jd-key",
        jdcloud_openai_base_url="https://modelservice.jdcloud.com/v1/",
        jdcloud_openai_audit_model="GPT-5.5",
        jdcloud_openai_audit_models=["GPT-5.5", "Kimi-K2.6"],
    )
    conn = connect(settings.db_path)
    init_db(conn)
    user = create_user(conn, "alice", hash_password("secret123"), "user")
    task = create_task(
        conn,
        user.id,
        "Audit",
        1,
        screen_width_px=1440,
        screen_height_px=900,
    )
    dirs = ensure_task_dirs(settings, task.id)
    image_path = dirs.originals / "image-001.png"
    Image.new("RGB", (720, 450), color=(107, 54, 250)).save(image_path)
    add_task_image(conn, task.id, "image-001.png", relative_to_data(settings, image_path), 0)
    captured = []

    class FakeClient:
        def __init__(self, **kwargs):
            pass

    def fake_chat_audit(
        client,
        model,
        image_path,
        spec_text,
        reasoning_effort=None,
        declared_screen_size=None,
        scale_context=None,
    ):
        captured.append(
            {
                "model": model,
                "declared_screen_size": declared_screen_size,
                "scale_context": scale_context,
            }
        )
        return _empty_audit()

    monkeypatch.setattr(task_runner, "OpenAI", FakeClient)
    monkeypatch.setattr(task_runner, "audit_image_with_chat", fake_chat_audit)
    spec_path = tmp_path / "spec.md"
    spec_path.write_text("spec", encoding="utf-8")
    monkeypatch.setattr(task_runner, "SPEC_PATH", spec_path)

    run_task(settings, task.id)

    assert captured == [
        {
            "model": "GPT-5.5",
            "declared_screen_size": (1440, 900),
            "scale_context": {
                "x": 0.5,
                "y": 0.5,
                "uniform": True,
                "aspect_ratio_mismatch": False,
            },
        },
        {
            "model": "Kimi-K2.6",
            "declared_screen_size": (1440, 900),
            "scale_context": {
                "x": 0.5,
                "y": 0.5,
                "uniform": True,
                "aspect_ratio_mismatch": False,
            },
        },
    ]


def test_run_task_uses_trusted_artifact_dir_for_unsafe_image_filename(tmp_path):
    settings = Settings(
        openai_api_key="key",
        app_secret_key="secret",
        register_invite_code="invite",
        initial_admin_username="admin",
        initial_admin_password="password123",
        data_dir=tmp_path,
    )
    conn = connect(settings.db_path)
    init_db(conn)
    user = create_user(conn, "alice", hash_password("secret123"), "user")
    task = create_task(conn, user.id, "Audit", 1)
    dirs = ensure_task_dirs(settings, task.id)
    image_path = dirs.originals / "image-001.png"
    Image.new("RGB", (20, 20), color=(107, 54, 250)).save(image_path)
    add_task_image(conn, task.id, "../escape.png", relative_to_data(settings, image_path), 0)

    def fake_auditor(path):
        return _empty_audit()

    run_task(settings, task.id, auditor=fake_auditor)

    assert (dirs.artifacts / "image-001" / "audit.json").exists()
    assert not (dirs.artifacts.parent / "escape").exists()


def test_run_task_rerun_no_issue_success_clears_old_annotated_path(tmp_path):
    settings = Settings(
        openai_api_key="key",
        app_secret_key="secret",
        register_invite_code="invite",
        initial_admin_username="admin",
        initial_admin_password="password123",
        data_dir=tmp_path,
    )
    conn = connect(settings.db_path)
    init_db(conn)
    user = create_user(conn, "alice", hash_password("secret123"), "user")
    task = create_task(conn, user.id, "Audit", 1)
    dirs = ensure_task_dirs(settings, task.id)
    image_path = dirs.originals / "image-001.png"
    Image.new("RGB", (20, 20), color=(107, 54, 250)).save(image_path)
    add_task_image(conn, task.id, "image-001.png", relative_to_data(settings, image_path), 0)

    run_task(settings, task.id, auditor=lambda path: _issue_audit("GPT-5.5"))
    assert list_task_images(conn, task.id)[0].annotated_path is not None

    run_task(settings, task.id, auditor=lambda path: _empty_audit())

    assert list_task_images(conn, task.id)[0].annotated_path is None


def test_run_task_rerun_all_failed_clears_old_report_path(tmp_path):
    settings = Settings(
        openai_api_key="key",
        app_secret_key="secret",
        register_invite_code="invite",
        initial_admin_username="admin",
        initial_admin_password="password123",
        data_dir=tmp_path,
    )
    conn = connect(settings.db_path)
    init_db(conn)
    user = create_user(conn, "alice", hash_password("secret123"), "user")
    task = create_task(conn, user.id, "Audit", 1)
    dirs = ensure_task_dirs(settings, task.id)
    image_path = dirs.originals / "image-001.png"
    Image.new("RGB", (20, 20), color=(107, 54, 250)).save(image_path)
    add_task_image(conn, task.id, "image-001.png", relative_to_data(settings, image_path), 0)

    run_task(settings, task.id, auditor=lambda path: _empty_audit())
    assert get_task_by_id(conn, task.id).report_path == "uploads/1/report.html"

    def failing_auditor(path):
        raise RuntimeError("model failed")

    run_task(settings, task.id, auditor=failing_auditor)

    refreshed = get_task_by_id(conn, task.id)
    assert refreshed.status == "failed"
    assert refreshed.report_path is None
    assert refreshed.summary is None


def test_run_task_includes_declared_screen_size_in_report(tmp_path):
    settings = Settings(
        openai_api_key="key",
        app_secret_key="secret",
        register_invite_code="invite",
        initial_admin_username="admin",
        initial_admin_password="password123",
        data_dir=tmp_path,
    )
    conn = connect(settings.db_path)
    init_db(conn)
    user = create_user(conn, "alice", hash_password("secret123"), "user")
    task = create_task(
        conn,
        user.id,
        "Audit",
        1,
        screen_width_px=1440,
        screen_height_px=900,
    )
    dirs = ensure_task_dirs(settings, task.id)
    image_path = dirs.originals / "image-001.png"
    Image.new("RGB", (20, 20), color=(107, 54, 250)).save(image_path)
    add_task_image(conn, task.id, "image-001.png", relative_to_data(settings, image_path), 0)

    def fake_auditor(path):
        return {
            "screen_context": "测试页",
            "overall_conclusion": "基本符合",
            "major_issues": [],
            "passes": [],
            "issues": [],
            "sample_points": [],
            "regions": [],
            "distances": [],
            "checklist": [],
            "cannot_verify": [],
        }

    run_task(settings, task.id, auditor=fake_auditor)

    refreshed = get_task_by_id(conn, task.id)
    assert refreshed is not None
    assert refreshed.report_path is not None
    report_html = (tmp_path / refreshed.report_path).read_text(encoding="utf-8")
    assert "稿件基准尺寸：1440 × 900 px" in report_html


def test_run_task_passes_declared_size_to_measurements(monkeypatch, tmp_path):
    settings = Settings(
        openai_api_key="key",
        app_secret_key="secret",
        register_invite_code="invite",
        initial_admin_username="admin",
        initial_admin_password="password123",
        data_dir=tmp_path,
    )
    conn = connect(settings.db_path)
    init_db(conn)
    user = create_user(conn, "alice", hash_password("secret123"), "user")
    task = create_task(
        conn,
        user.id,
        "Audit",
        1,
        screen_width_px=1440,
        screen_height_px=900,
    )
    dirs = ensure_task_dirs(settings, task.id)
    image_path = dirs.originals / "image-001.png"
    Image.new("RGB", (720, 450), color=(107, 54, 250)).save(image_path)
    add_task_image(conn, task.id, "image-001.png", relative_to_data(settings, image_path), 0)
    captured = {}

    def fake_measurements(
        image_path,
        regions_path,
        output_path,
        crop_dir,
        design_size=None,
    ):
        captured["design_size"] = design_size
        output_path.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(task_runner, "run_measurements", fake_measurements)

    run_task(settings, task.id, auditor=lambda path: _empty_audit())

    assert captured["design_size"] == (1440, 900)


def test_run_task_applies_rule_review_before_writing_final_audit(monkeypatch, tmp_path):
    settings = Settings(
        openai_api_key="key",
        app_secret_key="secret",
        register_invite_code="invite",
        initial_admin_username="admin",
        initial_admin_password="password123",
        data_dir=tmp_path,
    )
    conn = connect(settings.db_path)
    init_db(conn)
    user = create_user(conn, "alice", hash_password("secret123"), "user")
    task = create_task(conn, user.id, "Audit", 1)
    dirs = ensure_task_dirs(settings, task.id)
    image_path = dirs.originals / "image-001.png"
    Image.new("RGB", (40, 40), color=(255, 255, 255)).save(image_path)
    add_task_image(conn, task.id, "image-001.png", relative_to_data(settings, image_path), 0)

    def fake_auditor(path):
        return {
            **_empty_audit(),
            "sample_points": [{"label": "邀好友赚套餐按钮", "x": 20, "y": 20}],
        }

    def fake_color_analysis(image_path, output_path, sample_points):
        output_path.write_text(
            json.dumps(
                {
                    "samples": [
                        {
                            "label": "邀好友赚套餐按钮",
                            "x": 20,
                            "y": 20,
                            "hex": "#F37021",
                            "family": "red/orange",
                            "nearest_jm_token": {
                                "name": "ai/ai-normal",
                                "hex": "#6B36FA",
                                "distance": 190.0,
                                "is_close": False,
                            },
                            "off_token_candidate": True,
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def fake_measurements(image_path, regions_path, output_path, crop_dir, design_size=None):
        output_path.write_text(json.dumps({"regions": [], "distances": []}), encoding="utf-8")

    monkeypatch.setattr(task_runner, "run_color_analysis", fake_color_analysis)
    monkeypatch.setattr(task_runner, "run_measurements", fake_measurements)

    run_task(settings, task.id, auditor=fake_auditor)

    artifact_dir = dirs.artifacts / "image-001"
    final_audit = json.loads((artifact_dir / "audit.json").read_text(encoding="utf-8"))
    issues_json = json.loads((artifact_dir / "issues.json").read_text(encoding="utf-8"))
    assert final_audit["issues"][0]["rule_source"] == "color_sample"
    assert final_audit["issues"][0]["location"] == "邀好友赚套餐按钮"
    assert issues_json[0]["bbox"] == [8.0, 8.0, 24.0, 24.0]


def test_run_task_omits_design_size_when_task_has_no_declared_size(monkeypatch, tmp_path):
    settings = Settings(
        openai_api_key="key",
        app_secret_key="secret",
        register_invite_code="invite",
        initial_admin_username="admin",
        initial_admin_password="password123",
        data_dir=tmp_path,
    )
    conn = connect(settings.db_path)
    init_db(conn)
    user = create_user(conn, "alice", hash_password("secret123"), "user")
    task = create_task(conn, user.id, "Audit", 1)
    dirs = ensure_task_dirs(settings, task.id)
    image_path = dirs.originals / "image-001.png"
    Image.new("RGB", (720, 450), color=(107, 54, 250)).save(image_path)
    add_task_image(conn, task.id, "image-001.png", relative_to_data(settings, image_path), 0)
    captured = {}

    def fake_measurements(
        image_path,
        regions_path,
        output_path,
        crop_dir,
        design_size=None,
    ):
        captured["design_size"] = design_size
        output_path.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(task_runner, "run_measurements", fake_measurements)

    run_task(settings, task.id, auditor=lambda path: _empty_audit())

    assert captured["design_size"] is None


def test_run_task_default_auditor_receives_scale_context(monkeypatch, tmp_path):
    settings = Settings(
        openai_api_key="key",
        app_secret_key="secret",
        register_invite_code="invite",
        initial_admin_username="admin",
        initial_admin_password="password123",
        data_dir=tmp_path,
    )
    conn = connect(settings.db_path)
    init_db(conn)
    user = create_user(conn, "alice", hash_password("secret123"), "user")
    task = create_task(
        conn,
        user.id,
        "Audit",
        1,
        screen_width_px=1440,
        screen_height_px=900,
    )
    dirs = ensure_task_dirs(settings, task.id)
    image_path = dirs.originals / "image-001.png"
    Image.new("RGB", (720, 450), color=(107, 54, 250)).save(image_path)
    add_task_image(conn, task.id, "image-001.png", relative_to_data(settings, image_path), 0)
    captured = {}

    class FakeClient:
        def __init__(self, **kwargs):
            pass

    def fake_audit(
        client,
        model,
        image_path,
        spec_text,
        reasoning_effort=None,
        declared_screen_size=None,
        scale_context=None,
    ):
        captured["declared_screen_size"] = declared_screen_size
        captured["scale_context"] = scale_context
        return _empty_audit()

    monkeypatch.setattr(task_runner, "OpenAI", FakeClient)
    monkeypatch.setattr(task_runner, "audit_image", fake_audit)
    spec_path = tmp_path / "spec.md"
    spec_path.write_text("spec", encoding="utf-8")
    monkeypatch.setattr(task_runner, "SPEC_PATH", spec_path)

    run_task(settings, task.id)

    assert captured["declared_screen_size"] == (1440, 900)
    assert captured["scale_context"] == {
        "x": 0.5,
        "y": 0.5,
        "uniform": True,
        "aspect_ratio_mismatch": False,
    }


def test_run_task_marks_task_failed_when_all_images_fail(tmp_path):
    settings = Settings(
        openai_api_key="key",
        app_secret_key="secret",
        register_invite_code="invite",
        initial_admin_username="admin",
        initial_admin_password="password123",
        data_dir=tmp_path,
    )
    conn = connect(settings.db_path)
    init_db(conn)
    user = create_user(conn, "alice", hash_password("secret123"), "user")
    task = create_task(conn, user.id, "Audit", 1)
    dirs = ensure_task_dirs(settings, task.id)
    image_path = dirs.originals / "image-001.png"
    Image.new("RGB", (20, 20), color=(107, 54, 250)).save(image_path)
    add_task_image(conn, task.id, "image-001.png", relative_to_data(settings, image_path), 0)

    def failing_auditor(path):
        raise RuntimeError("model failed")

    run_task(settings, task.id, auditor=failing_auditor)

    refreshed = get_task_by_id(conn, task.id)
    images = list_task_images(conn, task.id)

    assert refreshed is not None
    assert refreshed.status == "failed"
    assert refreshed.error_message == "全部图片审核失败"
    assert images[0].status == "failed"
    assert images[0].error_message == "model failed"


def test_default_auditor_sets_openai_timeout(monkeypatch, tmp_path):
    settings = Settings(
        openai_api_key="key",
        app_secret_key="secret",
        register_invite_code="invite",
        initial_admin_username="admin",
        initial_admin_password="password123",
        data_dir=tmp_path,
        openai_timeout_seconds=12,
    )
    captured = {}

    class FakeClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(task_runner, "OpenAI", FakeClient)
    spec_path = tmp_path / "spec.md"
    spec_path.write_text("spec", encoding="utf-8")
    monkeypatch.setattr(task_runner, "SPEC_PATH", spec_path)

    auditor = task_runner._default_auditor(settings)

    assert callable(auditor)
    assert captured == {
        "api_key": "key",
        "base_url": None,
        "timeout": 12,
        "max_retries": 0,
    }


def test_default_auditor_uses_jdcloud_chat_when_configured(monkeypatch, tmp_path):
    settings = Settings(
        openai_api_key="key",
        app_secret_key="secret",
        register_invite_code="invite",
        initial_admin_username="admin",
        initial_admin_password="password123",
        data_dir=tmp_path,
        audit_model_provider="jdcloud",
        jdcloud_openai_api_key="jd-key",
        jdcloud_openai_base_url="https://modelservice.jdcloud.com/v1/",
        jdcloud_openai_audit_model="Kimi-K2.6",
        jdcloud_openai_timeout_seconds=60,
    )
    captured_client = {}
    captured_audit = {}

    class FakeClient:
        def __init__(self, **kwargs):
            captured_client.update(kwargs)

    def fake_chat_audit(
        client,
        model,
        image_path,
        spec_text,
        reasoning_effort=None,
        declared_screen_size=None,
        scale_context=None,
    ):
        captured_audit.update(
            {
                "client": client,
                "model": model,
                "image_path": image_path,
                "spec_text": spec_text,
                "reasoning_effort": reasoning_effort,
                "declared_screen_size": declared_screen_size,
            }
        )
        return {}

    monkeypatch.setattr(task_runner, "OpenAI", FakeClient)
    monkeypatch.setattr(task_runner, "audit_image_with_chat", fake_chat_audit)
    spec_path = tmp_path / "spec.md"
    spec_path.write_text("spec", encoding="utf-8")
    monkeypatch.setattr(task_runner, "SPEC_PATH", spec_path)

    auditor = task_runner._default_auditor(settings, declared_screen_size=(1440, 900))
    image_path = tmp_path / "screen.png"
    auditor(image_path)

    assert captured_client == {
        "api_key": "jd-key",
        "base_url": "https://modelservice.jdcloud.com/v1/",
        "timeout": 60,
        "max_retries": 0,
    }
    assert captured_audit["model"] == "Kimi-K2.6"
    assert captured_audit["image_path"] == image_path
    assert captured_audit["spec_text"] == "spec"
    assert captured_audit["reasoning_effort"] is None
    assert captured_audit["declared_screen_size"] == (1440, 900)


def test_default_auditor_passes_scale_context(monkeypatch, tmp_path):
    settings = Settings(
        openai_api_key="key",
        app_secret_key="secret",
        register_invite_code="invite",
        initial_admin_username="admin",
        initial_admin_password="password123",
        data_dir=tmp_path,
        audit_model_provider="jdcloud",
        jdcloud_openai_api_key="jd-key",
        jdcloud_openai_base_url="https://modelservice.jdcloud.com/v1/",
        jdcloud_openai_audit_model="Kimi-K2.6",
    )
    captured_audit = {}

    class FakeClient:
        def __init__(self, **kwargs):
            pass

    def fake_chat_audit(
        client,
        model,
        image_path,
        spec_text,
        reasoning_effort=None,
        declared_screen_size=None,
        scale_context=None,
    ):
        captured_audit.update(
            {
                "declared_screen_size": declared_screen_size,
                "scale_context": scale_context,
            }
        )
        return {}

    monkeypatch.setattr(task_runner, "OpenAI", FakeClient)
    monkeypatch.setattr(task_runner, "audit_image_with_chat", fake_chat_audit)
    spec_path = tmp_path / "spec.md"
    spec_path.write_text("spec", encoding="utf-8")
    monkeypatch.setattr(task_runner, "SPEC_PATH", spec_path)

    auditor = task_runner._default_auditor(settings, declared_screen_size=(1440, 900))
    auditor(tmp_path / "screen.png", scale_context={"x": 0.5, "y": 0.5, "uniform": True})

    assert captured_audit["declared_screen_size"] == (1440, 900)
    assert captured_audit["scale_context"] == {"x": 0.5, "y": 0.5, "uniform": True}
