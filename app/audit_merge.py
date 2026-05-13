from __future__ import annotations

from copy import deepcopy
from difflib import SequenceMatcher
from typing import Any

from app.model_errors import model_failure


REQUIRED_TOP_LEVEL_KEYS = [
    "screen_context",
    "overall_conclusion",
    "major_issues",
    "passes",
    "issues",
    "sample_points",
    "regions",
    "distances",
    "checklist",
    "cannot_verify",
]
MODEL_ORDER = ["GPT-5.5", "Kimi-K2.6"]
SEVERITY_RANK = {"低": 1, "中": 2, "高": 3}
TEXT_FIELDS = ["current_observation", "spec_expectation", "recommendation", "location"]
MATCH_THRESHOLD = 0.65
BBOX_KEEP = "keep"
BBOX_DROP = "drop"
CATEGORY_ALIASES = {
    "ai标签": "color",
    "color": "color",
    "colour": "color",
    "颜色": "color",
    "颜色和渐变": "color",
    "颜色和状态标签": "color",
    "色彩": "color",
    "色彩和渐变": "color",
    "ai按钮": "button",
    "按钮": "button",
    "button": "button",
    "ai图标和闪光标": "icon",
    "图标": "icon",
    "icon": "icon",
}
GENERIC_ANCHORS = {
    "顶部右上角",
    "顶部操作区",
    "右侧区域",
    "右侧底部",
    "右下角",
    "使用绿色",
    "按钮使用",
    "色渐变",
    "当前选中",
}


def merge_audits(model_audits: list[dict[str, Any]]) -> dict[str, Any]:
    audits = [_with_model(audit, index) for index, audit in enumerate(model_audits)]
    audits.sort(key=lambda audit: _model_index(audit["model"]))

    merged_issues: list[dict[str, Any]] = []
    for audit in audits:
        for raw_issue in _list(audit.get("issues")):
            issue = dict(raw_issue) if isinstance(raw_issue, dict) else {"current_observation": str(raw_issue)}
            issue["_source_models"] = [audit["model"]]
            match = _find_match(merged_issues, issue)
            if match is None:
                merged_issues.append(issue)
            else:
                _merge_issue_into(match, issue)

    final_issues = [_finalize_issue(issue, index) for index, issue in enumerate(merged_issues, start=1)]
    comparison = _comparison([audit["model"] for audit in audits], final_issues, [])

    result = _base_payload(audits)
    result["issues"] = final_issues
    if final_issues:
        result["checklist"] = _checklist_from_issues(final_issues)
    result["major_issues"] = result["major_issues"] or [
        _issue_summary(issue) for issue in final_issues if issue.get("severity") in {"高", "中"}
    ]
    result["overall_conclusion"] = _conclusion(final_issues, comparison)
    result["model_comparison"] = comparison
    return result


def merge_audit_attempts(attempts: list[dict[str, Any]]) -> dict[str, Any]:
    audits: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    for index, attempt in enumerate(attempts):
        model = str(attempt.get("model") or _default_model(index))
        audit = attempt["audit"] if "audit" in attempt else attempt.get("result")
        error = attempt.get("error")
        if isinstance(audit, dict) and error is None and _has_valid_audit_content(audit):
            audits.append(
                {
                    "model": str(audit.get("model") or model),
                    "audit": audit,
                    "image_size": attempt.get("image_size"),
                }
            )
        else:
            failures.append(_failure_from_attempt(model, attempt, error or "unknown error"))

    if not audits:
        if failures and all(failure["error"] == "unknown error" for failure in failures):
            raise RuntimeError("全部模型审核失败：模型未返回有效审核内容")
        raise RuntimeError("全部模型审核失败")

    result = merge_audits(audits)
    result["model_comparison"]["model_failures"] = failures
    if failures:
        result["overall_conclusion"] = f"单模型降级审核：{result['overall_conclusion']}"
    return result


