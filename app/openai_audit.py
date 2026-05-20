from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any, Protocol

from PIL import Image

from app.b_design_router import (
    component_names,
    has_selected_b_design_components,
    is_b_design_label,
    normalize_b_design_applicability,
    select_b_design_spec_context,
)
from app.prompt_builder import (
    SCHEMA_VERSION,
    build_audit_prompt,
    build_b_design_applicability_prompt,
    build_kimi_light_audit_prompt,
    build_light_audit_prompt,
    prompt_metadata,
)


REQUIRED_KEYS = {
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
}
ARRAY_KEYS = REQUIRED_KEYS - {"screen_context", "overall_conclusion"}
CHAT_AUDIT_MAX_TOKENS = 32768
CHAT_AUDIT_LIGHT_MAX_TOKENS = 8192
KIMI_CHAT_AUDIT_LIGHT_MAX_TOKENS = 16384
B_DESIGN_APPLICABILITY_MAX_TOKENS = 4096
SEVERITY_MAP = {
    "critical": "高",
    "high": "高",
    "medium": "中",
    "warning": "中",
    "low": "低",
    "info": "低",
}
TEXT_TRANSLATIONS = {
    "ChatExcel Max product interface with left sidebar": "ChatExcel Max 产品界面，包含左侧导航",
    "The interface uses non-compliant orange and green accents.": "界面使用了不符合规范的橙色和绿色强调色。",
    "Color and gradients": "颜色与渐变",
    "Color - Brand accent": "颜色 - 品牌强调色",
    "Color - Functional icon": "颜色 - 功能图标",
    "Color - Commercial action": "颜色 - 商业操作",
    "Typography - Font size": "字体 - 字号",
    "Spacing - Layout": "间距 - 布局",
    "AI Buttons - Icon color": "AI 按钮 - 图标颜色",
    "AI Tags - Style": "AI 标签 - 样式",
    "Header - Hierarchy": "头部 - 层级",
    "AI Icon - Sparkle": "AI 图标 - 星光标记",
    "Top right header area": "右上角头部区域",
    "Orange invite button is not a JM AI color token.": "橙色邀请按钮不是 JM AI 颜色 token。",
    "Primary action buttons should use JM AI purple tokens.": "主要操作按钮应使用 JM AI 紫色 token。",
    "Change the button to #6B36FA.": "将按钮改为 #6B36FA。",
    "Purple title text appears consistent with JM AI primary colors.": "紫色标题文本看起来符合 JM AI 主色。",
    "Primary action buttons use AI tokens": "主要操作按钮使用 AI token",
    "Orange button is off-token": "橙色按钮偏离 token",
    "Exact font family": "精确字体族",
    "Screenshot cannot expose CSS font stack": "截图无法暴露 CSS 字体栈",
    "Color and gradients": "颜色与渐变",
    "Top right header area - 续费套餐 pill/tag": "右上角头部区域 - 续费套餐标签",
    "ChatExcel Max AI Excel processing product interface. Contains left navigation sidebar, main content area with feature cards (multi-file/sheet processing, large file handling, private computing), official capability demonstration grid (Excel processing, data operations, data analysis, chart generation), industry example tags, and right-side chat panel with file upload zone and input area. Top header includes product branding, download client button, invite-to-earn button, user avatar, and续费套餐 (renew package) pill.": "ChatExcel Max 的 AI Excel 处理产品界面，包含左侧导航、中部功能卡片、官方能力演示、行业样例标签，以及右侧带文件上传区和输入框的对话面板。顶部包含产品品牌、下载客户端、邀好友赚套餐、用户头像和续费套餐入口。",
    "The interface uses a mix of JM AI-compliant purple branding alongside non-compliant orange/red accent colors for key commercial actions (邀好友赚套餐/renew package). Green is used for functional checkmarks rather than brand accents. Several header hierarchy and spacing observations noted. The right panel uses JM AI purple gradient appropriately. Left navigation uses neutral colors consistent with standard UI but lacks clear JM AI brand accent on active state from visible evidence.": "界面同时使用了符合 JM AI 的紫色品牌元素，以及不符合规范的橙红色商业操作入口（邀好友赚套餐/续费套餐）。功能勾选标记使用了绿色而非品牌强调色；头部层级和间距仍有需要确认的观察项。右侧面板的紫色渐变使用较合适，但左侧导航的激活状态缺少明确的 JM AI 品牌强调。",
    "Right panel 'ChatExcel Max' header uses purple gradient background consistent with JM AI purple branding": "右侧 ChatExcel Max 头部使用紫色渐变背景，符合 JM AI 紫色品牌表达",
    "Main headline '多文件多Sheet、大文件' uses purple text (#6B36FA or similar) for emphasis portion, consistent with ai/ai-normal token": "主标题中的“多文件多Sheet、大文件”使用紫色强调，接近 ai/ai-normal token",
}


class AuditModelError(Exception):
    pass


class _ResponsesClient(Protocol):
    def create(self, **kwargs: Any) -> Any:
        ...


class _ChatCompletionsClient(Protocol):
    def create(self, **kwargs: Any) -> Any:
        ...


class _ChatClient(Protocol):
    completions: _ChatCompletionsClient


class _OpenAIClient(Protocol):
    responses: _ResponsesClient
    chat: _ChatClient


def _strict_object_schema(properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(properties),
        "properties": properties,
    }


def _nullable_string() -> dict[str, Any]:
    return {"anyOf": [{"type": "string"}, {"type": "null"}]}


def _nullable_bbox() -> dict[str, Any]:
    return {
        "anyOf": [
            {
                "type": "array",
                "items": {"type": "number"},
                "minItems": 4,
                "maxItems": 4,
            },
            {"type": "null"},
        ]
    }


def _image_size(path: Path) -> tuple[int, int]:
    with Image.open(path) as image:
        return image.size


