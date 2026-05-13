# Audit Platform Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the current JM AI audit app without an evaluation dataset by standardizing issue structure, making bbox evidence safer, making prompts versioned, standardizing rule evidence, and improving report clarity.

**Architecture:** Keep the current FastAPI app, SQLite task flow, in-process queue, and artifact-based report generation. Add small deterministic modules for taxonomy, issue normalization, bbox validation, prompt building, model error classification, and rule hits; wire them into the existing audit pipeline with backward compatibility for old model JSON.

**Tech Stack:** Python 3.12, FastAPI, Jinja2, SQLite, Pillow, OpenAI-compatible SDK, pytest.

---

## Scope

This plan implements the first optimization round under one constraint: **no evaluation dataset is provided**.

Therefore this plan does not claim model accuracy improvement. It targets deterministic improvements:

- stable taxonomy
- standard issue schema
- safer bbox screenshot behavior
- versioned prompt construction
- model fallback/error classification
- standard rule hit evidence
- clearer report summary and issue table

Deferred:

- new database tables
- quality dashboard
- OCR
- component detector
- PDF export
- Figma integration
- full report versioning

## File Structure

- Create `app/audit_taxonomy.py`: standard category/subcategory normalization and display labels.
- Create `app/audit_issue.py`: issue normalization, issue key generation, rule/source metadata, and compatibility with old issue payloads.
- Create `app/bbox_validator.py`: deterministic bbox status, confidence, and reason.
- Create `app/prompt_builder.py`: PromptOps-style layered prompt construction with version metadata.
- Create `app/model_errors.py`: model error classification and fallback/degradation helpers.
- Modify `app/openai_audit.py`: call prompt builder and include `prompt_version` / `schema_version` in parsed audit payloads.
- Modify `app/audit_merge.py`: normalize issues before matching and preserve new issue fields.
- Modify `app/rule_engine.py`: emit standard `rule_hits`, attach `rule_sources`, and keep old `rule_warnings` compatibility.
- Modify `app/evidence_tools.py`: only emit screenshot issues for trusted bbox values.
- Modify `app/task_runner.py`: include degradation metadata and preserve new audit metadata.
- Modify `app/report_renderer.py`: render report quality summary and new issue metadata.
- Add `tests/test_audit_taxonomy.py`.
- Add `tests/test_audit_issue.py`.
- Add `tests/test_bbox_validator.py`.
- Add `tests/test_prompt_builder.py`.
- Add `tests/test_model_errors.py`.
- Modify `tests/test_audit_merge.py`.
- Modify `tests/test_rule_engine.py`.
- Modify `tests/test_evidence_tools.py`.
- Modify `tests/test_openai_audit.py`.
- Modify `tests/test_report_renderer.py`.
- Modify `tests/test_task_runner.py`.

Use this command in this environment:

```bash
PYTHONPATH=/private/tmp/pytest-no-readline:. .venv/bin/python -m pytest \
  tests/test_audit_taxonomy.py \
  tests/test_audit_issue.py \
  tests/test_bbox_validator.py \
  tests/test_prompt_builder.py \
  tests/test_model_errors.py \
  tests/test_audit_merge.py \
  tests/test_rule_engine.py \
  tests/test_evidence_tools.py \
  tests/test_openai_audit.py \
  tests/test_report_renderer.py \
  tests/test_task_runner.py \
  -q
```

Expected final result: selected tests pass.

---

### Task 1: Add Standard Audit Taxonomy

**Files:**
- Create: `app/audit_taxonomy.py`
- Add: `tests/test_audit_taxonomy.py`

- [ ] **Step 1: Write failing taxonomy tests**

Create `tests/test_audit_taxonomy.py`:

```python
from app.audit_taxonomy import (
    CATEGORY_LABELS,
    normalize_category,
    normalize_subcategory,
)


def test_normalize_category_maps_common_chinese_and_english_values():
    assert normalize_category("色彩") == "color_gradient"
    assert normalize_category("颜色和渐变") == "color_gradient"
    assert normalize_category("Color") == "color_gradient"
    assert normalize_category("按钮") == "component_spec"
    assert normalize_category("AI 标签") == "component_spec"
    assert normalize_category("字体") == "typography"
    assert normalize_category("间距") == "spacing_layout"
    assert normalize_category("Header") == "header_navigation"


def test_normalize_category_keeps_known_internal_values():
    assert normalize_category("color_gradient") == "color_gradient"
    assert normalize_category("component_spec") == "component_spec"


def test_normalize_category_falls_back_to_content_hierarchy():
    assert normalize_category("") == "content_hierarchy"
    assert normalize_category(None) == "content_hierarchy"
    assert normalize_category("无法归类") == "content_hierarchy"


def test_normalize_subcategory_uses_category_specific_defaults():
    assert normalize_subcategory("非规范色", "color_gradient") == "off_token_color"
    assert normalize_subcategory("按钮样式错误", "component_spec") == "button_wrong_style"
    assert normalize_subcategory("", "spacing_layout") == "general"


def test_category_labels_cover_all_public_categories():
    for key in [
        "brand_identity",
        "color_gradient",
        "typography",
        "spacing_layout",
        "component_spec",
        "icon_ai_mark",
        "header_navigation",
        "interaction_state",
        "accessibility",
        "content_hierarchy",
    ]:
        assert key in CATEGORY_LABELS
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
PYTHONPATH=/private/tmp/pytest-no-readline:. .venv/bin/python -m pytest tests/test_audit_taxonomy.py -q
```

Expected: fail because `app.audit_taxonomy` does not exist.

- [ ] **Step 3: Implement taxonomy module**

Create `app/audit_taxonomy.py`:

