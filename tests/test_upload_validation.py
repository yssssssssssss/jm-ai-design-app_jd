from app.config import Settings
from app.storage import UploadValidationError
from app.upload_validation import validate_upload_form


class FakeUpload:
    def __init__(self, filename: str, content_type: str, size: int):
        self.filename = filename
        self.content_type = content_type
        self.size = size


def _settings(tmp_path):
    return Settings(
        openai_api_key="key",
        app_secret_key="secret",
        register_invite_code="invite",
        initial_admin_username="admin",
        initial_admin_password="password123",
        data_dir=tmp_path,
        max_upload_files=2,
        max_upload_mb_per_file=1,
    )


def _valid_files():
    return [FakeUpload("screen.png", "image/png", 12)]


def test_validate_upload_form_normalizes_valid_input(tmp_path):
    form = validate_upload_form(
        settings=_settings(tmp_path),
        title="  首页审核  ",
        audit_spec_ids=["jm-ai", "b-design"],
        audit_spec_id=None,
        screen_width_px="1440",
        screen_height_px="900",
        files=_valid_files(),
    )

    assert form.title == "首页审核"
    assert form.audit_spec_ids == ["jm-ai", "b-design"]
    assert form.stored_audit_spec_id == "jm-ai,b-design"
    assert form.screen_width_px == 1440
    assert form.screen_height_px == 900


def test_validate_upload_form_uses_default_title(tmp_path):
    form = validate_upload_form(
        settings=_settings(tmp_path),
        title="  ",
        audit_spec_ids=["jm-ai"],
        audit_spec_id=None,
        screen_width_px=None,
        screen_height_px=None,
        files=_valid_files(),
    )

    assert form.title == "未命名审核任务"
    assert form.screen_width_px is None
    assert form.screen_height_px is None


def test_validate_upload_form_rejects_missing_spec(tmp_path):
    try:
        validate_upload_form(
            settings=_settings(tmp_path),
            title="审核",
            audit_spec_ids=None,
            audit_spec_id=None,
            screen_width_px=None,
            screen_height_px=None,
            files=_valid_files(),
        )
    except UploadValidationError as exc:
        assert "请选择至少一个审核规范" in str(exc)
    else:
        raise AssertionError("missing audit spec should be rejected")


def test_validate_upload_form_rejects_unknown_spec(tmp_path):
    try:
        validate_upload_form(
            settings=_settings(tmp_path),
            title="审核",
            audit_spec_ids=["unknown"],
            audit_spec_id=None,
            screen_width_px=None,
            screen_height_px=None,
            files=_valid_files(),
        )
    except UploadValidationError as exc:
        assert "未知审核规范" in str(exc)
    else:
        raise AssertionError("unknown audit spec should be rejected")


def test_validate_upload_form_keeps_legacy_single_spec_field(tmp_path):
    form = validate_upload_form(
        settings=_settings(tmp_path),
        title="审核",
        audit_spec_ids=None,
        audit_spec_id="b-design",
        screen_width_px=None,
        screen_height_px=None,
        files=_valid_files(),
    )

    assert form.audit_spec_ids == ["b-design"]
    assert form.stored_audit_spec_id == "b-design"


def test_validate_upload_form_rejects_file_count_type_and_size(tmp_path):
    settings = _settings(tmp_path)
    cases = [
        ([], "请至少上传 1 张图片"),
        (
            [
                FakeUpload("a.png", "image/png", 12),
                FakeUpload("b.png", "image/png", 12),
                FakeUpload("c.png", "image/png", 12),
            ],
            "最多上传 2 张图片",
        ),
        ([FakeUpload("a.txt", "text/plain", 12)], "仅支持 PNG/JPG/JPEG/WEBP 图片"),
        (
            [FakeUpload("a.png", "image/png", settings.max_upload_mb_per_file * 1024 * 1024 + 1)],
            "单张图片不能超过 1MB",
        ),
    ]

    for files, message in cases:
        try:
            validate_upload_form(
                settings=settings,
                title="审核",
                audit_spec_ids=["jm-ai"],
                audit_spec_id=None,
                screen_width_px=None,
                screen_height_px=None,
                files=files,
            )
        except UploadValidationError as exc:
            assert message in str(exc)
        else:
            raise AssertionError(f"{message} should be rejected")


def test_validate_upload_form_rejects_invalid_screen_size(tmp_path):
    settings = _settings(tmp_path)
    cases = [
        ("1440", "", "截图宽度和高度需要同时填写"),
        ("1440.5", "900", "截图宽度和高度必须填写整数"),
        ("1440", "900.0", "截图宽度和高度必须填写整数"),
        ("0", "900", "截图宽度和高度必须在 1 到 20000 px 之间"),
        ("1440", "20001", "截图宽度和高度必须在 1 到 20000 px 之间"),
    ]

    for width, height, message in cases:
        try:
            validate_upload_form(
                settings=settings,
                title="审核",
                audit_spec_ids=["jm-ai"],
                audit_spec_id=None,
                screen_width_px=width,
                screen_height_px=height,
                files=_valid_files(),
            )
        except UploadValidationError as exc:
            assert message in str(exc)
        else:
            raise AssertionError(f"{message} should be rejected")