def audit_json_schema() -> dict[str, Any]:
    return {
        "type": "json_schema",
        "name": SCHEMA_VERSION.replace("-", "_"),
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": sorted(REQUIRED_KEYS),
            "properties": {
                "screen_context": {"type": "string"},
                "overall_conclusion": {"type": "string"},
                "major_issues": {"type": "array", "items": {"type": "string"}},
                "passes": {"type": "array", "items": {"type": "string"}},
                "issues": {
                    "type": "array",
                    "items": _strict_object_schema(
                        {
                            "id": {"type": "string"},
                            "category": {"type": "string"},
                            "severity": {"type": "string", "enum": ["高", "中", "低"]},
                            "location": {"type": "string"},
                            "current_observation": {"type": "string"},
                            "spec_expectation": {"type": "string"},
                            "recommendation": {"type": "string"},
                            "confidence": {
                                "type": "number",
                                "minimum": 0,
                                "maximum": 1,
                            },
                            "bbox": _nullable_bbox(),
                            "rule_source_type": _nullable_string(),
                            "rule_source_ref": _nullable_string(),
                        }
                    ),
                },
                "sample_points": {
                    "type": "array",
                    "items": _strict_object_schema(
                        {
                            "label": {"type": "string"},
                            "x": {"type": "integer"},
                            "y": {"type": "integer"},
                        }
                    ),
                },
                "regions": {
                    "type": "array",
                    "items": _strict_object_schema(
                        {
                            "id": {"type": "string"},
                            "title": _nullable_string(),
                            "bbox": _nullable_bbox(),
                            "role_hint": _nullable_string(),
                            "measure_kind": {
                                "type": "string",
                                "enum": [
                                    "component",
                                    "spacing",
                                    "gap",
                                    "padding",
                                    "text",
                                    "typography",
                                ],
                            },
                        }
                    ),
                },
                "distances": {
                    "type": "array",
                    "items": _strict_object_schema(
                        {
                            "id": {"type": "string"},
                            "title": _nullable_string(),
                            "from": {"type": "string"},
                            "to": {"type": "string"},
                            "axis": {"type": "string", "enum": ["x", "y"]},
                        }
                    ),
                },
                "checklist": {
                    "type": "array",
                    "items": _strict_object_schema(
                        {
                            "item": {"type": "string"},
                            "status": {
                                "type": "string",
                                "enum": ["通过", "不通过", "无法确认"],
                            },
                            "evidence": _nullable_string(),
                        }
                    ),
                },
                "cannot_verify": {
                    "type": "array",
                    "items": _strict_object_schema(
                        {
                            "item": {"type": "string"},
                            "reason": {"type": "string"},
                        }
                    ),
                },
            },
        },
    }


def b_design_applicability_json_schema() -> dict[str, Any]:
    return {
        "type": "json_schema",
        "name": "b_design_applicability",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "screen_context",
                "applicability",
                "matched_components",
                "reason",
                "cannot_verify",
            ],
            "properties": {
                "screen_context": {"type": "string"},
                "applicability": {"type": "string", "enum": ["strong", "weak", "none"]},
                "matched_components": {
                    "type": "array",
                    "items": _strict_object_schema(
                        {
                            "component_id": {"type": "string"},
                            "component_name": {"type": "string"},
                            "confidence": {
                                "type": "number",
                                "minimum": 0,
                                "maximum": 1,
                            },
                            "applicability": {
                                "type": "string",
                                "enum": ["strong", "weak", "none"],
                            },
                            "evidence": {"type": "string"},
                        }
                    ),
                },
                "reason": {"type": "string"},
                "cannot_verify": {"type": "array", "items": {"type": "string"}},
            },
        },
    }


def parse_audit_json(
    text: str,
    allow_missing_arrays: bool = False,
    image_size: tuple[int, int] | None = None,
    audit_spec_label: str = "JM AI 设计规范",
) -> dict[str, Any]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AuditModelError("模型返回的 JSON 无法解析") from exc

    if not isinstance(data, dict):
        raise AuditModelError("模型返回的 JSON 必须是对象")

    if allow_missing_arrays:
        data = _normalize_chat_audit_payload(
            data,
            image_size=image_size,
            audit_spec_label=audit_spec_label,
        )
        _reject_empty_chat_audit(data)

    missing = REQUIRED_KEYS - set(data)
    if allow_missing_arrays:
        for key in sorted(missing & ARRAY_KEYS):
            data[key] = []
        missing = REQUIRED_KEYS - set(data)
    if missing:
        raise AuditModelError(f"模型返回缺少字段: {', '.join(sorted(missing))}")

    for key in ARRAY_KEYS:
        if not isinstance(data[key], list):
            raise AuditModelError(f"模型返回字段必须是数组: {key}")

    return data


def parse_strict_audit_json(text: str) -> dict[str, Any]:
    return parse_audit_json(text, allow_missing_arrays=False)


def _with_prompt_metadata(
    audit: dict[str, Any],
    audit_spec_label: str = "JM AI 设计规范",
) -> dict[str, Any]:
    return {**audit, **prompt_metadata(audit_spec_label)}


def parse_lenient_chat_audit_json(
    text: str,
    image_size: tuple[int, int] | None = None,
    audit_spec_label: str = "JM AI 设计规范",
) -> dict[str, Any]:
    return parse_audit_json(
        text,
        allow_missing_arrays=True,
        image_size=image_size,
        audit_spec_label=audit_spec_label,
    )


def _reject_empty_chat_audit(data: dict[str, Any]) -> None:
    evidence_keys = [
        "major_issues",
        "passes",
        "issues",
        "sample_points",
        "regions",
        "distances",
        "checklist",
        "cannot_verify",
    ]
    has_evidence = any(data.get(key) for key in evidence_keys)
    generic_context = str(data.get("screen_context") or "").strip() in {
        "",
        ":",
        "模型未返回页面识别",
    }
    generic_conclusion = _is_generic_conclusion(data.get("overall_conclusion"))
    if not has_evidence and generic_context and generic_conclusion:
        raise AuditModelError("模型未返回有效审核内容，请重新审核")