```python
from __future__ import annotations

from typing import Any


CATEGORY_LABELS = {
    "brand_identity": "品牌一致性",
    "color_gradient": "色彩与渐变",
    "typography": "字体与文本",
    "spacing_layout": "间距与布局",
    "component_spec": "组件规范",
    "icon_ai_mark": "图标与 AI 标识",
    "header_navigation": "头部与导航",
    "interaction_state": "交互与状态",
    "accessibility": "可访问性",
    "content_hierarchy": "文案与信息层级",
}

CATEGORY_ALIASES = {
    "brand": "brand_identity",
    "品牌": "brand_identity",
    "品牌一致性": "brand_identity",
    "color": "color_gradient",
    "colour": "color_gradient",
    "色彩": "color_gradient",
    "颜色": "color_gradient",
    "颜色和渐变": "color_gradient",
    "色彩和渐变": "color_gradient",
    "渐变": "color_gradient",
    "typography": "typography",
    "font": "typography",
    "字体": "typography",
    "字号": "typography",
    "文本": "typography",
    "spacing": "spacing_layout",
    "layout": "spacing_layout",
    "间距": "spacing_layout",
    "布局": "spacing_layout",
    "padding": "spacing_layout",
    "gap": "spacing_layout",
    "component": "component_spec",
    "button": "component_spec",
    "tag": "component_spec",
    "按钮": "component_spec",
    "标签": "component_spec",
    "ai标签": "component_spec",
    "组件": "component_spec",
    "icon": "icon_ai_mark",
    "图标": "icon_ai_mark",
    "闪光": "icon_ai_mark",
    "sparkle": "icon_ai_mark",
    "header": "header_navigation",
    "头部": "header_navigation",
    "导航": "header_navigation",
    "state": "interaction_state",
    "状态": "interaction_state",
    "交互": "interaction_state",
    "accessibility": "accessibility",
    "a11y": "accessibility",
    "可访问性": "accessibility",
    "content": "content_hierarchy",
    "文案": "content_hierarchy",
    "信息层级": "content_hierarchy",
}

SUBCATEGORY_ALIASES = {
    "color_gradient": {
        "非规范色": "off_token_color",
        "off token": "off_token_color",
        "off_token_color": "off_token_color",
        "错误渐变": "wrong_gradient_direction",
        "wrong_gradient_direction": "wrong_gradient_direction",
        "主操作非ai色": "non_ai_primary_action",
        "non_ai_primary_action": "non_ai_primary_action",
        "低对比度": "low_contrast",
        "low_contrast": "low_contrast",
    },
    "spacing_layout": {
        "间距偏差": "off_spacing_token",
        "off_spacing_token": "off_spacing_token",
        "对齐异常": "alignment_mismatch",
        "alignment_mismatch": "alignment_mismatch",
    },
    "component_spec": {
        "按钮样式错误": "button_wrong_style",
        "button_wrong_style": "button_wrong_style",
        "标签样式错误": "tag_wrong_shape",
        "tag_wrong_shape": "tag_wrong_shape",
    },
}


def _normalized(value: Any) -> str:
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


def normalize_category(value: Any) -> str:
    raw = str(value or "").strip()
    if raw in CATEGORY_LABELS:
        return raw
    key = _normalized(raw)
    if key in CATEGORY_ALIASES:
        return CATEGORY_ALIASES[key]
    for alias, category in CATEGORY_ALIASES.items():
        if alias in key or key in alias:
            return category
    return "content_hierarchy"


def normalize_subcategory(value: Any, category: Any) -> str:
    category_key = normalize_category(category)
    raw = str(value or "").strip()
    if not raw:
        return "general"
    key = _normalized(raw)
    aliases = SUBCATEGORY_ALIASES.get(category_key, {})
    if key in aliases:
        return aliases[key]
    for alias, subcategory in aliases.items():
        if alias in key or key in alias:
            return subcategory
    return key or "general"
```

- [ ] **Step 4: Run taxonomy tests**

Run:

```bash
PYTHONPATH=/private/tmp/pytest-no-readline:. .venv/bin/python -m pytest tests/test_audit_taxonomy.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add app/audit_taxonomy.py tests/test_audit_taxonomy.py
git commit -m "Add audit taxonomy normalization"
```

---

### Task 2: Add Standard Issue Normalization

**Files:**
- Create: `app/audit_issue.py`
- Add: `tests/test_audit_issue.py`

- [ ] **Step 1: Write failing issue normalization tests**

Create `tests/test_audit_issue.py`:

```python
from app.audit_issue import normalize_issue, normalize_issues


def test_normalize_issue_preserves_old_issue_fields_and_adds_standard_fields():
    issue = normalize_issue(
        {
            "id": "color-01",
            "category": "色彩",
            "severity": "中",
            "location": "顶部右上角",
            "current_observation": "邀好友按钮使用橙色。",
            "spec_expectation": "应使用 JM AI 主色。",
            "recommendation": "替换为 #6B36FA。",
            "confidence": 0.8,
            "bbox": [10, 20, 100, 40],
        },
        index=1,
        source_model="GPT-5.5",
    )

    assert issue["id"] == "color-01"
    assert issue["category"] == "color_gradient"
    assert issue["subcategory"] == "general"
    assert issue["target_element"] == "顶部右上角"
    assert issue["violation_type"] == "color_gradient.general"
    assert issue["evidence_type"] == "model_only"
    assert issue["source_models"] == ["GPT-5.5"]
    assert issue["rule_sources"] == []
    assert issue["bbox_status"] == "unvalidated"
    assert issue["bbox_confidence"] is None
    assert issue["issue_key"].startswith("color_gradient.general:")


def test_normalize_issue_uses_explicit_target_and_violation_type():
    issue = normalize_issue(
        {
            "category": "component_spec",
            "subcategory": "button_wrong_style",
            "target_element": "右上角邀好友按钮",
            "violation_type": "非 JM AI 主按钮样式",
            "current_observation": "按钮样式错误",
        },
        index=2,
        source_model="Kimi-K2.6",
    )

    assert issue["id"] == "问题-002"
    assert issue["target_element"] == "右上角邀好友按钮"
    assert issue["violation_type"] == "非 JM AI 主按钮样式"
    assert "右上角邀好友按钮" in issue["issue_key"]
    assert issue["source_models"] == ["Kimi-K2.6"]


def test_normalize_issue_handles_non_dict_issue():
    issue = normalize_issue("按钮颜色不符合规范", index=3)

    assert issue["id"] == "问题-003"
    assert issue["category"] == "content_hierarchy"
    assert issue["current_observation"] == "按钮颜色不符合规范"
    assert issue["confidence"] == 0.6


def test_normalize_issues_applies_source_model_to_each_issue():
    issues = normalize_issues(
        [{"category": "色彩", "location": "按钮"}, {"category": "间距", "location": "卡片"}],
        source_model="GPT-5.5",
    )

    assert [issue["source_models"] for issue in issues] == [["GPT-5.5"], ["GPT-5.5"]]
    assert [issue["category"] for issue in issues] == ["color_gradient", "spacing_layout"]
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
PYTHONPATH=/private/tmp/pytest-no-readline:. .venv/bin/python -m pytest tests/test_audit_issue.py -q
```