def merge_primary_with_candidates(
    primary_attempt: dict[str, Any],
    candidate_attempts: list[dict[str, Any]],
) -> dict[str, Any]:
    primary = _valid_attempt_audit(primary_attempt, 0)
    candidates = [
        _valid_attempt_audit(attempt, index + 1)
        for index, attempt in enumerate(candidate_attempts)
        if isinstance(attempt.get("audit") if "audit" in attempt else attempt.get("result"), dict)
    ]

    official_issues = [
        _primary_issue(issue, primary["model"])
        for issue in _list(primary.get("issues"))
        if isinstance(issue, dict)
    ]
    review_candidates: list[dict[str, Any]] = []

    for candidate in candidates:
        for raw_issue in _list(candidate.get("issues")):
            if not isinstance(raw_issue, dict):
                continue
            candidate_issue = dict(raw_issue)
            match = _find_match(official_issues, candidate_issue)
            if match is None:
                review_candidates.append(_review_candidate(candidate_issue, candidate["model"]))
                continue
            _promote_primary_issue(match, candidate_issue, candidate["model"])

    result = deepcopy(primary)
    result["issues"] = [
        _finalize_primary_issue(issue, index)
        for index, issue in enumerate(official_issues, start=1)
    ]
    comparison = _comparison(
        [primary["model"]] + [candidate["model"] for candidate in candidates],
        result["issues"],
        [],
    )
    comparison["promoted_issues"] = [
        issue for issue in result["issues"] if issue.get("agreement") == "promoted_candidate"
    ]
    comparison["primary_only_issues"] = [
        issue for issue in result["issues"] if issue.get("agreement") == "primary_only"
    ]
    comparison["review_candidates"] = review_candidates
    result["model_comparison"] = comparison
    return result


def _valid_attempt_audit(attempt: dict[str, Any], index: int) -> dict[str, Any]:
    audit = attempt["audit"] if "audit" in attempt else attempt.get("result")
    if not isinstance(audit, dict) or not _has_valid_audit_content(audit):
        raise RuntimeError("模型未返回有效审核内容")
    model = str(audit.get("model") or attempt.get("model") or _default_model(index))
    image_size = _image_size(attempt.get("image_size") or audit.get("_image_size"))
    return _prepare_audit({**audit, "model": model}, image_size)


def _has_valid_audit_content(audit: dict[str, Any]) -> bool:
    return all(key in audit for key in REQUIRED_TOP_LEVEL_KEYS)


def _primary_issue(issue: dict[str, Any], model: str) -> dict[str, Any]:
    output = deepcopy(issue)
    output["_source_models"] = [model]
    return output


def _promote_primary_issue(
    primary_issue: dict[str, Any],
    candidate_issue: dict[str, Any],
    candidate_model: str,
) -> None:
    primary_issue["_source_models"] = _sort_models(
        _list(primary_issue.get("_source_models")) + [candidate_model]
    )
    primary_issue["severity"] = _higher_severity(
        primary_issue.get("severity"),
        candidate_issue.get("severity"),
    )


def _finalize_primary_issue(issue: dict[str, Any], index: int) -> dict[str, Any]:
    output = {key: value for key, value in issue.items() if key != "_source_models"}
    output.setdefault("id", f"问题-{index:03d}")
    source_models = _sort_models(issue.get("_source_models", []))
    output["source_models"] = source_models
    output["agreement"] = "promoted_candidate" if len(source_models) > 1 else "primary_only"
    return output


def _review_candidate(issue: dict[str, Any], model: str) -> dict[str, Any]:
    output = deepcopy(issue)
    output["source_model"] = model
    return output


def _with_model(audit: dict[str, Any], index: int) -> dict[str, Any]:
    image_size = _image_size(audit.get("image_size") or audit.get("_image_size"))
    if isinstance(audit.get("audit"), dict):
        model = str(audit.get("model") or audit["audit"].get("model") or _default_model(index))
        return _prepare_audit({**audit["audit"], "model": model}, image_size)
    model = str(audit.get("model") or audit.get("source_model") or _default_model(index))
    return _prepare_audit({**audit, "model": model}, image_size)


def _prepare_audit(
    audit: dict[str, Any],
    image_size: tuple[int, int] | None,
) -> dict[str, Any]:
    if image_size is None:
        return audit
    issues = _list(audit.get("issues"))
    prepared = dict(audit)
    prepared["issues"] = [
        _with_transformed_issue_bbox(
            issue,
            _bbox_transform_decision(issue, image_size),
        )
        if isinstance(issue, dict)
        else issue
        for issue in issues
    ]
    return prepared