def _normalize_chat_audit_payload(
    data: dict[str, Any],
    image_size: tuple[int, int] | None = None,
    audit_spec_label: str = "JM AI 设计规范",
) -> dict[str, Any]:
    normalized = dict(data)
    label = _audit_spec_phrase(audit_spec_label)
    if not normalized.get("screen_context"):
        normalized["screen_context"] = _first_text(
            normalized.get("page_context"),
            normalized.get("screen"),
            normalized.get("interface"),
            _infer_screen_context(normalized),
            "模型未返回页面识别",
        )
    if not normalized.get("overall_conclusion"):
        normalized["overall_conclusion"] = _normalize_conclusion(
            normalized.get("conclusion"),
            normalized.get("summary"),
            normalized.get("audit_summary"),
            audit_spec_label=audit_spec_label,
        )
    else:
        normalized["overall_conclusion"] = _normalize_conclusion(
            normalized.get("overall_conclusion"),
            audit_spec_label=audit_spec_label,
        )

    issues = _normalize_issue_list(
        normalized.get("issues"),
        image_size=image_size,
        audit_spec_label=audit_spec_label,
    )
    for key in ["problems", "violations", "findings"]:
        issues.extend(
            _normalize_issue_list(
                normalized.get(key),
                image_size=image_size,
                audit_spec_label=audit_spec_label,
            )
        )
    issues.extend(
        _issues_from_sections(
            normalized,
            image_size=image_size,
            audit_spec_label=audit_spec_label,
        )
    )
    issues.extend(
        _issues_from_notes(
            normalized,
            image_size=image_size,
            audit_spec_label=audit_spec_label,
        )
    )
    category_issues = _issues_from_categories(
        normalized.get("categories"),
        image_size=image_size,
        audit_spec_label=audit_spec_label,
    )
    if category_issues:
        issues = category_issues if not issues else issues + category_issues
    normalized["issues"] = issues

    if "major_issues" not in normalized or not normalized.get("major_issues"):
        normalized["major_issues"] = [
            issue["current_observation"]
            for issue in issues
            if issue.get("severity") in {"高", "中"} and issue.get("current_observation")
        ][:8]
    elif not isinstance(normalized["major_issues"], list):
        normalized["major_issues"] = [normalized["major_issues"]]
    if issues and _is_generic_conclusion(normalized.get("overall_conclusion")):
        normalized["overall_conclusion"] = f"存在 {len(issues)} 个需要调整的{label}问题。"
    normalized["checklist"] = _normalize_checklist(normalized.get("checklist"))
    if issues and not _has_visible_checklist_items(normalized["checklist"]):
        normalized["checklist"] = _checklist_from_issues(issues)
    if not issues:
        issues = _issues_from_failed_checklist(
            normalized.get("checklist"),
            audit_spec_label=audit_spec_label,
        )
        normalized["issues"] = issues
        if not normalized.get("major_issues"):
            normalized["major_issues"] = [
                issue["current_observation"]
                for issue in issues
                if issue.get("current_observation")
            ][:8]
        if issues and _is_generic_conclusion(normalized.get("overall_conclusion")):
            normalized["overall_conclusion"] = f"存在 {len(issues)} 个需要调整的{label}问题。"
    normalized["passes"] = _normalize_passes(normalized)
    normalized["cannot_verify"] = _normalize_cannot_verify(normalized)
    normalized["regions"] = _normalize_regions(normalized, image_size=image_size)
    normalized["distances"] = _normalize_distances(normalized)
    normalized["sample_points"] = _normalize_sample_points(
        normalized.get("sample_points"),
        image_size=image_size,
    )
    _localize_audit_payload(normalized)
    for key in ARRAY_KEYS:
        if key not in normalized or normalized[key] is None:
            normalized[key] = []
        elif not isinstance(normalized[key], list):
            normalized[key] = [normalized[key]]
    return normalized


