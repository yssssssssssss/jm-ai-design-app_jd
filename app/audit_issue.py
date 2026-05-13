from __future__ import annotations

from typing import Any

from app.audit_taxonomy import normalize_category, normalize_subcategory


SEVERITY_VALUES = {"高", "中", "低"}


def _list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _first_present(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _key_text(value: Any) -> str:
    text = _text(value).lower()
    return "-".join("".join(ch if ch.isalnum() or ch in "._" else " " for ch in text).split())


def _severity(value: Any) -> str:
    text = _text(value)
    if text in SEVERITY_VALUES:
        return text
    lowered = text.lower()
    if lowered in {"critical", "high"}:
        return "高"
    if lowered in {"medium", "warning"}:
        return "中"
    return "低"


def _confidence(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.6


def _text_list(value: Any) -> list[str]:
    return [_text(item) for item in _list(value) if _text(item)]


def issue_key(issue: Any) -> str:
    if not isinstance(issue, dict):
        issue = {"current_observation": _text(issue)} if _text(issue) else {}
    category_value = normalize_category(issue.get("category"))
    subcategory_value = normalize_subcategory(issue.get("subcategory"), category_value)
    category = _key_text(category_value)
    subcategory = _key_text(subcategory_value)
    target = _key_text(issue.get("target_element") or issue.get("location") or "unknown")
    violation = _key_text(
        issue.get("violation_type") or issue.get("current_observation") or "issue"
    )
    return f"{category}.{subcategory}:{target}:{violation}"


def normalize_issue(
    raw_issue: Any,
    index: int,
    source_model: str | None = None,
) -> dict[str, Any]:
    if isinstance(raw_issue, dict):
        issue = dict(raw_issue)
    else:
        issue = {"current_observation": _text(raw_issue)}

    category = normalize_category(issue.get("category"))
    subcategory = normalize_subcategory(issue.get("subcategory"), category)
    location = _text(_first_present(issue.get("location"), issue.get("title"), issue.get("id"), "问题"))
    target_element = _text(_first_present(issue.get("target_element"), location))
    violation_type = _text(_first_present(issue.get("violation_type"), f"{category}.{subcategory}"))

    output = {
        **issue,
        "id": _text(issue.get("id")) or f"问题-{index:03d}",
        "issue_key": _text(issue.get("issue_key")),
        "category": category,
        "subcategory": subcategory,
        "target_element": target_element,
        "violation_type": violation_type,
        "severity": _severity(issue.get("severity")),
        "location": location,
        "current_observation": _text(
            _first_present(issue.get("current_observation"), issue.get("description"))
        ),
        "spec_expectation": _text(issue.get("spec_expectation")),
        "recommendation": _text(issue.get("recommendation")),
        "confidence": _confidence(issue.get("confidence")),
        "evidence_type": _text(issue.get("evidence_type") or "model_only"),
        "bbox": issue.get("bbox"),
        "bbox_status": _text(issue.get("bbox_status") or "unvalidated"),
        "bbox_confidence": issue.get("bbox_confidence"),
        "bbox_reason": _text(issue.get("bbox_reason")),
        "source_models": _text_list(issue.get("source_models")),
        "rule_sources": _text_list(issue.get("rule_sources")),
    }
    clean_source_model = _text(source_model)
    if clean_source_model and clean_source_model not in output["source_models"]:
        output["source_models"].append(clean_source_model)
    output["issue_key"] = output["issue_key"] or issue_key(output)
    return output


def normalize_issues(
    issues: list[Any] | None,
    source_model: str | None = None,
) -> list[dict[str, Any]]:
    return [
        normalize_issue(issue, index=index, source_model=source_model)
        for index, issue in enumerate(issues or [], start=1)
    ]