Expected: fail because `app.audit_issue` does not exist.

- [ ] **Step 3: Implement issue normalization**

Create `app/audit_issue.py`:

```python
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
    return str(value or "").strip()


def _normalized_key(value: Any) -> str:
    text = _text(value).lower()
    return "-".join("".join(ch if ch.isalnum() else " " for ch in text).split())


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


def issue_key(issue: dict[str, Any]) -> str:
    parts = [
        issue.get("category") or "content_hierarchy",
        issue.get("subcategory") or "general",
        issue.get("target_element") or issue.get("location") or "unknown",
        issue.get("violation_type") or issue.get("current_observation") or "issue",
    ]
    return ":".join(_normalized_key(part) for part in parts if _normalized_key(part))


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
    location = _text(issue.get("location") or issue.get("title") or issue.get("id") or "问题")
    target_element = _text(issue.get("target_element") or location)
    violation_type = _text(issue.get("violation_type") or f"{category}.{subcategory}")

    output = {
        **issue,
        "id": _text(issue.get("id")) or f"问题-{index:03d}",
        "category": category,
        "subcategory": subcategory,
        "target_element": target_element,
        "violation_type": violation_type,
        "severity": _severity(issue.get("severity")),
        "location": location,
        "current_observation": _text(issue.get("current_observation") or issue.get("description")),
        "spec_expectation": _text(issue.get("spec_expectation")),
        "recommendation": _text(issue.get("recommendation")),
        "confidence": float(issue.get("confidence") or 0.6),
        "evidence_type": _text(issue.get("evidence_type") or "model_only"),
        "bbox": issue.get("bbox"),
        "bbox_status": _text(issue.get("bbox_status") or "unvalidated"),
        "bbox_confidence": issue.get("bbox_confidence"),
        "bbox_reason": _text(issue.get("bbox_reason")),
        "source_models": [str(model) for model in _list(issue.get("source_models")) if str(model).strip()],
        "rule_sources": [str(rule) for rule in _list(issue.get("rule_sources")) if str(rule).strip()],
    }
    if source_model and source_model not in output["source_models"]:
        output["source_models"].append(source_model)
    output["issue_key"] = _text(issue.get("issue_key")) or issue_key(output)
    return output


def normalize_issues(
    issues: list[Any],
    source_model: str | None = None,
) -> list[dict[str, Any]]:
    return [
        normalize_issue(issue, index=index, source_model=source_model)
        for index, issue in enumerate(issues or [], start=1)
    ]
```

- [ ] **Step 4: Run issue tests**

Run:

```bash
PYTHONPATH=/private/tmp/pytest-no-readline:. .venv/bin/python -m pytest tests/test_audit_issue.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add app/audit_issue.py tests/test_audit_issue.py
git commit -m "Add audit issue normalization"
```

---

### Task 3: Add BBox Validator

**Files:**
- Create: `app/bbox_validator.py`
- Add: `tests/test_bbox_validator.py`
- Modify: `app/evidence_tools.py`
- Modify: `tests/test_evidence_tools.py`

- [ ] **Step 1: Write failing bbox validator tests**

Create `tests/test_bbox_validator.py`:

```python
from app.bbox_validator import validate_bbox


def test_validate_bbox_trusts_in_bounds_matching_position():
    result = validate_bbox(
        [700, 20, 120, 40],
        image_size=(1000, 600),
        text="顶部右上角邀好友按钮颜色违规",
    )

    assert result["bbox_status"] == "trusted"
    assert result["bbox_confidence"] >= 0.8
    assert "符合" in result["bbox_reason"]


def test_validate_bbox_drops_out_of_bounds_bbox():
    result = validate_bbox([980, 20, 100, 40], image_size=(1000, 600), text="右上角按钮")

    assert result["bbox_status"] == "dropped"
    assert result["bbox_confidence"] == 0.0
    assert "越界" in result["bbox_reason"]


def test_validate_bbox_marks_position_conflict_suspicious():
    result = validate_bbox([10, 20, 120, 40], image_size=(1000, 600), text="右上角按钮")

    assert result["bbox_status"] == "suspicious"
    assert 0 < result["bbox_confidence"] < 0.8
    assert "位置描述" in result["bbox_reason"]


def test_validate_bbox_drops_invalid_bbox():
    result = validate_bbox([10, 20, 0, 40], image_size=(1000, 600), text="按钮")

    assert result["bbox_status"] == "dropped"
    assert "无效" in result["bbox_reason"]
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
PYTHONPATH=/private/tmp/pytest-no-readline:. .venv/bin/python -m pytest tests/test_bbox_validator.py -q
```

Expected: fail because `app.bbox_validator` does not exist.

- [ ] **Step 3: Implement bbox validator**

Create `app/bbox_validator.py`:

```python
from __future__ import annotations

from typing import Any


def _bbox(value: Any) -> tuple[float, float, float, float] | None:
    try:
        if isinstance(value, dict):
            x = float(value["x"])
            y = float(value["y"])
            w = float(value["width"])
            h = float(value["height"])
        elif isinstance(value, (list, tuple)) and len(value) == 4:
            x = float(value[0])
            y = float(value[1])
            w = float(value[2])
            h = float(value[3])
        else:
            return None
    except (KeyError, TypeError, ValueError):
        return None
    if w <= 0 or h <= 0:
        return None
    return x, y, w, h


def validate_bbox(
    bbox: Any,
    image_size: tuple[int, int],
    text: str = "",
) -> dict[str, Any]:
    parsed = _bbox(bbox)
    if parsed is None:
        return {
            "bbox_status": "dropped",
            "bbox_confidence": 0.0,
            "bbox_reason": "bbox 无效，无法生成可信截图。",
        }

    width, height = image_size
    x, y, w, h = parsed
    if x < 0 or y < 0 or x + w > width or y + h > height:
        return {
            "bbox_status": "dropped",
            "bbox_confidence": 0.0,
            "bbox_reason": "bbox 越界，已禁止生成问题截图。",
        }

    area_ratio = (w * h) / max(1, width * height)
    if area_ratio > 0.55:
        return {
            "bbox_status": "suspicious",
            "bbox_confidence": 0.45,
            "bbox_reason": "bbox 覆盖区域过大，截图证据可信度较低。",
        }

    center_x = x + w / 2
    center_y = y + h / 2
    issue_text = text or ""
    conflicts = []
    if "右" in issue_text and "左" not in issue_text and center_x < width * 0.5:
        conflicts.append("右侧")
    if "左" in issue_text and "右" not in issue_text and center_x > width * 0.5:
        conflicts.append("左侧")
    if ("顶部" in issue_text or "上角" in issue_text) and center_y > height * 0.5:
        conflicts.append("顶部")
    if ("底部" in issue_text or "下角" in issue_text) and center_y < height * 0.5:
        conflicts.append("底部")
    if conflicts:
        return {
            "bbox_status": "suspicious",
            "bbox_confidence": 0.35,
            "bbox_reason": f"bbox 与问题位置描述不一致：{', '.join(conflicts)}。",
        }

    return {
        "bbox_status": "trusted",
        "bbox_confidence": 0.9,
        "bbox_reason": "bbox 位于图片范围内，且符合问题位置描述。",
    }
```