def _first_text(*values: Any) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _localize_text(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text:
        return text
    if text in TEXT_TRANSLATIONS:
        return TEXT_TRANSLATIONS[text]
    for source, target in TEXT_TRANSLATIONS.items():
        if source in text:
            text = text.replace(source, target)
    return text


def _localize_audit_payload(data: dict[str, Any]) -> None:
    for key in ["screen_context", "overall_conclusion"]:
        data[key] = _localize_text(data.get(key))
    data["major_issues"] = [_localize_text(item) for item in _list_or_empty(data.get("major_issues"))]
    data["passes"] = [_localize_text(item) for item in _list_or_empty(data.get("passes"))]
    for issue in _list_or_empty(data.get("issues")):
        if not isinstance(issue, dict):
            continue
        for key in [
            "category",
            "location",
            "current_observation",
            "spec_expectation",
            "recommendation",
        ]:
            issue[key] = _localize_text(issue.get(key))
    for item in _list_or_empty(data.get("checklist")):
        if not isinstance(item, dict):
            continue
        for key in ["item", "evidence"]:
            item[key] = _localize_text(item.get(key))
    for item in _list_or_empty(data.get("cannot_verify")):
        if not isinstance(item, dict):
            continue
        for key in ["item", "reason"]:
            item[key] = _localize_text(item.get(key))


def _infer_screen_context(data: dict[str, Any]) -> str:
    image_size = data.get("input_image_size")
    if isinstance(image_size, dict):
        width = image_size.get("width")
        height = image_size.get("height")
        if width and height:
            return f"上传界面截图（{width}×{height}px）"
    for key in ["page_title", "title", "product", "app"]:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _audit_spec_phrase(audit_spec_label: str) -> str:
    label = (audit_spec_label or "JM AI 设计规范").strip()
    if label == "JM AI 设计规范":
        return " JM AI 设计规范"
    return label


def _normalize_conclusion(
    *values: Any,
    audit_spec_label: str = "JM AI 设计规范",
) -> str:
    label = _audit_spec_phrase(audit_spec_label)
    for value in values:
        if isinstance(value, str) and value.strip():
            raw = value.strip()
            lowered = raw.lower()
            if lowered in {"pass", "passed"}:
                return f"整体符合{label}。"
            if lowered in {"fail", "failed"}:
                return f"存在不符合{label}的问题。"
            if lowered in {"pass_with_cautions", "warning", "warnings"}:
                return "整体可识别，但存在需要调整的设计规范问题。"
            return raw
        if isinstance(value, dict) and value:
            return "模型返回了审核摘要，存在需要进一步确认的设计规范问题。"
    return "模型已完成审核。"


def _is_generic_conclusion(value: Any) -> bool:
    text = str(value or "").strip()
    return text in {"", "模型已完成审核。", "模型返回了审核摘要，存在需要进一步确认的设计规范问题。"}


def _checklist_from_issues(issues: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [
        {
            "item": f"{issue.get('category') or '问题'}：{issue.get('location') or issue.get('id')}",
            "status": "不通过",
            "evidence": str(issue.get("current_observation") or ""),
        }
        for issue in issues[:12]
    ]


def _normalize_checklist(value: Any) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    for item in _list_or_empty(value):
        if not isinstance(item, dict):
            continue
        status = _normalize_check_status(item.get("status"))
        output.append(
            {
                "item": _first_text(item.get("item"), item.get("title"), item.get("id")),
                "status": status,
                "evidence": _first_text(item.get("evidence"), item.get("reason"), item.get("note")),
            }
        )
    return output


def _normalize_check_status(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"通过", "pass", "passed", "ok", "yes"}:
        return "通过"
    if text in {"不通过", "fail", "failed", "no", "error", "warning"}:
        return "不通过"
    return "无法确认"


def _has_visible_checklist_items(items: list[dict[str, str]]) -> bool:
    return any(item.get("status") in {"通过", "不通过"} for item in items)


def _issues_from_failed_checklist(
    value: Any,
    audit_spec_label: str = "JM AI 设计规范",
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    label = _audit_spec_phrase(audit_spec_label)
    for item in _list_or_empty(value):
        if not isinstance(item, dict) or item.get("status") != "不通过":
            continue
        issue = _normalize_issue(
            {
                "id": f"check-{len(issues) + 1:03d}",
                "category": "Checklist",
                "severity": "warning",
                "title": item.get("item"),
                "description": item.get("evidence"),
                "recommendation": f"请按{label}逐项调整。",
            },
            "Checklist",
            len(issues) + 1,
            audit_spec_label=audit_spec_label,
        )
        if issue:
            issues.append(issue)
    return issues


def _issues_from_categories(
    value: Any,
    image_size: tuple[int, int] | None = None,
    audit_spec_label: str = "JM AI 设计规范",
) -> list[dict[str, Any]]:
    if not isinstance(value, dict):
        return []
    issues: list[dict[str, Any]] = []
    for category, details in value.items():
        if not isinstance(details, dict):
            continue
        status = str(details.get("status") or "").lower()
        items = details.get("items")
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            if status == "pass" and not item.get("issue"):
                continue
            issue = _normalize_issue(
                item,
                str(category),
                len(issues) + 1,
                image_size=image_size,
                audit_spec_label=audit_spec_label,
            )
            if issue:
                issues.append(issue)
    return issues


def _issues_from_sections(
    data: dict[str, Any],
    image_size: tuple[int, int] | None = None,
    audit_spec_label: str = "JM AI 设计规范",
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for key, value in data.items():
        if key in REQUIRED_KEYS or key in {"categories", "evidence_requests"}:
            continue
        if not isinstance(value, dict):
            continue
        section_issues = value.get("issues")
        if not isinstance(section_issues, list):
            continue
        for item in section_issues:
            if not isinstance(item, dict):
                continue
            issue = _normalize_issue(
                item,
                str(item.get("category") or key),
                len(issues) + 1,
                image_size=image_size,
                audit_spec_label=audit_spec_label,
            )
            if issue:
                issues.append(issue)
    return issues


def _issues_from_notes(
    data: dict[str, Any],
    image_size: tuple[int, int] | None = None,
    audit_spec_label: str = "JM AI 设计规范",
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for key, value in data.items():
        if not isinstance(value, dict):
            continue
        for note in _list_or_empty(value.get("notes")):
            if not isinstance(note, dict) or not _note_is_issue(note):
                continue
            issue = _normalize_issue(
                {
                    "id": note.get("id"),
                    "category": key,
                    "severity": "warning",
                    "title": note.get("element"),
                    "description": note.get("observation"),
                    "bbox": note.get("bbox"),
                    "inference": note.get("note"),
                },
                key,
                len(issues) + 1,
                image_size=image_size,
                audit_spec_label=audit_spec_label,
            )
            if issue:
                issues.append(issue)
    return issues


def _note_is_issue(note: dict[str, Any]) -> bool:
    text = " ".join(
        str(note.get(key) or "")
        for key in ["observation", "note", "element", "description"]
    ).lower()
    negative_tokens = [
        "not a jm ai",
        "not in jm ai",
        "not jm ai",
        "非jm ai",
        "不属于jm ai",
        "不符合",
        "distinct from jm ai",
        "lacks",
        "缺少",
        "无sparkle",
    ]
    exempt_tokens = ["possibly", "可能豁免", "third-party", "exempt"]
    if any(token in text for token in exempt_tokens) and "not" not in text:
        return False
    return any(token in text for token in negative_tokens)


def _normalize_passes(data: dict[str, Any]) -> list[Any]:
    output = [_pass_text(item) for item in _list_or_empty(data.get("passes"))]
    for value in data.values():
        if not isinstance(value, dict):
            continue
        for item in _list_or_empty(value.get("passed")):
            output.append(_pass_text(item))
        for item in _list_or_empty(value.get("notes")):
            if isinstance(item, dict) and _note_is_pass(item):
                output.append(_pass_text(item.get("observation") or item))
    return output


def _note_is_pass(note: dict[str, Any]) -> bool:
    text = str(note.get("observation") or "").lower()
    return any(token in text for token in ["consistent", "符合", "matches", "appears to be primary"])


def _pass_text(item: Any) -> str:
    if isinstance(item, dict):
        return _localize_text(
            _first_text(
                item.get("description"),
                item.get("observation"),
                item.get("title"),
                item.get("id"),
            )
        )
    return str(_localize_text(str(item)))


def _normalize_cannot_verify(data: dict[str, Any]) -> list[dict[str, Any]]:
    output = [_cannot_verify_item(item) for item in _list_or_empty(data.get("cannot_verify"))]
    for value in data.values():
        if not isinstance(value, dict):
            continue
        for item in _list_or_empty(value.get("cannot_verify")):
            output.append(_cannot_verify_item(item))
    return [item for item in output if item["item"] or item["reason"]]


def _cannot_verify_item(item: Any) -> dict[str, Any]:
    if isinstance(item, dict):
        return {
            "item": _first_text(
                item.get("item"),
                item.get("description"),
                item.get("summary"),
                item.get("id"),
            ),
            "reason": _first_text(item.get("reason"), item.get("note")),
        }
    return {"item": str(item), "reason": ""}


def _normalize_regions(
    data: dict[str, Any],
    image_size: tuple[int, int] | None = None,
) -> list[dict[str, Any]]:
    output = _normalize_region_items(_list_or_empty(data.get("regions")), image_size)
    evidence_requests = data.get("evidence_requests")
    if isinstance(evidence_requests, dict):
        output.extend(
            _normalize_region_items(
                _list_or_empty(evidence_requests.get("regions")),
                image_size,
            )
        )
    return output


def _normalize_region_items(
    items: list[Any],
    image_size: tuple[int, int] | None,
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue
        bbox = _normalize_bbox(
            item.get("bbox") or item.get("approximate_bbox"),
            image_size=image_size,
        )
        if bbox is None:
            continue
        output.append(
            {
                "id": _first_text(item.get("id"), f"region-{index:03d}"),
                "title": _first_text(item.get("title"), item.get("description")),
                "bbox": bbox,
                "role_hint": _first_text(item.get("role_hint"), item.get("purpose")) or None,
                "measure_kind": _measure_kind(item.get("measure_kind"), item.get("purpose")),
            }
        )
    return output


def _normalize_distances(data: dict[str, Any]) -> list[dict[str, Any]]:
    output = _list_or_empty(data.get("distances"))
    evidence_requests = data.get("evidence_requests")
    if isinstance(evidence_requests, dict):
        output.extend(_list_or_empty(evidence_requests.get("distances")))
    return [item for item in output if isinstance(item, dict)]


def _normalize_sample_points(
    value: Any,
    image_size: tuple[int, int] | None = None,
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for index, item in enumerate(_list_or_empty(value), start=1):
        if not isinstance(item, dict):
            continue
        label = _first_text(item.get("label"), item.get("id"), f"sample-{index:03d}")
        x = item.get("x")
        y = item.get("y")
        bbox = _normalize_bbox(item.get("bbox"), image_size=image_size)
        if bbox is not None and not isinstance(x, int) and not isinstance(y, int):
            x = int(round(bbox[0] + bbox[2] / 2))
            y = int(round(bbox[1] + bbox[3] / 4))
        if isinstance(x, (int, float)) and isinstance(y, (int, float)):
            output.append({"label": label, "x": int(round(x)), "y": int(round(y))})
    return output


def _measure_kind(*values: Any) -> str:
    text = " ".join(str(value or "").lower() for value in values)
    if any(token in text for token in ["spacing", "gap", "padding", "distance"]):
        return "spacing"
    if any(token in text for token in ["type", "font", "text"]):
        return "typography"
    return "component"


def _list_or_empty(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def _normalize_issue_list(
    value: Any,
    image_size: tuple[int, int] | None = None,
    audit_spec_label: str = "JM AI 设计规范",
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    issues: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        issue = _normalize_issue(
            item,
            None,
            len(issues) + 1,
            image_size=image_size,
            audit_spec_label=audit_spec_label,
        )
        if issue:
            issues.append(issue)
    return issues


def _normalize_issue(
    item: dict[str, Any],
    category: str | None,
    index: int,
    image_size: tuple[int, int] | None = None,
    audit_spec_label: str = "JM AI 设计规范",
) -> dict[str, Any] | None:
    evidence = item.get("evidence")
    observation = _first_text(
        item.get("current_observation"),
        _dict_text(evidence, "description"),
        _join_texts(evidence),
        item.get("description"),
        item.get("observation"),
        item.get("title"),
        item.get("issue"),
    )
    if not observation:
        return None
    issue_category = _first_text(item.get("category"), category, "其他")
    return {
        "id": _first_text(item.get("id"), f"issue-{index:03d}"),
        "category": issue_category,
        "severity": _normalize_severity(item.get("severity")),
        "location": _first_text(item.get("location"), item.get("title"), issue_category),
        "current_observation": observation,
        "spec_expectation": _first_text(
            item.get("spec_expectation"),
            item.get("expectation"),
            item.get("expected"),
            item.get("rule"),
            item.get("inference"),
            item.get("subcategory"),
        ),
        "recommendation": _first_text(
            item.get("recommendation"),
            item.get("suggestion"),
            item.get("fix"),
            f"请按{_audit_spec_phrase(audit_spec_label)}调整。",
        ),
        "confidence": _normalize_confidence(item.get("confidence")),
        "bbox": _normalize_bbox(
            item.get("bbox") or _dict_value(evidence, "bbox"),
            image_size=image_size,
        ),
        "rule_source_type": _first_text(
            item.get("rule_source_type"),
            item.get("source_type"),
        )
        or None,
        "rule_source_ref": _first_text(
            item.get("rule_source_ref"),
            item.get("source_ref"),
            item.get("rule_source"),
            item.get("source"),
        )
        or None,
    }


def _normalize_severity(value: Any) -> str:
    text = str(value or "").strip()
    if text in {"高", "中", "低"}:
        return text
    return SEVERITY_MAP.get(text.lower(), "中")


def _join_texts(value: Any) -> str:
    if isinstance(value, list):
        return "；".join(str(item) for item in value if str(item).strip())
    if isinstance(value, str):
        return value
    return ""


def _dict_text(value: Any, key: str) -> str:
    nested = _dict_value(value, key)
    return nested.strip() if isinstance(nested, str) else ""


def _dict_value(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return value.get(key)
    return None


def _normalize_confidence(value: Any) -> float:
    if isinstance(value, (int, float)) and 0 <= value <= 1:
        return float(value)
    return 0.7


def _normalize_bbox(
    value: Any,
    image_size: tuple[int, int] | None = None,
) -> list[float] | None:
    if not (
        isinstance(value, list)
        and len(value) == 4
        and all(isinstance(item, (int, float)) for item in value)
    ):
        return None
    if value[2] <= 0 or value[3] <= 0:
        return None
    if all(0 <= item <= 1 for item in value):
        if image_size is None:
            return None
        width, height = image_size
        x, y, third, fourth = [float(item) for item in value]
        if x + third > 1 or y + fourth > 1:
            return _rounded_bbox(
                [x * width, y * height, (third - x) * width, (fourth - y) * height]
            )
        return _rounded_bbox([x * width, y * height, third * width, fourth * height])
    return _rounded_bbox([float(item) for item in value])


def _rounded_bbox(value: list[float]) -> list[float]:
    return [round(item, 6) for item in value]


def image_data_url(path: Path) -> str:
    suffix = path.suffix.lower()
    media_type = "image/png"
    if suffix in {".jpg", ".jpeg"}:
        media_type = "image/jpeg"
    elif suffix == ".webp":
        media_type = "image/webp"

    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{media_type};base64,{encoded}"


def parse_b_design_applicability_json(text: str) -> dict[str, Any]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AuditModelError("B-design 适用性识别 JSON 无法解析") from exc
    return normalize_b_design_applicability(data)


def _detect_b_design_applicability_with_responses(
    client: _OpenAIClient,
    model: str,
    image_path: Path,
    audit_spec_label: str,
    actual_image_size: tuple[int, int],
    reasoning_effort: str | None = None,
    declared_screen_size: tuple[int, int] | None = None,
    scale_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    request: dict[str, Any] = {
        "model": model,
        "input": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": build_b_design_applicability_prompt(
                            audit_spec_label=audit_spec_label,
                            actual_image_size=actual_image_size,
                            declared_screen_size=declared_screen_size,
                            scale_context=scale_context,
                        ),
                    },
                    {
                        "type": "input_image",
                        "image_url": image_data_url(image_path),
                        "detail": "high",
                    },
                ],
            }
        ],
        "text": {"format": b_design_applicability_json_schema()},
    }
    if reasoning_effort:
        request["reasoning"] = {"effort": reasoning_effort}
    response = client.responses.create(**request)
    return parse_b_design_applicability_json(response.output_text)


def _detect_b_design_applicability_with_chat(
    client: _OpenAIClient,
    model: str,
    image_path: Path,
    audit_spec_label: str,
    actual_image_size: tuple[int, int],
    reasoning_effort: str | None = None,
    declared_screen_size: tuple[int, int] | None = None,
    scale_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    request: dict[str, Any] = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": build_b_design_applicability_prompt(
                            audit_spec_label=audit_spec_label,
                            actual_image_size=actual_image_size,
                            declared_screen_size=declared_screen_size,
                            scale_context=scale_context,
                        ),
                    },
                    {"type": "image_url", "image_url": {"url": image_data_url(image_path)}},
                ],
            }
        ],
        "response_format": {"type": "json_object"},
        "max_tokens": B_DESIGN_APPLICABILITY_MAX_TOKENS,
    }
    if reasoning_effort:
        request["reasoning"] = {"effort": reasoning_effort}
    response = client.chat.completions.create(**request)
    choice = response.choices[0]
    content = choice.message.content
    if not isinstance(content, str) or not content.strip():
        finish_reason = getattr(choice, "finish_reason", None)
        raise AuditModelError(
            "B-design 适用性识别没有返回 JSON 内容"
            f" (finish_reason={finish_reason}). "
            "请提高适用性识别输出 token 上限，或检查该模型是否支持图片 JSON 输出。"
        )
    return parse_b_design_applicability_json(content)


def _routed_b_design_context(
    spec_text: str,
    applicability: dict[str, Any],
) -> dict[str, Any]:
    return select_b_design_spec_context(
        spec_text,
        list(applicability.get("selected_component_ids") or []),
    )


def _b_design_not_applicable_audit(
    audit_spec_label: str,
    applicability: dict[str, Any],
) -> dict[str, Any]:
    reason = (
        applicability.get("reason")
        or "截图未命中 B-design 覆盖组件或扩展规则场景。"
    )
    audit = {
        "screen_context": applicability.get("screen_context") or "未命中 B-design 规范覆盖",
        "overall_conclusion": (
            "未命中 B-design 规范覆盖范围；本次不输出规范违规问题。"
        ),
        "major_issues": [],
        "passes": [],
        "issues": [],
        "sample_points": [],
        "regions": [],
        "distances": [],
        "checklist": [],
        "cannot_verify": [
            {
                "item": "B-design 规范适用性",
                "reason": str(reason),
            }
        ],
        "b_design_applicability": applicability,
        "loaded_spec_sections": [],
    }
    return _with_prompt_metadata(audit, audit_spec_label=audit_spec_label)


def _with_b_design_routing_metadata(
    audit: dict[str, Any],
    applicability: dict[str, Any] | None,
    context: dict[str, Any] | None,
) -> dict[str, Any]:
    if applicability is None:
        return audit
    output = dict(audit)
    output["b_design_applicability"] = applicability
    output["loaded_spec_sections"] = list((context or {}).get("loaded_sections") or [])
    output["loaded_spec_components"] = component_names(
        list((context or {}).get("component_ids") or [])
    )
    return output


def audit_image(
    client: _OpenAIClient,
    model: str,
    image_path: Path,
    spec_text: str,
    audit_spec_label: str = "JM AI 设计规范",
    reasoning_effort: str | None = None,
    declared_screen_size: tuple[int, int] | None = None,
    scale_context: dict[str, Any] | None = None,
    normalized_preview_path: Path | None = None,
    experiment_variant: str | None = None,
) -> dict[str, Any]:
    actual_image_size = _image_size(image_path)
    normalized_size = _image_size(normalized_preview_path) if normalized_preview_path else None
    b_design_applicability: dict[str, Any] | None = None
    b_design_context: dict[str, Any] | None = None
    if is_b_design_label(audit_spec_label):
        b_design_applicability = _detect_b_design_applicability_with_responses(
            client,
            model,
            image_path,
            audit_spec_label,
            actual_image_size,
            reasoning_effort=reasoning_effort,
            declared_screen_size=declared_screen_size,
            scale_context=scale_context,
        )
        if not has_selected_b_design_components(b_design_applicability):
            return _b_design_not_applicable_audit(audit_spec_label, b_design_applicability)
        b_design_context = _routed_b_design_context(spec_text, b_design_applicability)
        spec_text = str(b_design_context["spec_text"])
    content: list[dict[str, Any]] = [
        {
            "type": "input_text",
            "text": build_audit_prompt(
                spec_text,
                audit_spec_label=audit_spec_label,
                declared_screen_size=declared_screen_size,
                actual_image_size=actual_image_size,
                scale_context=scale_context,
                normalized_preview_size=normalized_size,
                experiment_variant=experiment_variant,
            ),
        },
        {
            "type": "input_image",
            "image_url": image_data_url(image_path),
            "detail": "high",
        },
    ]
    if normalized_preview_path:
        content.append(
            {
                "type": "input_image",
                "image_url": image_data_url(normalized_preview_path),
                "detail": "high",
            }
        )
    request: dict[str, Any] = {
        "model": model,
        "input": [
            {
                "role": "user",
                "content": content,
            }
        ],
        "text": {"format": audit_json_schema()},
    }
    if reasoning_effort:
        request["reasoning"] = {"effort": reasoning_effort}

    response = client.responses.create(**request)
    audit = _with_b_design_routing_metadata(
        parse_strict_audit_json(response.output_text),
        b_design_applicability,
        b_design_context,
    )
    return _with_prompt_metadata(
        audit,
        audit_spec_label=audit_spec_label,
    )


def audit_image_with_chat(
    client: _OpenAIClient,
    model: str,
    image_path: Path,
    spec_text: str,
    audit_spec_label: str = "JM AI 设计规范",
    reasoning_effort: str | None = None,
    declared_screen_size: tuple[int, int] | None = None,
    scale_context: dict[str, Any] | None = None,
    normalized_preview_path: Path | None = None,
    experiment_variant: str | None = None,
) -> dict[str, Any]:
    actual_image_size = _image_size(image_path)
    normalized_size = _image_size(normalized_preview_path) if normalized_preview_path else None
    b_design_applicability: dict[str, Any] | None = None
    b_design_context: dict[str, Any] | None = None
    if is_b_design_label(audit_spec_label):
        b_design_applicability = _detect_b_design_applicability_with_chat(
            client,
            model,
            image_path,
            audit_spec_label,
            actual_image_size,
            reasoning_effort=reasoning_effort,
            declared_screen_size=declared_screen_size,
            scale_context=scale_context,
        )
        if not has_selected_b_design_components(b_design_applicability):
            return _b_design_not_applicable_audit(audit_spec_label, b_design_applicability)
        b_design_context = _routed_b_design_context(spec_text, b_design_applicability)
        spec_text = str(b_design_context["spec_text"])
    prompt = (
        build_audit_prompt(
            spec_text,
            audit_spec_label=audit_spec_label,
            declared_screen_size=declared_screen_size,
            actual_image_size=actual_image_size,
            scale_context=scale_context,
            normalized_preview_size=normalized_size,
            experiment_variant=experiment_variant,
        )
        + "\n\n必须只输出一个 JSON 对象，不要输出 Markdown，不要包裹代码块。"
        "所有字段值必须使用简体中文；除 token、hex 色值、专有产品名和代码标识外，不要输出英文句子。"
        "必须优先使用这些顶层字段："
        "screen_context(string), overall_conclusion(string), major_issues(array), "
        "passes(array), issues(array), sample_points(array), regions(array), "
        "distances(array), checklist(array), cannot_verify(array)。"
        "发现问题必须写入 issues；不要只写 notes、summary 或分组章节。"
        "每个 issue 必须包含 id, category, severity(高/中/低), location, "
        "current_observation, spec_expectation, recommendation, confidence, bbox, "
        "rule_source_type, rule_source_ref。"
        "bbox 必须是截图像素 [x,y,w,h]；无法定位时填 null。"
        "B-design issue 的 rule_source_type 只能为 pdf_text、pdf_visual_example 或 alpha_case；"
        "非 B-design 审核可填 null。"
        "正向观察写入 passes；无法确认项写入 cannot_verify。"
    )
    content: list[dict[str, Any]] = [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": image_data_url(image_path)}},
    ]
    if normalized_preview_path:
        content.append(
            {"type": "image_url", "image_url": {"url": image_data_url(normalized_preview_path)}}
        )
    request: dict[str, Any] = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": content,
            }
        ],
        "response_format": {"type": "json_object"},
        "max_tokens": CHAT_AUDIT_MAX_TOKENS,
    }
    if reasoning_effort:
        request["reasoning"] = {"effort": reasoning_effort}

    response = client.chat.completions.create(**request)
    choice = response.choices[0]
    content = choice.message.content
    if not isinstance(content, str) or not content.strip():
        finish_reason = getattr(choice, "finish_reason", None)
        raise AuditModelError(
            "模型没有返回可解析的 JSON 内容"
            f" (finish_reason={finish_reason}). "
            "请提高输出 token 上限，或检查该模型是否支持图片 JSON 输出。"
        )
    audit = _with_b_design_routing_metadata(
        parse_lenient_chat_audit_json(
            content,
            image_size=actual_image_size,
            audit_spec_label=audit_spec_label,
        ),
        b_design_applicability,
        b_design_context,
    )
    return _with_prompt_metadata(
        audit,
        audit_spec_label=audit_spec_label,
    )