def _with_transformed_issue_bbox(
    issue: dict[str, Any],
    transform: tuple[float, float] | str,
) -> dict[str, Any]:
    output = dict(issue)
    bbox = _bbox_as_list(output.get("bbox"))
    if bbox is None:
        output["bbox"] = None
    elif transform == BBOX_DROP:
        output["bbox"] = None
    elif transform == BBOX_KEEP:
        output["bbox"] = issue.get("bbox")
    else:
        scale_x, scale_y = transform
        output["bbox"] = _rounded_bbox(
            [
                bbox[0] * scale_x,
                bbox[1] * scale_y,
                bbox[2] * scale_x,
                bbox[3] * scale_y,
            ]
        )
    return output


def _bbox_transform_decision(
    issue: dict[str, Any],
    image_size: tuple[int, int],
) -> tuple[float, float] | str:
    if _bbox(issue.get("bbox")) is None:
        return BBOX_KEEP
    native_score = _position_violation_count([issue], image_size, (1.0, 1.0))
    if native_score == 0:
        return BBOX_KEEP
    return BBOX_DROP


def _default_model(index: int) -> str:
    return MODEL_ORDER[index] if index < len(MODEL_ORDER) else f"model-{index + 1}"


def _model_index(model: str) -> int:
    try:
        return MODEL_ORDER.index(model)
    except ValueError:
        return len(MODEL_ORDER)


def _find_match(issues: list[dict[str, Any]], issue: dict[str, Any]) -> dict[str, Any] | None:
    best_score = 0.0
    best_issue: dict[str, Any] | None = None
    for existing in issues:
        score = _issue_match_score(existing, issue)
        if score > best_score:
            best_score = score
            best_issue = existing
    return best_issue if best_score >= MATCH_THRESHOLD else None