- [ ] **Step 4: Run bbox validator tests**

Run:

```bash
PYTHONPATH=/private/tmp/pytest-no-readline:. .venv/bin/python -m pytest tests/test_bbox_validator.py -q
```

Expected: pass.

- [ ] **Step 5: Add evidence tool filtering test**

Append to `tests/test_evidence_tools.py`:

```python
def test_build_issues_json_for_image_skips_dropped_or_suspicious_bboxes():
    issues = [
        {
            "id": "ok",
            "severity": "中",
            "category": "色彩",
            "current_observation": "右上角按钮颜色违规",
            "bbox": [80, 5, 10, 10],
            "bbox_status": "trusted",
        },
        {
            "id": "bad",
            "severity": "中",
            "category": "色彩",
            "current_observation": "右上角按钮颜色违规",
            "bbox": [5, 5, 10, 10],
            "bbox_status": "suspicious",
        },
    ]

    result = build_issues_json_for_image(issues, image_size=(100, 100))

    assert [item["id"] for item in result] == ["ok"]
```

- [ ] **Step 6: Update evidence tool filtering**

In `app/evidence_tools.py`, inside `_build_issues_json`, skip explicit non-trusted bbox values:

```python
        if issue.get("bbox_status") in {"suspicious", "dropped"}:
            continue
```

Place the check before `_valid_bbox(bbox)`.

- [ ] **Step 7: Run evidence tests**

Run:

```bash
PYTHONPATH=/private/tmp/pytest-no-readline:. .venv/bin/python -m pytest tests/test_bbox_validator.py tests/test_evidence_tools.py -q
```

Expected: pass.

- [ ] **Step 8: Commit**

```bash
git add app/bbox_validator.py app/evidence_tools.py tests/test_bbox_validator.py tests/test_evidence_tools.py
git commit -m "Add bbox validation for audit evidence"
```

---

### Task 4: Wire Issue Normalization and BBox Validation Into Merge and Rule Review

**Files:**
- Modify: `app/audit_merge.py`
- Modify: `app/rule_engine.py`
- Modify: `tests/test_audit_merge.py`
- Modify: `tests/test_rule_engine.py`

- [ ] **Step 1: Add failing merge normalization test**

Append to `tests/test_audit_merge.py`:

```python
def test_merge_audits_normalizes_issue_schema_fields():
    result = merge_audits(
        [
            _audit(
                "GPT-5.5",
                [
                    {
                        "category": "色彩",
                        "location": "顶部右上角",
                        "current_observation": "邀好友按钮使用橙色。",
                        "bbox": [700, 20, 100, 40],
                    }
                ],
            )
        ]
    )

    issue = result["issues"][0]
    assert issue["category"] == "color_gradient"
    assert issue["subcategory"] == "general"
    assert issue["target_element"] == "顶部右上角"
    assert issue["issue_key"].startswith("color-gradient")
    assert issue["bbox_status"] in {"trusted", "unvalidated"}
```

- [ ] **Step 2: Add failing rule bbox validation test**

Append to `tests/test_rule_engine.py`:

```python
def test_rule_review_adds_bbox_confidence_fields():
    audit = _audit(
        issues=[
            {
                "id": "model-001",
                "category": "色彩",
                "location": "顶部右上角按钮",
                "current_observation": "按钮颜色异常。",
                "bbox": [70, 5, 20, 20],
            }
        ]
    )

    result = apply_rule_review(audit, tokens={}, measurements={}, image_size=(100, 100))

    issue = result["issues"][0]
    assert issue["bbox_status"] == "trusted"
    assert issue["bbox_confidence"] >= 0.8
    assert issue["bbox_reason"]
```

- [ ] **Step 3: Run tests to verify failure**

Run:

```bash
PYTHONPATH=/private/tmp/pytest-no-readline:. .venv/bin/python -m pytest tests/test_audit_merge.py::test_merge_audits_normalizes_issue_schema_fields tests/test_rule_engine.py::test_rule_review_adds_bbox_confidence_fields -q
```

Expected: fail because new schema fields are not applied.

- [ ] **Step 4: Normalize issues in audit merge**

In `app/audit_merge.py`, import:

```python
from app.audit_issue import normalize_issue
```

In `_with_model`, after model is known and before `_prepare_audit`, ensure audit issues are normalized:

```python
    payload = {**audit, "model": model}
    payload["issues"] = [
        normalize_issue(issue, index=index, source_model=model)
        for index, issue in enumerate(_list(payload.get("issues")), start=1)
    ]
    return _prepare_audit(payload, image_size)
```

Apply the same pattern to wrapper-shape audits before `_prepare_audit`.

- [ ] **Step 5: Validate bbox in rule engine**

In `app/rule_engine.py`, import:

```python
from app.audit_issue import normalize_issue
from app.bbox_validator import validate_bbox
```

Replace `_normalize_issue` body with logic that normalizes first, then validates bbox:

```python
def _normalize_issue(issue: Any, image_size: tuple[int, int]) -> dict[str, Any]:
    output = normalize_issue(issue, index=1)
    validation = validate_bbox(
        output.get("bbox"),
        image_size=image_size,
        text=_issue_text(output),
    )
    output.update(validation)
    if validation["bbox_status"] == "dropped":
        if output.get("bbox") is not None:
            output["bbox_rule_status"] = "dropped_untrusted"
        output["bbox"] = None
    return output
```