def audit_image_with_chat_light(
    client: _OpenAIClient,
    model: str,
    image_path: Path,
    spec_text: str,
    audit_spec_label: str = "JM AI 设计规范",
    reasoning_effort: str | None = None,
    declared_screen_size: tuple[int, int] | None = None,
    scale_context: dict[str, Any] | None = None,
    normalized_preview_path: Path | None = None,
    experiment_variant: str | None = None,
) -> dict[str, Any]:
    actual_image_size = _image_size(image_path)
    normalized_size = _image_size(normalized_preview_path) if normalized_preview_path else None
    b_design_applicability: dict[str, Any] | None = None
    b_design_context: dict[str, Any] | None = None
    if is_b_design_label(audit_spec_label):
        b_design_applicability = _detect_b_design_applicability_with_chat(
            client,
            model,
            image_path,
            audit_spec_label,
            actual_image_size,
            reasoning_effort=reasoning_effort,
            declared_screen_size=declared_screen_size,
            scale_context=scale_context,
        )
        if not has_selected_b_design_components(b_design_applicability):
            return _b_design_not_applicable_audit(audit_spec_label, b_design_applicability)
        b_design_context = _routed_b_design_context(spec_text, b_design_applicability)
        spec_text = str(b_design_context["spec_text"])
        prompt = (
            build_audit_prompt(
                spec_text,
                audit_spec_label=audit_spec_label,
                declared_screen_size=declared_screen_size,
                actual_image_size=actual_image_size,
                scale_context=scale_context,
                normalized_preview_size=normalized_size,
                experiment_variant=experiment_variant,
            )
            + "\n\n只依据上方已加载的 B-design 章节审核。"
            "不要输出通用 B 端界面风险，不要使用未加载章节或其他规范。"
            "每个 issue 必须填写 rule_source_type 和 rule_source_ref。"
        )
    else:
        prompt = build_light_audit_prompt(
            audit_spec_label=audit_spec_label,
            declared_screen_size=declared_screen_size,
            actual_image_size=actual_image_size,
            scale_context=scale_context,
            normalized_preview_size=normalized_size,
            experiment_variant=experiment_variant,
        )
    content: list[dict[str, Any]] = [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": image_data_url(image_path)}},
    ]
    if normalized_preview_path:
        content.append(
            {"type": "image_url", "image_url": {"url": image_data_url(normalized_preview_path)}}
        )
    request: dict[str, Any] = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": content,
            }
        ],
        "response_format": {"type": "json_object"},
        "max_tokens": CHAT_AUDIT_LIGHT_MAX_TOKENS,
    }
    if reasoning_effort:
        request["reasoning"] = {"effort": reasoning_effort}

    response = client.chat.completions.create(**request)
    choice = response.choices[0]
    content = choice.message.content
    if not isinstance(content, str) or not content.strip():
        finish_reason = getattr(choice, "finish_reason", None)
        raise AuditModelError(
            "模型没有返回可解析的轻量审核 JSON 内容"
            f" (finish_reason={finish_reason}). "
            "请检查该模型是否支持图片 JSON 输出，或切回 full prompt mode。"
        )
    audit = _with_b_design_routing_metadata(
        parse_lenient_chat_audit_json(
            content,
            image_size=actual_image_size,
            audit_spec_label=audit_spec_label,
        ),
        b_design_applicability,
        b_design_context,
    )
    return _with_prompt_metadata(
        audit,
        audit_spec_label=audit_spec_label,
    )