def _same_issue(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return _issue_match_score(left, right) >= MATCH_THRESHOLD


def _issue_match_score(left: dict[str, Any], right: dict[str, Any]) -> float:
    left_bbox = _bbox(left.get("bbox"))
    right_bbox = _bbox(right.get("bbox"))
    anchor_score = _shared_anchor_score(left, right)
    object_score = _text_similarity(_object_signature(left), _object_signature(right))
    semantic_score = _semantic_text_similarity(left, right)
    category_match = _category_match(left, right)

    if _side_conflict(left, right):
        return 0.0
    if _issue_kind_conflict(left, right):
        return 0.0

    if left_bbox and right_bbox:
        if not _bbox_related(left_bbox, right_bbox):
            return 0.0
        if _different_semantic_category(left, right) and semantic_score < 0.55 and anchor_score < 0.6:
            return 0.0
        return 0.75 + min(object_score, 0.2) + min(semantic_score, 0.05)

    if anchor_score >= 0.6 and object_score >= 0.18:
        return 0.8 + min(object_score, 0.15)
    if object_score >= 0.3 and (category_match or semantic_score >= 0.12):
        return 0.72 + min(semantic_score, 0.08)
    if object_score >= 0.3 and category_match and semantic_score >= 0.18:
        return 0.65
    return 0.0


def _semantic_match(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_category = _category_key(left.get("category"))
    right_category = _category_key(right.get("category"))
    if left_category and right_category:
        if left_category == right_category or _text_similarity(left_category, right_category) >= 0.75:
            return True
        return _semantic_text_similarity(left, right) >= 0.7
    return _text_similarity(_semantic_signature(left), _semantic_signature(right)) >= 0.7


def _category_match(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_category = _category_key(left.get("category"))
    right_category = _category_key(right.get("category"))
    return bool(
        left_category
        and right_category
        and (
            left_category == right_category
            or _text_similarity(left_category, right_category) >= 0.75
        )
    )


def _different_semantic_category(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_category = _category_key(left.get("category"))
    right_category = _category_key(right.get("category"))
    return bool(left_category and right_category and left_category != right_category)


def _object_match(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return _text_similarity(_object_signature(left), _object_signature(right)) >= 0.18


def _object_signature(issue: dict[str, Any]) -> str:
    return _normalized_text(
        " ".join(
            str(issue.get(field) or "")
            for field in ["location", "current_observation"]
        )
    )


def _semantic_text_similarity(left: dict[str, Any], right: dict[str, Any]) -> float:
    return _text_similarity(_semantic_signature(left), _semantic_signature(right))


def _category_key(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    normalized = _normalized_text(text)
    if normalized in CATEGORY_ALIASES:
        return CATEGORY_ALIASES[normalized]
    if any(token in text for token in ["color", "colour", "颜色", "色彩", "渐变", "标签"]):
        return "color"
    if any(token in text for token in ["spacing", "间距", "padding", "gap"]):
        return "spacing"
    if any(token in text for token in ["typography", "font", "字体", "字号"]):
        return "typography"
    if any(token in text for token in ["button", "按钮"]):
        return "button"
    if any(token in text for token in ["icon", "图标", "闪光"]):
        return "icon"
    return normalized


def _issue_kind(issue: dict[str, Any]) -> str:
    category = _category_key(issue.get("category"))
    if category in {"color", "spacing", "typography", "button", "icon"}:
        return category
    text = _normalized_text(
        " ".join(
            str(issue.get(field) or "")
            for field in ["current_observation", "spec_expectation", "recommendation"]
        )
    )
    if any(token in text for token in ["颜色", "色彩", "渐变", "橙色", "绿色", "红色", "紫色", "主色"]):
        return "color"
    if any(token in text for token in ["间距", "内边距", "外边距", "padding", "gap"]):
        return "spacing"
    if any(token in text for token in ["字号", "字体", "字重", "typography", "font"]):
        return "typography"
    if any(token in text for token in ["按钮"]):
        return "button"
    if any(token in text for token in ["图标", "闪光"]):
        return "icon"
    return ""


def _issue_kind_conflict(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_kind = _issue_kind(left)
    right_kind = _issue_kind(right)
    if not left_kind or not right_kind or left_kind == right_kind:
        return False
    visual_kinds = {"color", "button", "icon"}
    if left_kind in visual_kinds and right_kind in visual_kinds:
        return False
    return True


def _semantic_signature(issue: dict[str, Any]) -> str:
    return " ".join(
        str(issue.get(field) or "")
        for field in ["current_observation", "spec_expectation", "recommendation"]
        if issue.get(field)
    )


def _bbox(value: Any) -> dict[str, float] | None:
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
    return {"x": x, "y": y, "width": width, "height": height}


def _bbox_as_list(value: Any) -> list[float] | None:
    bbox = _bbox(value)
    if bbox is None:
        return None
    return [bbox["x"], bbox["y"], bbox["width"], bbox["height"]]


def _image_size(value: Any) -> tuple[int, int] | None:
    if (
        isinstance(value, (list, tuple))
        and len(value) == 2
        and all(isinstance(item, (int, float)) for item in value)
        and value[0] > 0
        and value[1] > 0
    ):
        return int(value[0]), int(value[1])
    return None


def _iou(left: dict[str, float], right: dict[str, float]) -> float:
    left_x2 = left["x"] + left["width"]
    left_y2 = left["y"] + left["height"]
    right_x2 = right["x"] + right["width"]
    right_y2 = right["y"] + right["height"]
    overlap_w = max(0.0, min(left_x2, right_x2) - max(left["x"], right["x"]))
    overlap_h = max(0.0, min(left_y2, right_y2) - max(left["y"], right["y"]))
    intersection = overlap_w * overlap_h
    union = left["width"] * left["height"] + right["width"] * right["height"] - intersection
    return intersection / union if union else 0.0


def _bbox_related(left: dict[str, float], right: dict[str, float]) -> bool:
    return _iou(left, right) >= 0.2 or _bbox_containment(left, right) >= 0.6


def _bbox_containment(left: dict[str, float], right: dict[str, float]) -> float:
    left_x2 = left["x"] + left["width"]
    left_y2 = left["y"] + left["height"]
    right_x2 = right["x"] + right["width"]
    right_y2 = right["y"] + right["height"]
    overlap_w = max(0.0, min(left_x2, right_x2) - max(left["x"], right["x"]))
    overlap_h = max(0.0, min(left_y2, right_y2) - max(left["y"], right["y"]))
    intersection = overlap_w * overlap_h
    smaller = min(left["width"] * left["height"], right["width"] * right["height"])
    return intersection / smaller if smaller else 0.0


def _position_violation_count(
    issues: list[dict[str, Any]],
    image_size: tuple[int, int],
    scale: tuple[float, float],
) -> int:
    width, height = image_size
    scale_x, scale_y = scale
    violations = 0
    for issue in issues:
        bbox = _bbox_as_list(issue.get("bbox"))
        if bbox is None:
            continue
        x, y, w, h = bbox
        center_x = (x + w / 2) * scale_x
        center_y = (y + h / 2) * scale_y
        text = _object_signature(issue)
        has_left = "左" in text
        has_right = "右" in text
        has_top = "顶部" in text or "上角" in text or "右上" in text or "左上" in text
        has_bottom = "底部" in text or "下角" in text or "右下" in text or "左下" in text
        if "右下" in text and (center_x < width * 0.55 or center_y < height * 0.55):
            violations += 1
        if "右上" in text and (center_x < width * 0.55 or center_y > height * 0.45):
            violations += 1
        if "左下" in text and (center_x > width * 0.45 or center_y < height * 0.55):
            violations += 1
        if "左上" in text and (center_x > width * 0.45 or center_y > height * 0.45):
            violations += 1
        if has_right and not has_left and center_x < width * 0.55:
            violations += 1
        if has_left and not has_right and center_x > width * 0.45:
            violations += 1
        if has_bottom and not has_top and center_y < height * 0.45:
            violations += 1
        if has_top and not has_bottom and center_y > height * 0.45:
            violations += 1
    return violations


def _out_of_bounds_count(
    issues: list[dict[str, Any]],
    image_size: tuple[int, int],
    scale: tuple[float, float],
) -> int:
    width, height = image_size
    scale_x, scale_y = scale
    count = 0
    for issue in issues:
        bbox = _bbox_as_list(issue.get("bbox"))
        if bbox is None:
            continue
        x, y, w, h = bbox
        if x * scale_x < 0 or y * scale_y < 0:
            count += 1
        if (x + w) * scale_x > width * 1.03 or (y + h) * scale_y > height * 1.03:
            count += 1
    return count


def _location_similarity(left: Any, right: Any) -> float:
    left_text = _normalized_text(left)
    right_text = _normalized_text(right)
    return _text_similarity(left_text, right_text)


def _text_similarity(left_text: str, right_text: str) -> float:
    if not left_text or not right_text:
        return 0.0
    if left_text in right_text or right_text in left_text:
        return 1.0
    return SequenceMatcher(None, left_text, right_text).ratio()


def _normalized_text(value: Any) -> str:
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


def _shared_anchor_score(left: dict[str, Any], right: dict[str, Any]) -> float:
    anchor = _longest_common_substring(_object_signature(left), _object_signature(right))
    if len(anchor) < 4 or _is_generic_anchor(anchor):
        return 0.0
    return min(1.0, len(anchor) / 8)


def _longest_common_substring(left: str, right: str) -> str:
    best = ""
    for left_index in range(len(left)):
        for right_index in range(len(right)):
            offset = 0
            while (
                left_index + offset < len(left)
                and right_index + offset < len(right)
                and left[left_index + offset] == right[right_index + offset]
            ):
                offset += 1
            if offset > len(best):
                best = left[left_index : left_index + offset]
    return best


def _is_generic_anchor(value: str) -> bool:
    if value in GENERIC_ANCHORS:
        return True
    if not any(
        token in value
        for token in [
            "套餐",
            "模型",
            "文件",
            "ppt",
            "chatexcel",
            "excelpro",
            "新对话",
            "输入框",
            "闪光",
            "图标",
            "头像",
            "皇冠",
        ]
    ):
        return True
    return value.startswith(("顶部", "右侧", "左侧", "底部")) and not any(
        token in value for token in ["套餐", "模型", "文件", "ppt", "chatexcel", "excelpro"]
    )


def _side_conflict(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_text = _object_signature(left)
    right_text = _object_signature(right)
    if ("左" in left_text and "右" in right_text) or ("右" in left_text and "左" in right_text):
        return True
    if (
        ("顶部" in left_text or "上角" in left_text)
        and ("底部" in right_text or "下角" in right_text)
    ) or (
        ("底部" in left_text or "下角" in left_text)
        and ("顶部" in right_text or "上角" in right_text)
    ):
        return True
    return False


def _merge_issue_into(target: dict[str, Any], source: dict[str, Any]) -> None:
    target["_source_models"] = _sort_models(target.get("_source_models", []) + source.get("_source_models", []))
    target["severity"] = _higher_severity(target.get("severity"), source.get("severity"))
    target["bbox"] = _choose_bbox(target.get("bbox"), source.get("bbox"))
    for field in TEXT_FIELDS:
        target[field] = _longer_text(target.get(field), source.get(field))
    for key, value in source.items():
        if key not in target and key != "_source_models":
            target[key] = value


def _higher_severity(left: Any, right: Any) -> str:
    left_text = str(left or "低")
    right_text = str(right or "低")
    return left_text if SEVERITY_RANK.get(left_text, 0) >= SEVERITY_RANK.get(right_text, 0) else right_text


def _choose_bbox(left: Any, right: Any) -> Any:
    left_bbox = _bbox(left)
    right_bbox = _bbox(right)
    if left_bbox and not right_bbox:
        return left
    if right_bbox and not left_bbox:
        return right
    if not left_bbox and not right_bbox:
        return left or right
    left_area = left_bbox["width"] * left_bbox["height"]
    right_area = right_bbox["width"] * right_bbox["height"]
    return left if left_area <= right_area else right


def _longer_text(left: Any, right: Any) -> Any:
    if left is None:
        return right
    if right is None:
        return left
    return left if len(str(left)) >= len(str(right)) else right


def _rounded_bbox(value: list[float]) -> list[float]:
    return [round(item, 6) for item in value]


def _finalize_issue(issue: dict[str, Any], index: int) -> dict[str, Any]:
    output = {key: value for key, value in issue.items() if key != "_source_models"}
    source_models = _sort_models(issue.get("_source_models", []))
    output["id"] = f"问题-{index:03d}"
    output["source_models"] = source_models
    output["agreement"] = _agreement(source_models)
    return output


def _agreement(source_models: list[str]) -> str:
    has_gpt = MODEL_ORDER[0] in source_models
    has_kimi = MODEL_ORDER[1] in source_models
    if has_gpt and has_kimi:
        return "both"
    if has_gpt:
        return "gpt_only"
    if has_kimi:
        return "kimi_only"
    return "model_only"


def _sort_models(models: Any) -> list[str]:
    return sorted({str(model) for model in _list(models)}, key=_model_index)


def _failure_from_attempt(model: str, attempt: dict[str, Any], error: Any) -> dict[str, Any]:
    if "error_type" in attempt or "retriable" in attempt or "degraded" in attempt:
        return {
            "model": model,
            "error": _short_error(error),
            "error_type": str(attempt.get("error_type") or "unknown"),
            "retriable": bool(attempt.get("retriable")),
            "degraded": bool(attempt.get("degraded", True)),
        }
    return model_failure(model, error)


def _comparison(models: list[str], issues: list[dict[str, Any]], failures: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "models": _sort_models(models),
        "agreed_issues": [issue for issue in issues if issue.get("agreement") == "both"],
        "gpt_only_issues": [issue for issue in issues if issue.get("agreement") == "gpt_only"],
        "kimi_only_issues": [issue for issue in issues if issue.get("agreement") == "kimi_only"],
        "conflicts": [],
        "model_failures": failures,
    }


def _base_payload(audits: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {key: [] for key in REQUIRED_TOP_LEVEL_KEYS}
    result["screen_context"] = _first_text(audit.get("screen_context") for audit in audits)
    result["overall_conclusion"] = ""
    for key in REQUIRED_TOP_LEVEL_KEYS:
        if key in {"screen_context", "overall_conclusion", "issues"}:
            continue
        result[key] = [item for audit in audits for item in _list(audit.get(key))]
    return result


def _checklist_from_issues(issues: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [
        {
            "item": str(issue.get("location") or issue.get("category") or issue.get("id") or "问题"),
            "status": "不通过",
            "evidence": str(issue.get("current_observation") or ""),
        }
        for issue in issues
    ]


def _conclusion(issues: list[dict[str, Any]], comparison: dict[str, Any]) -> str:
    if not issues:
        return "双模型审核未发现明确 JM AI 设计规范问题。"
    agreed_count = len(comparison["agreed_issues"])
    supplemental_count = len(comparison["gpt_only_issues"]) + len(
        comparison["kimi_only_issues"]
    )
    return (
        f"双模型本地合并完成：共发现 {len(issues)} 个 JM AI 设计规范问题，"
        f"双方共同确认 {agreed_count} 个，单模型补充 {supplemental_count} 个。"
    )


def _issue_summary(issue: dict[str, Any]) -> str:
    severity = str(issue.get("severity") or "")
    location = str(issue.get("location") or issue.get("current_observation") or "")
    return f"{severity}：{location}" if severity and location else location or severity


def _first_text(values: Any) -> str:
    for value in values:
        if value:
            return str(value)
    return ""


def _list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _short_error(error: Any) -> str:
    return str(error).strip().replace("\n", " ")[:120] or "unknown error"
