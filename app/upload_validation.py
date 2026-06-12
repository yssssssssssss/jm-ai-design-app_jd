from __future__ import annotations

from dataclasses import dataclass

from app.config import Settings
from app.spec_registry import serialize_audit_spec_ids, validate_audit_spec_ids
from app.storage import UploadValidationError, validate_upload_batch


@dataclass(frozen=True)
class UploadForm:
    title: str
    audit_spec_ids: list[str]
    stored_audit_spec_id: str
    screen_width_px: int | None
    screen_height_px: int | None


def validate_upload_form(
    *,
    settings: Settings,
    title: str,
    audit_spec_ids: list[str] | None,
    audit_spec_id: str | None,
    screen_width_px: str | None,
    screen_height_px: str | None,
    files: list,
) -> UploadForm:
    if not audit_spec_ids and not audit_spec_id:
        raise UploadValidationError("请选择至少一个审核规范")
    try:
        selected_audit_spec_ids = validate_audit_spec_ids(
            audit_spec_ids or audit_spec_id
        )
    except ValueError as exc:
        raise UploadValidationError("未知审核规范") from exc

    validate_upload_batch(settings, files)
    parsed_width, parsed_height = validate_screen_size(
        screen_width_px,
        screen_height_px,
    )
    return UploadForm(
        title=title.strip() or "未命名审核任务",
        audit_spec_ids=selected_audit_spec_ids,
        stored_audit_spec_id=serialize_audit_spec_ids(selected_audit_spec_ids),
        screen_width_px=parsed_width,
        screen_height_px=parsed_height,
    )


def validate_screen_size(
    width: str | None,
    height: str | None,
) -> tuple[int | None, int | None]:
    width_value = (width or "").strip()
    height_value = (height or "").strip()
    if not width_value and not height_value:
        return None, None
    if not width_value or not height_value:
        raise UploadValidationError("截图宽度和高度需要同时填写")
    try:
        parsed_width = int(width_value)
        parsed_height = int(height_value)
    except ValueError as exc:
        raise UploadValidationError("截图宽度和高度必须填写整数") from exc
    if str(parsed_width) != width_value or str(parsed_height) != height_value:
        raise UploadValidationError("截图宽度和高度必须填写整数")
    if not 1 <= parsed_width <= 20000 or not 1 <= parsed_height <= 20000:
        raise UploadValidationError("截图宽度和高度必须在 1 到 20000 px 之间")
    return parsed_width, parsed_height