Keep `_trusted_bbox` for existing tests only if still needed by other helpers; do not use it for new validation decisions.

- [ ] **Step 6: Run merge and rule tests**

Run:

```bash
PYTHONPATH=/private/tmp/pytest-no-readline:. .venv/bin/python -m pytest tests/test_audit_merge.py tests/test_rule_engine.py -q
```

Expected: pass.

- [ ] **Step 7: Commit**

```bash
git add app/audit_merge.py app/rule_engine.py tests/test_audit_merge.py tests/test_rule_engine.py
git commit -m "Normalize audit issues and validate bbox evidence"
```

---

### Task 5: Add PromptOps Builder and Version Metadata

**Files:**
- Create: `app/prompt_builder.py`
- Add: `tests/test_prompt_builder.py`
- Modify: `app/openai_audit.py`
- Modify: `tests/test_openai_audit.py`

- [ ] **Step 1: Write failing prompt builder tests**

Create `tests/test_prompt_builder.py`:

```python
from app.prompt_builder import (
    PROMPT_VERSION,
    SCHEMA_VERSION,
    build_layered_audit_prompt,
)


def test_build_layered_audit_prompt_includes_versions_and_contract():
    prompt = build_layered_audit_prompt(
        spec_text="JM AI SPEC",
        declared_screen_size=(1440, 900),
        actual_image_size=(2880, 1800),
        scale_context={"x": 2, "y": 2, "uniform": True},
    )

    assert PROMPT_VERSION in prompt
    assert SCHEMA_VERSION in prompt
    assert "JM AI SPEC" in prompt
    assert "bbox" in prompt
    assert "target_element" in prompt
    assert "violation_type" in prompt
    assert "不能编造" in prompt
    assert "1440px × 900px" in prompt
    assert "2880px × 1800px" in prompt


def test_build_layered_audit_prompt_includes_false_positive_constraints():
    prompt = build_layered_audit_prompt(spec_text="SPEC")

    assert "第三方" in prompt
    assert "无法确认" in prompt
    assert "cannot_verify" in prompt
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
PYTHONPATH=/private/tmp/pytest-no-readline:. .venv/bin/python -m pytest tests/test_prompt_builder.py -q
```

Expected: fail because `app.prompt_builder` does not exist.

- [ ] **Step 3: Implement prompt builder**

Create `app/prompt_builder.py`:

```python
from __future__ import annotations

from typing import Any


PROMPT_VERSION = "audit-prompt-v2"
SCHEMA_VERSION = "audit-schema-v2"


def _size_context(
    declared_screen_size: tuple[int, int] | None,
    actual_image_size: tuple[int, int] | None,
    scale_context: dict[str, Any] | None,
) -> str:
    lines = ["## 图片上下文"]
    if actual_image_size:
        lines.append(f"- 上传图片实际像素尺寸：{actual_image_size[0]}px × {actual_image_size[1]}px。")
    if declared_screen_size:
        lines.append(f"- 用户声明稿件基准尺寸：{declared_screen_size[0]}px × {declared_screen_size[1]}px。")
    if scale_context:
        lines.append(
            "- 缩放上下文："
            f"scale_x={scale_context.get('x')}, "
            f"scale_y={scale_context.get('y')}, "
            f"uniform={scale_context.get('uniform')}。"
        )
    return "\n".join(lines)


def build_layered_audit_prompt(
    spec_text: str,
    declared_screen_size: tuple[int, int] | None = None,
    actual_image_size: tuple[int, int] | None = None,
    scale_context: dict[str, Any] | None = None,
) -> str:
    return "\n\n".join(
        [
            f"## Prompt Version\n- prompt_version: {PROMPT_VERSION}\n- schema_version: {SCHEMA_VERSION}",
            (
                "## System Prompt\n"
                "你是 JM AI 设计规范审核助手。必须基于截图可见证据和 JM AI 规范进行审核。"
                "不能编造无法确认的信息；证据不足的内容必须放入 cannot_verify。"
            ),
            _size_context(declared_screen_size, actual_image_size, scale_context),
            (
                "## Output Contract\n"
                "必须只输出一个 JSON 对象。issues 中每个问题尽量包含：id, category, subcategory, "
                "target_element, violation_type, severity, location, current_observation, "
                "spec_expectation, recommendation, confidence, evidence_type, bbox。"
            ),
            (
                "## BBox Rules\n"
                "bbox 必须使用上传原图像素坐标 [x,y,w,h]。无法可靠定位时填 null。"
                "不要输出越界 bbox，不要把右上角问题框到左侧或底部。"
            ),
            (
                "## Tool Request Rules\n"
                "如果颜色、间距、尺寸需要工具验证，请输出 sample_points、regions 或 distances。"
                "颜色、间距、字号等可测量内容不要只凭主观描述下确定结论。"
            ),
            (
                "## False Positive Constraints\n"
                "第三方图片、客户内容、外部品牌素材不应默认判为 JM AI 规范违规。"
                "截图无法确认字体族、精确圆角、阴影参数时必须写入 cannot_verify。"
            ),
            "## JM AI SPEC\n" + spec_text,
        ]
    )
```

- [ ] **Step 4: Run prompt builder tests**

Run:

```bash
PYTHONPATH=/private/tmp/pytest-no-readline:. .venv/bin/python -m pytest tests/test_prompt_builder.py -q
```

Expected: pass.

- [ ] **Step 5: Wire prompt builder into openai audit**

In `app/openai_audit.py`, import:

```python
from app.prompt_builder import PROMPT_VERSION, SCHEMA_VERSION, build_layered_audit_prompt
```

Change `build_audit_prompt(...)` implementation so it delegates to the layered builder:

```python
    return build_layered_audit_prompt(
        spec_text=spec_text,
        declared_screen_size=declared_screen_size,
        actual_image_size=actual_image_size,
        scale_context=scale_context,
    )
```

After parsing JSON in each audit function, add metadata before returning:

```python
    data["_prompt_version"] = PROMPT_VERSION
    data["_schema_version"] = SCHEMA_VERSION
    return data
```

Apply to strict Responses API and chat audit parse paths.

