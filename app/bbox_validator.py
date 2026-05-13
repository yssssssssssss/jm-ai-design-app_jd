from __future__ import annotations

import math
from typing import Any


TRUSTED = "trusted"
SUSPICIOUS = "suspicious"
DROPPED = "dropped"


def validate_bbox(issue: dict[str, Any], image_size: tuple[int, int]) -> dict[str, Any]:
    output = dict(issue)
    bbox = _bbox_as_list(issue.get("bbox"))
    if bbox is None:
        return _with_status(output, None, DROPPED, 0.0, "bbox 无效")

    width, height = image_size
    if width <= 0 or height <= 0:
        return _with_status(output, None, DROPPED, 0.0, "图片尺寸无效")

    x, y, w, h = bbox
    if x < 0 or y < 0 or x + w > width or y + h > height:
        return _with_status(output, None, DROPPED, 0.0, "bbox 越界")

    if _has_position_conflict(output, bbox, image_size):
        return _with_status(output, bbox, SUSPICIOUS, 0.4, "bbox 与文本位置描述冲突")

    return _with_status(output, bbox, TRUSTED, 0.9, "")


def _with_status(
    issue: dict[str, Any],
    bbox: list[float] | None,
    status: str,
    confidence: float,
    reason: str,
) -> dict[str, Any]:
    issue["bbox"] = bbox
    issue["bbox_status"] = status
    issue["bbox_confidence"] = confidence
    issue["bbox_reason"] = reason
    return issue


def _bbox_as_list(value: Any) -> list[float] | None:
    try:
        if isinstance(value, dict):
            bbox = [
                float(value["x"]),
                float(value["y"]),
                float(value["width"]),
                float(value["height"]),
            ]
        elif isinstance(value, (list, tuple)) and len(value) == 4:
            bbox = [float(item) for item in value]
        else:
            return None
    except (KeyError, TypeError, ValueError):
        return None
    if not all(math.isfinite(item) for item in bbox):
        return None
    if bbox[2] <= 0 or bbox[3] <= 0:
        return None
    return bbox


def _has_position_conflict(
    issue: dict[str, Any],
    bbox: list[float],
    image_size: tuple[int, int],
) -> bool:
    width, height = image_size
    center_x = bbox[0] + bbox[2] / 2
    center_y = bbox[1] + bbox[3] / 2
    text = _position_text(issue)

    has_left = "左" in text
    has_right = "右" in text
    has_top = "顶部" in text or "上角" in text or "右上" in text or "左上" in text
    has_bottom = "底部" in text or "下角" in text or "右下" in text or "左下" in text

    if "右下" in text and (center_x < width * 0.55 or center_y < height * 0.55):
        return True
    if "右上" in text and (center_x < width * 0.55 or center_y > height * 0.45):
        return True
    if "左下" in text and (center_x > width * 0.45 or center_y < height * 0.55):
        return True
    if "左上" in text and (center_x > width * 0.45 or center_y > height * 0.45):
        return True
    if has_right and not has_left and center_x < width * 0.55:
        return True
    if has_left and not has_right and center_x > width * 0.45:
        return True
    if has_bottom and not has_top and center_y < height * 0.45:
        return True
    if has_top and not has_bottom and center_y > height * 0.45:
        return True
    return False


def _position_text(issue: dict[str, Any]) -> str:
    fields = [
        "target_element",
        "location",
        "title",
    ]
    return " ".join(str(issue.get(field) or "") for field in fields)
