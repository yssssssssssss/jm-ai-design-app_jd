from __future__ import annotations

from copy import deepcopy
from typing import Any


REQUIRED_AUDIT_LISTS = [
    "major_issues",
    "passes",
    "issues",
    "sample_points",
    "regions",
    "distances",
    "checklist",
    "cannot_verify",
]
SEVERITY_RANK = {"低": 1, "中": 2, "高": 3}


def apply_rule_review(
    audit: dict[str, Any],
    tokens: dict[str, Any] | None,
    measurements: dict[str, Any] | None,
    image_size: tuple[int, int],
) -> dict[str, Any]:
    reviewed = deepcopy(audit)
    _ensure_shape(reviewed)
    reviewed["issues"] = [_normalize_issue(issue, image_size) for issue in _list(reviewed.get("issues"))]

    for issue in _color_issues_from_samples(tokens):
        _upsert_issue(reviewed["issues"], issue)
    for issue in _spacing_issues_from_measurements(measurements):
        _upsert_issue(reviewed["issues"], issue)

    _finalize(reviewed)
    return reviewed


def _ensure_shape(audit: dict[str, Any]) -> None:
    audit.setdefault("screen_context", "")
    audit.setdefault("overall_conclusion", "")
    for key in REQUIRED_AUDIT_LISTS:
        if not isinstance(audit.get(key), list):
            audit[key] = []


def _color_issues_from_samples(tokens: dict[str, Any] | None) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for sample in _list((tokens or {}).get("samples")):
        if not isinstance(sample, dict) or not sample.get("off_token_candidate"):
            continue
        label = str(sample.get("label") or "颜色采样点")
        hex_value = str(sample.get("hex") or "未知颜色")
        nearest = sample.get("nearest_jm_token") if isinstance(sample.get("nearest_jm_token"), dict) else {}
        nearest_name = str(nearest.get("name") or "JM AI 色彩 token")
        nearest_hex = str(nearest.get("hex") or "")
        distance = nearest.get("distance")
        distance_text = f"，色差 {distance}" if distance is not None else ""
        bbox = _sample_bbox(sample)
        issues.append(
            {
                "category": "色彩",
                "severity": "中",
                "location": label,
                "current_observation": (
                    f"实测颜色 {hex_value} 偏离 JM AI 规范色，最近 token 为 "
                    f"{nearest_name}{f'({nearest_hex})' if nearest_hex else ''}{distance_text}。"
                ),
                "spec_expectation": "可见的主操作、营销入口、品牌感知元素应使用 JM AI 规范色彩 token。",
                "recommendation": "将该区域颜色替换为规范色彩 token，避免使用未授权的高饱和强调色。",
                "confidence": 0.9,
                "bbox": bbox,
                "rule_source": "color_sample",
            }
        )
    return issues


def _spacing_issues_from_measurements(measurements: dict[str, Any] | None) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for distance in _list((measurements or {}).get("distances")):
        if not isinstance(distance, dict):
            continue
        nearest = distance.get("nearest_spacing")
        if not isinstance(nearest, dict) or nearest.get("passes_with_1px_tolerance") is not False:
            continue
        location = str(distance.get("id") or f"{distance.get('from', '')}-{distance.get('to', '')}")
        measured = distance.get("gap_design_px", distance.get("gap_px"))
        token = nearest.get("token")
        delta = nearest.get("delta")
        issues.append(
            {
                "category": "间距",
                "severity": "低",
                "location": location,
                "current_observation": (
                    f"实测间距为 {measured}px，未命中 JM AI 间距 token "
                    f"{token}px，偏差 {delta}px。"
                ),
                "spec_expectation": "组件间距应落在 JM AI 间距 token 上，并控制在 1px 容差内。",
                "recommendation": "调整相关元素间距到最近的规范 token。",
                "confidence": 0.85,
                "bbox": None,
                "rule_source": "spacing_measurement",
            }
        )
    return issues


def _sample_bbox(sample: dict[str, Any]) -> list[int] | None:
    x = sample.get("x")
    y = sample.get("y")
    if not isinstance(x, int) or not isinstance(y, int):
        return None
    return [max(0, x - 12), max(0, y - 12), 24, 24]


def _normalize_issue(issue: Any, image_size: tuple[int, int]) -> dict[str, Any]:
    if not isinstance(issue, dict):
        issue = {"current_observation": str(issue)}
    output = dict(issue)
    output.setdefault("category", "其他")
    output.setdefault("severity", "中")
    output.setdefault("location", output.get("current_observation") or "问题")
    output.setdefault("current_observation", "")
    output.setdefault("spec_expectation", "")
    output.setdefault("recommendation", "")
    output.setdefault("confidence", 0.6)
    if not _trusted_bbox(output, image_size):
        if output.get("bbox") is not None:
            output["bbox_rule_status"] = "dropped_untrusted"
        output["bbox"] = None
    return output