- [ ] **Step 6: Add openai audit metadata test**

Append to `tests/test_openai_audit.py`:

```python
def test_parse_audit_payload_can_store_prompt_metadata():
    data = parse_lenient_chat_audit_json(
        '{"screen_context":"首页","overall_conclusion":"完成","issues":[]}',
        image_size=(100, 100),
    )
    data["_prompt_version"] = "audit-prompt-v2"
    data["_schema_version"] = "audit-schema-v2"

    assert data["_prompt_version"] == "audit-prompt-v2"
    assert data["_schema_version"] == "audit-schema-v2"
```

- [ ] **Step 7: Run prompt and audit tests**

Run:

```bash
PYTHONPATH=/private/tmp/pytest-no-readline:. .venv/bin/python -m pytest tests/test_prompt_builder.py tests/test_openai_audit.py -q
```

Expected: pass.

- [ ] **Step 8: Commit**

```bash
git add app/prompt_builder.py app/openai_audit.py tests/test_prompt_builder.py tests/test_openai_audit.py
git commit -m "Add layered audit prompt builder"
```

---

### Task 6: Add Model Error Classification and Fallback Metadata

**Files:**
- Create: `app/model_errors.py`
- Add: `tests/test_model_errors.py`
- Modify: `app/task_runner.py`
- Modify: `tests/test_task_runner.py`

- [ ] **Step 1: Write failing model error tests**

Create `tests/test_model_errors.py`:

```python
from app.model_errors import classify_model_error, model_failure


def test_classify_model_error_detects_capacity():
    assert classify_model_error("Selected model is at capacity. Please try a different model.") == "capacity"


def test_classify_model_error_detects_timeout_and_invalid_json():
    assert classify_model_error("request timed out") == "timeout"
    assert classify_model_error("模型返回的 JSON 无法解析") == "invalid_json"


def test_model_failure_returns_standard_shape():
    failure = model_failure("GPT-5.5", RuntimeError("timeout"))

    assert failure["model"] == "GPT-5.5"
    assert failure["error_type"] == "timeout"
    assert failure["error"] == "timeout"
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
PYTHONPATH=/private/tmp/pytest-no-readline:. .venv/bin/python -m pytest tests/test_model_errors.py -q
```

Expected: fail because `app.model_errors` does not exist.

- [ ] **Step 3: Implement model error helpers**

Create `app/model_errors.py`:

```python
from __future__ import annotations


def classify_model_error(message: object) -> str:
    text = str(message or "").lower()
    if "capacity" in text or "try a different model" in text:
        return "capacity"
    if "timeout" in text or "timed out" in text:
        return "timeout"
    if "rate limit" in text or "429" in text:
        return "rate_limit"
    if "json" in text or "无法解析" in text:
        return "invalid_json"
    if "empty" in text or "空" in text:
        return "empty_response"
    return "unknown"


def model_failure(model: str, error: object) -> dict[str, str]:
    message = str(error or "").strip() or error.__class__.__name__
    return {
        "model": model,
        "error_type": classify_model_error(message),
        "error": message[:500],
    }
```

- [ ] **Step 4: Run model error tests**

Run:

```bash
PYTHONPATH=/private/tmp/pytest-no-readline:. .venv/bin/python -m pytest tests/test_model_errors.py -q
```

Expected: pass.

- [ ] **Step 5: Use standard failures in task runner dual auditor**

In `app/task_runner.py`, import:

```python
from app.model_errors import model_failure
```

In `_dual_auditor`, replace manual error attempt creation:

```python
                attempts.append({"model": model, "error": _short_error(exc)})
```

with:

```python
                attempts.append(model_failure(model, exc))
```

When building `failures`, include `error_type`:

```python
            failures = [
                {
                    "model": str(attempt.get("model") or ""),
                    "error_type": str(attempt.get("error_type") or "unknown"),
                    "error": str(attempt.get("error") or ""),
                }
                for attempt in attempts[1:]
                if attempt.get("error")
            ]
```

- [ ] **Step 6: Add task runner failure type test**

Append this test to `tests/test_task_runner.py` near `test_run_task_dual_mode_succeeds_when_one_model_fails`:

```python
def test_run_task_dual_mode_records_model_failure_type(monkeypatch, tmp_path):
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
            return None

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
            raise RuntimeError("Selected model is at capacity. Please try a different model.")
        return _issue_audit(model)

    monkeypatch.setattr(task_runner, "OpenAI", FakeClient)
    monkeypatch.setattr(task_runner, "audit_image_with_chat", fake_chat_audit)
    spec_path = tmp_path / "spec.md"
    spec_path.write_text("spec", encoding="utf-8")
    monkeypatch.setattr(task_runner, "SPEC_PATH", spec_path)

    run_task(settings, task.id)

    artifact_dir = dirs.artifacts / "image-001"
    merged_audit = json.loads((artifact_dir / "audit.json").read_text(encoding="utf-8"))

    assert merged_audit["model_comparison"]["model_failures"] == [
        {
            "model": "Kimi-K2.6",
            "error_type": "capacity",
            "error": "Selected model is at capacity. Please try a different model.",
        }
    ]
```

- [ ] **Step 7: Run tests**

Run:

```bash
PYTHONPATH=/private/tmp/pytest-no-readline:. .venv/bin/python -m pytest tests/test_model_errors.py tests/test_task_runner.py -q
```

Expected: pass.

- [ ] **Step 8: Commit**

```bash
git add app/model_errors.py app/task_runner.py tests/test_model_errors.py tests/test_task_runner.py
git commit -m "Classify audit model failures"
```

---

### Task 7: Standardize Rule Hits for Color and Spacing Evidence

**Files:**
- Modify: `app/rule_engine.py`
- Modify: `tests/test_rule_engine.py`

- [ ] **Step 1: Add failing rule hit tests**

Append to `tests/test_rule_engine.py`:

```python
def test_rule_review_records_color_rule_hit_when_enriching_issue():
    audit = _audit(
        issues=[
            {
                "category": "色彩",
                "location": "邀好友赚套餐按钮",
                "current_observation": "按钮颜色不符合规范。",
                "bbox": [10, 10, 40, 20],
            }
        ]
    )
    tokens = {
        "samples": [
            {
                "label": "邀好友赚套餐按钮",
                "x": 20,
                "y": 20,
                "hex": "#F37021",
                "nearest_jm_token": {"name": "ai/ai-normal", "hex": "#6B36FA", "distance": 190.0},
                "off_token_candidate": True,
            }
        ]
    }

    result = apply_rule_review(audit, tokens=tokens, measurements={}, image_size=(100, 100))

    assert result["rule_hits"][0]["rule_id"] == "color.off_token_sample"
    assert result["rule_hits"][0]["result"] == "failed"
    assert result["rule_hits"][0]["measured_value"] == "#F37021"
    assert result["issues"][0]["rule_sources"] == ["color.off_token_sample"]
    assert result["issues"][0]["evidence_type"] == "model_with_rule"


def test_rule_review_records_spacing_rule_hit():
    result = apply_rule_review(
        _audit(),
        tokens={},
        measurements={
            "distances": [
                {
                    "id": "header-gap",
                    "gap_design_px": 18.4,
                    "nearest_spacing": {"token": 16, "delta": 2.4, "passes_with_1px_tolerance": False},
                }
            ]
        },
        image_size=(100, 100),
    )

    assert result["rule_hits"][0]["rule_id"] == "spacing.off_token_gap"
    assert result["rule_hits"][0]["measured_value"] == "18.4px"
    assert result["rule_hits"][0]["expected_value"] == "16px"
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
PYTHONPATH=/private/tmp/pytest-no-readline:. .venv/bin/python -m pytest tests/test_rule_engine.py::test_rule_review_records_color_rule_hit_when_enriching_issue tests/test_rule_engine.py::test_rule_review_records_spacing_rule_hit -q
```

Expected: fail because `rule_hits` is missing.

- [ ] **Step 3: Implement rule hit helpers**

In `app/rule_engine.py`, add:

```python
def _rule_hit(
    rule_id: str,
    category: str,
    subcategory: str,
    measured_value: Any,
    expected_value: Any,
    delta: Any,
    confidence: float,
    evidence_type: str,
) -> dict[str, Any]:
    return {
        "rule_id": rule_id,
        "category": category,
        "subcategory": subcategory,
        "result": "failed",
        "measured_value": str(measured_value),
        "expected_value": str(expected_value),
        "delta": delta,
        "confidence": confidence,
        "evidence_type": evidence_type,
    }
```

In `apply_rule_review`, initialize:

```python
    reviewed["rule_hits"] = _list(reviewed.get("rule_hits"))
```

Make `_color_issues_from_samples` return tuples or embed `rule_hit`; the simplest local change is to add `rule_hit` inside each rule issue:

```python
                "rule_hit": _rule_hit(
                    "color.off_token_sample",
                    "color_gradient",
                    "off_token_color",
                    hex_value,
                    nearest_hex or nearest_name,
                    distance,
                    0.9,
                    "sampled_color",
                ),
```

Do the same for spacing:

```python
                "rule_hit": _rule_hit(
                    "spacing.off_token_gap",
                    "spacing_layout",
                    "off_spacing_token",
                    f"{measured}px",
                    f"{token}px",
                    delta,
                    0.85,
                    "measured_spacing",
                ),
```

In `_upsert_rule_finding`, when a `rule_hit` exists:

```python
    rule_hit = rule_issue.get("rule_hit")
    if isinstance(rule_hit, dict):
        warnings.append(rule_hit)  # only if using a separate param is not yet available
```

Prefer a cleaner signature:

```python
def _upsert_rule_finding(issues, warnings, rule_hits, rule_issue):
```

Append rule hit to `rule_hits`, remove `rule_hit` from warning/issue display payload, and add `rule_sources` plus `evidence_type` to matched issues:

```python
    if isinstance(rule_hit, dict):
        rule_hits.append(rule_hit)
        rule_issue = {key: value for key, value in rule_issue.items() if key != "rule_hit"}
```

When matched:

```python
    sources = _list(match.get("rule_sources"))
    if rule_hit and rule_hit["rule_id"] not in sources:
        sources.append(rule_hit["rule_id"])
    match["rule_sources"] = sources
    match["evidence_type"] = "model_with_rule"
```

- [ ] **Step 4: Run rule engine tests**

Run:

```bash
PYTHONPATH=/private/tmp/pytest-no-readline:. .venv/bin/python -m pytest tests/test_rule_engine.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add app/rule_engine.py tests/test_rule_engine.py
git commit -m "Standardize rule hit evidence"
```

---

### Task 8: Upgrade Report Summary and Issue Table

**Files:**
- Modify: `app/report_renderer.py`
- Modify: `tests/test_report_renderer.py`

- [ ] **Step 1: Add failing report summary test**

Append to `tests/test_report_renderer.py`:

```python
def test_render_report_html_includes_quality_summary_metrics():
    audit = _audit_payload()
    audit["issues"][0].update(
        {
            "category": "color_gradient",
            "subcategory": "off_token_color",
            "target_element": "主按钮",
            "evidence_type": "model_with_rule",
            "bbox_status": "trusted",
            "bbox_confidence": 0.9,
            "source_models": ["GPT-5.5", "Kimi-K2.6"],
            "rule_sources": ["color.off_token_sample"],
            "agreement": "both",
        }
    )
    audit["rule_hits"] = [{"rule_id": "color.off_token_sample"}]

    html = render_report_html(
        task={"title": "审核", "summary": "完成"},
        image_results=[{"filename": "image-001.png", "audit": audit, "artifacts": {}}],
    )

    assert "质量摘要" in html
    assert "问题总数" in html
    assert "规则命中问题" in html
    assert "MoE 一致问题" in html
    assert "有截图证据" in html
```

- [ ] **Step 2: Add failing issue metadata table test**

Append to `tests/test_report_renderer.py`:

```python
def test_issues_table_shows_standard_issue_metadata():
    audit = _audit_payload()
    audit["issues"][0].update(
        {
            "category": "color_gradient",
            "subcategory": "off_token_color",
            "target_element": "主按钮",
            "evidence_type": "model_with_rule",
            "bbox_confidence": 0.9,
            "source_models": ["GPT-5.5"],
            "rule_sources": ["color.off_token_sample"],
        }
    )

    html = render_report_html(
        task={"title": "审核", "summary": "完成"},
        image_results=[{"filename": "image-001.png", "audit": audit, "artifacts": {}}],
    )

    assert "问题类型" in html
    assert "目标元素" in html
    assert "证据来源" in html
    assert "color_gradient.off_token_color" in html
    assert "model_with_rule" in html
    assert "color.off_token_sample" in html
```