def audit_image_with_kimi_light(
    client: _OpenAIClient,
    model: str,
    image_path: Path,
    spec_text: str,
    audit_spec_label: str = "JM AI 设计规范",
    reasoning_effort: str | None = None,
    declared_screen_size: tuple[int, int] | None = None,
    scale_context: dict[str, Any] | None = None,
    normalized_preview_path: Path | None = None,
    experiment_variant: str | None = None,
) -> dict[str, Any]:
    actual_image_size = _image_size(image_path)
    normalized_size = _image_size(normalized_preview_path) if normalized_preview_path else None
    b_design_applicability: dict[str, Any] | None = None
    b_design_context: dict[str, Any] | None = None
    if is_b_design_label(audit_spec_label):
        b_design_applicability = _detect_b_design_applicability_with_chat(
            client,
            model,
            image_path,
            audit_spec_label,
            actual_image_size,
            reasoning_effort=reasoning_effort,
            declared_screen_size=declared_screen_size,
            scale_context=scale_context,
        )
        if not has_selected_b_design_components(b_design_applicability):
            return _b_design_not_applicable_audit(audit_spec_label, b_design_applicability)
        b_design_context = _routed_b_design_context(spec_text, b_design_applicability)
        spec_text = str(b_design_context["spec_text"])
        prompt = (
            build_audit_prompt(
                spec_text,
                audit_spec_label=audit_spec_label,
                declared_screen_size=declared_screen_size,
                actual_image_size=actual_image_size,
                scale_context=scale_context,
                normalized_preview_size=normalized_size,
                experiment_variant=experiment_variant,
            )
            + "\n\n只依据上方已加载的 B-design 章节审核。"
            "不要输出通用 B 端界面风险，不要使用未加载章节或其他规范。"
            "每个 issue 必须填写 rule_source_type 和 rule_source_ref。"
            "保持输出紧凑，每个中文文本字段不超过 60 字。"
        )
    else:
        prompt = build_kimi_light_audit_prompt(
            audit_spec_label=audit_spec_label,
            declared_screen_size=declared_screen_size,
            actual_image_size=actual_image_size,
            scale_context=scale_context,
            normalized_preview_size=normalized_size,
            experiment_variant=experiment_variant,
        )
    content: list[dict[str, Any]] = [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": image_data_url(image_path)}},
    ]
    if normalized_preview_path:
        content.append(
            {"type": "image_url", "image_url": {"url": image_data_url(normalized_preview_path)}}
        )
    request: dict[str, Any] = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": content,
            }
        ],
        "response_format": {"type": "json_object"},
        "max_tokens": KIMI_CHAT_AUDIT_LIGHT_MAX_TOKENS,
    }
    if reasoning_effort:
        request["reasoning"] = {"effort": reasoning_effort}

    response = client.chat.completions.create(**request)
    choice = response.choices[0]
    content = choice.message.content
    if not isinstance(content, str) or not content.strip():
        finish_reason = getattr(choice, "finish_reason", None)
        raise AuditModelError(
            "Kimi 没有返回可解析的紧凑审核 JSON 内容"
            f" (finish_reason={finish_reason}). "
            "请进一步压缩 Kimi prompt 或提高 Kimi light 输出上限。"
        )
    audit = _with_b_design_routing_metadata(
        parse_lenient_chat_audit_json(
            content,
            image_size=actual_image_size,
            audit_spec_label=audit_spec_label,
        ),
        b_design_applicability,
        b_design_context,
    )
    return _with_prompt_metadata(
        audit,
        audit_spec_label=audit_spec_label,
    )