def _trusted_bbox(issue: dict[str, Any], image_size: tuple[int, int]) -> bool:
    bbox = _bbox(issue.get("bbox"))
    if bbox is None:
        return False
    width, height = image_size
    x, y, w, h = bbox
    if x < 0 or y < 0 or x + w > width * 1.03 or y + h > height * 1.03:
        return False
    center_x = x + w / 2
    center_y = y + h / 2
    text = _issue_text(issue)
    if "右下" in text and (center_x < width * 0.55 or center_y < height * 0.55):
        return False
    if "右上" in text and (center_x < width * 0.55 or center_y > height * 0.45):
        return False
    if "左下" in text and (center_x > width * 0.45 or center_y < height * 0.55):
        return False
    if "左上" in text and (center_x > width * 0.45 or center_y > height * 0.45):
        return False
    return True


def _upsert_issue(issues: list[dict[str, Any]], rule_issue: dict[str, Any]) -> None:
    match = _find_matching_issue(issues, rule_issue)
    if match is None:
        issues.append(rule_issue)
        return
    match["severity"] = _higher_severity(match.get("severity"), rule_issue.get("severity"))
    match["current_observation"] = _join_sentences(
        match.get("current_observation"),
        rule_issue.get("current_observation"),
    )
    for key in ["spec_expectation", "recommendation", "confidence", "rule_source"]:
        match[key] = rule_issue.get(key, match.get(key))
    if not match.get("bbox") and rule_issue.get("bbox"):
        match["bbox"] = rule_issue["bbox"]


def _find_matching_issue(
    issues: list[dict[str, Any]],
    rule_issue: dict[str, Any],
) -> dict[str, Any] | None:
    rule_location = _normalized(rule_issue.get("location"))
    rule_kind = _kind(rule_issue)
    for issue in issues:
        if _kind(issue) != rule_kind:
            continue
        issue_location = _normalized(issue.get("location"))
        if rule_location and issue_location and (
            rule_location in issue_location or issue_location in rule_location
        ):
            return issue
    return None


def _finalize(audit: dict[str, Any]) -> None:
    audit["issues"] = [_final_issue(issue, index) for index, issue in enumerate(audit["issues"], start=1)]
    if audit["issues"]:
        audit["checklist"] = [
            {
                "item": str(issue.get("location") or issue.get("category") or issue.get("id")),
                "status": "不通过",
                "evidence": str(issue.get("current_observation") or ""),
            }
            for issue in audit["issues"]
        ]
        audit["major_issues"] = [
            _issue_summary(issue)
            for issue in audit["issues"]
            if issue.get("severity") in {"高", "中"}
        ]
        audit["overall_conclusion"] = f"规则复核完成：共发现 {len(audit['issues'])} 个 JM AI 设计规范问题。"


def _final_issue(issue: dict[str, Any], index: int) -> dict[str, Any]:
    output = dict(issue)
    output["id"] = f"问题-{index:03d}"
    return output


def _issue_summary(issue: dict[str, Any]) -> str:
    severity = str(issue.get("severity") or "")
    location = str(issue.get("location") or issue.get("current_observation") or "")
    return f"{severity}：{location}" if severity and location else location or severity


def _higher_severity(left: Any, right: Any) -> str:
    left_text = str(left or "低")
    right_text = str(right or "低")
    return left_text if SEVERITY_RANK.get(left_text, 0) >= SEVERITY_RANK.get(right_text, 0) else right_text


def _join_sentences(left: Any, right: Any) -> str:
    left_text = str(left or "").strip()
    right_text = str(right or "").strip()
    if not left_text:
        return right_text
    if not right_text or right_text in left_text:
        return left_text
    return f"{left_text} {right_text}"


def _kind(issue: dict[str, Any]) -> str:
    text = _normalized(f"{issue.get('category', '')} {issue.get('current_observation', '')}")
    if any(token in text for token in ["色彩", "颜色", "color", "token"]):
        return "color"
    if any(token in text for token in ["间距", "spacing", "gap"]):
        return "spacing"
    return text


def _issue_text(issue: dict[str, Any]) -> str:
    return "".join(
        str(issue.get(key) or "")
        for key in ["location", "current_observation", "spec_expectation", "recommendation"]
    )


def _normalized(value: Any) -> str:
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


def _bbox(value: Any) -> tuple[float, float, float, float] | None:
    try:
        if isinstance(value, dict):
            x = float(value["x"])
            y = float(value["y"])
            width = float(value["width"])
            height = float(value["height"])
        elif isinstance(value, (list, tuple)) and len(value) == 4:
            x = float(value[0])
            y = float(value[1])
            width = float(value[2])
            height = float(value[3])
        else:
            return None
    except (KeyError, TypeError, ValueError):
        return None
    if width <= 0 or height <= 0:
        return None
    return x, y, width, height


def _list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]