- [ ] **Step 3: Run tests to verify failure**

Run:

```bash
PYTHONPATH=/private/tmp/pytest-no-readline:. .venv/bin/python -m pytest tests/test_report_renderer.py::test_render_report_html_includes_quality_summary_metrics tests/test_report_renderer.py::test_issues_table_shows_standard_issue_metadata -q
```

Expected: fail because summary and metadata are not rendered.

- [ ] **Step 4: Implement quality summary**

In `app/report_renderer.py`, add:

```python
def _quality_summary(audit: dict[str, Any]) -> str:
    issues = [item for item in audit.get("issues", []) if isinstance(item, dict)]
    high = sum(1 for item in issues if item.get("severity") == "高")
    medium = sum(1 for item in issues if item.get("severity") == "中")
    low = sum(1 for item in issues if item.get("severity") == "低")
    agreed = sum(1 for item in issues if item.get("agreement") in {"both", "promoted_candidate"})
    rule_count = sum(1 for item in issues if item.get("rule_sources"))
    screenshot_count = sum(1 for item in issues if item.get("bbox") and item.get("bbox_status") != "dropped")
    cannot_verify = len(audit.get("cannot_verify") or [])
    return f"""
      <section class="quality-summary">
        <h3>质量摘要</h3>
        <dl>
          <div><dt>问题总数</dt><dd>{_text(len(issues))}</dd></div>
          <div><dt>高/中/低风险</dt><dd>{_text(high)} / {_text(medium)} / {_text(low)}</dd></div>
          <div><dt>MoE 一致问题</dt><dd>{_text(agreed)}</dd></div>
          <div><dt>规则命中问题</dt><dd>{_text(rule_count)}</dd></div>
          <div><dt>有截图证据</dt><dd>{_text(screenshot_count)}</dd></div>
          <div><dt>待确认</dt><dd>{_text(cannot_verify)}</dd></div>
        </dl>
      </section>
    """
```

Call `_quality_summary(audit)` after `_core_conclusion(audit)` in `_image_section`.

- [ ] **Step 5: Upgrade issue table columns**

In `_issues_table`, change rows to include:

```python
issue_type = ".".join(
    part for part in [str(issue.get("category") or ""), str(issue.get("subcategory") or "")]
    if part
)
source_text = "；".join(
    [
        f"证据：{issue.get('evidence_type') or 'model_only'}",
        f"模型：{'、'.join(str(item) for item in issue.get('source_models') or []) or '无'}",
        f"规则：{'、'.join(str(item) for item in issue.get('rule_sources') or []) or '无'}",
        f"bbox：{issue.get('bbox_confidence') if issue.get('bbox_confidence') is not None else '无'}",
    ]
)
```

Render columns:

```html
<th>编号</th><th>问题类型</th><th>目标元素</th><th>位置</th><th>当前表现</th><th>修改建议</th><th>证据来源</th><th>参考素材</th>
```

Keep existing spec reference image cell.

- [ ] **Step 6: Add CSS for quality summary**

Inside `render_report_html` style block, add:

```css
    .quality-summary { margin-top: 12px; border: 1px solid var(--line); border-radius: 8px; padding: 12px; background: #fbfbfc; }
    .quality-summary dl { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin: 0; }
    .quality-summary div { border: 1px solid var(--line); border-radius: 6px; padding: 8px; background: var(--card); }
    .quality-summary dt { color: var(--muted); font-size: 12px; }
    .quality-summary dd { margin: 4px 0 0; font-weight: 700; }
```

- [ ] **Step 7: Run report tests**

Run:

```bash
PYTHONPATH=/private/tmp/pytest-no-readline:. .venv/bin/python -m pytest tests/test_report_renderer.py -q
```

Expected: pass.

- [ ] **Step 8: Commit**

```bash
git add app/report_renderer.py tests/test_report_renderer.py
git commit -m "Upgrade audit report summary and issue metadata"
```

---

### Task 9: Run Integrated Verification

**Files:**
- No direct code changes unless fixing failures from this task.

- [ ] **Step 1: Run focused suite**

Run:

```bash
PYTHONPATH=/private/tmp/pytest-no-readline:. .venv/bin/python -m pytest \
  tests/test_audit_taxonomy.py \
  tests/test_audit_issue.py \
  tests/test_bbox_validator.py \
  tests/test_prompt_builder.py \
  tests/test_model_errors.py \
  tests/test_audit_merge.py \
  tests/test_rule_engine.py \
  tests/test_evidence_tools.py \
  tests/test_openai_audit.py \
  tests/test_report_renderer.py \
  tests/test_task_runner.py \
  -q
```

Expected: pass.

- [ ] **Step 2: Run full suite**

Run:

```bash
PYTHONPATH=/private/tmp/pytest-no-readline:. .venv/bin/python -m pytest -q
```

Expected: pass.

- [ ] **Step 3: Manual artifact compatibility check**

Pick one existing successful task artifact under `data/uploads/<task_id>/artifacts/` if available. Confirm:

```bash
find data/uploads -name audit.json | head
```

If an audit JSON exists, run the smallest report rendering path through existing tests or a one-off local script only if needed. Do not modify production data.

Expected:

- old `audit.json` remains parseable
- report renderer does not crash on missing new fields
- issue table falls back to model-only metadata

- [ ] **Step 4: Commit fixes if verification reveals issues**

If fixes are required:

```bash
git add app tests
git commit -m "Fix audit platform upgrade integration"
```

If no fixes are required, do not create an empty commit.

---

## Implementation Notes

- Keep DB schema unchanged in this round.
- Keep old report URLs and artifact paths stable.
- Preserve old model output compatibility by normalizing missing fields.
- Avoid adding new third-party dependencies.
- Do not start with OCR or component detection.
- Do not claim model accuracy improvement without a future evaluation dataset.

## Completion Criteria

This implementation is complete when:

- taxonomy tests pass
- issue normalization tests pass
- bbox validator tests pass
- prompt builder tests pass
- model error tests pass
- merge/rule/evidence/report/task runner tests pass
- full pytest suite passes
- HTML report includes quality summary and issue metadata
- non-trusted bbox values do not produce issue crops
- old audit payloads still render without crashing
