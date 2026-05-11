# Size Experiment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an offline size experiment tool that compares baseline, scaled-metrics, and normalized-preview audit variants without changing the production task flow.

**Architecture:** Add deterministic experiment helpers in `app/size_experiment.py`, then add a thin CLI wrapper in `scripts/run_size_experiment.py`. The tool writes isolated output under `data/experiments/<run_id>/...`, reuses existing audit and evidence-tool code, and never modifies existing uploads, reports, database schema, or web routes.

**Tech Stack:** Python 3.11+, FastAPI project utilities, Pillow, pytest, existing OpenAI audit wrappers, existing measurement scripts.

---

## File Structure

- Create `app/size_experiment.py`
  - Owns deterministic helpers and orchestration: design-size parsing, scale metadata, normalized preview generation, variant result records, comparison JSON, and comparison HTML rendering.
- Create `scripts/run_size_experiment.py`
  - Thin CLI entrypoint. Parses args, loads `Settings`, resolves task/image input, and calls `app.size_experiment`.
- Create `tests/test_size_experiment.py`
  - Tests deterministic helpers and orchestration with mocked model/evidence functions.
- Modify `app/evidence_tools.py`
  - Add an optional `design_size` parameter to `run_measurements`; when provided, pass `--design-size WIDTHxHEIGHT`.
- Modify `app/openai_audit.py`
  - Add prompt support for explicit scale context and optional normalized-preview image input. Existing callers keep current behavior by default.

No changes to:

- `app/task_runner.py` production logic
- `app/routes/tasks.py`
- database schema
- upload templates
- existing task report paths

## Task 1: Deterministic Size Helpers

**Files:**
- Create: `app/size_experiment.py`
- Test: `tests/test_size_experiment.py`

- [ ] **Step 1: Write failing tests for size parsing and scale metadata**

Add to `tests/test_size_experiment.py`:

```python
from __future__ import annotations

import pytest

from app.size_experiment import (
    DesignSizeError,
    compute_scale,
    normalized_preview_size,
    parse_design_size,
)


def test_parse_design_size_accepts_width_x_height():
    assert parse_design_size("1440x900") == (1440, 900)
    assert parse_design_size("1440X900") == (1440, 900)
    assert parse_design_size(" 1440 x 900 ") == (1440, 900)


@pytest.mark.parametrize("value", ["", "1440", "1440x", "x900", "0x900", "1440x0", "-1x900", "1440.5x900"])
def test_parse_design_size_rejects_invalid_values(value):
    with pytest.raises(DesignSizeError):
        parse_design_size(value)


def test_compute_scale_marks_uniform_scale():
    scale = compute_scale(actual_size=(2880, 1800), declared_size=(1440, 900))

    assert scale == {
        "x": 2.0,
        "y": 2.0,
        "uniform": True,
        "aspect_ratio_mismatch": False,
    }


def test_compute_scale_marks_non_uniform_scale():
    scale = compute_scale(actual_size=(2880, 2000), declared_size=(1440, 900))

    assert scale["x"] == 2.0
    assert round(scale["y"], 4) == 2.2222
    assert scale["uniform"] is False
    assert scale["aspect_ratio_mismatch"] is True


def test_normalized_preview_size_scales_by_declared_width_without_stretching_height():
    assert normalized_preview_size(actual_size=(2880, 1800), declared_size=(1440, 900)) == (1440, 900)
    assert normalized_preview_size(actual_size=(2880, 2000), declared_size=(1440, 900)) == (1440, 1000)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_size_experiment.py -q
```

Expected: FAIL because `app.size_experiment` does not exist.

- [ ] **Step 3: Implement minimal helpers**

Create `app/size_experiment.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any, Callable

from PIL import Image


class DesignSizeError(ValueError):
    pass


DesignSize = tuple[int, int]


def parse_design_size(value: str) -> DesignSize:
    normalized = value.lower().replace(" ", "")
    if "x" not in normalized:
        raise DesignSizeError("design size must use WIDTHxHEIGHT")
    width_text, height_text = normalized.split("x", 1)
    if not width_text.isdecimal() or not height_text.isdecimal():
        raise DesignSizeError("design size must contain positive integers")
    width = int(width_text)
    height = int(height_text)
    if width <= 0 or height <= 0:
        raise DesignSizeError("design size must contain positive integers")
    return width, height


def compute_scale(actual_size: DesignSize, declared_size: DesignSize) -> dict[str, Any]:
    actual_width, actual_height = actual_size
    declared_width, declared_height = declared_size
    scale_x = actual_width / declared_width
    scale_y = actual_height / declared_height
    uniform = abs(scale_x - scale_y) <= 0.02
    return {
        "x": round(scale_x, 4),
        "y": round(scale_y, 4),
        "uniform": uniform,
        "aspect_ratio_mismatch": not uniform,
    }


def normalized_preview_size(actual_size: DesignSize, declared_size: DesignSize) -> DesignSize:
    actual_width, actual_height = actual_size
    declared_width, _ = declared_size
    normalized_height = round(actual_height * declared_width / actual_width)
    return declared_width, normalized_height
```

- [ ] **Step 4: Run tests to verify helpers pass**

Run:

```bash
.venv/bin/python -m pytest tests/test_size_experiment.py -q
```

Expected: PASS for the helper tests.

## Task 2: Normalized Preview Generation

**Files:**
- Modify: `app/size_experiment.py`
- Test: `tests/test_size_experiment.py`

- [ ] **Step 1: Write failing tests for preview generation**

Append to `tests/test_size_experiment.py`:

```python
from PIL import Image

from app.size_experiment import create_normalized_preview


def test_create_normalized_preview_writes_resized_copy(tmp_path):
    source = tmp_path / "source.png"
    output = tmp_path / "normalized.png"
    Image.new("RGB", (20, 10), color=(107, 54, 250)).save(source)

    result = create_normalized_preview(source, output, declared_size=(10, 5))

    assert result == (10, 5)
    with Image.open(output) as image:
        assert image.size == (10, 5)


def test_create_normalized_preview_does_not_modify_source(tmp_path):
    source = tmp_path / "source.png"
    output = tmp_path / "normalized.png"
    Image.new("RGB", (20, 12), color=(107, 54, 250)).save(source)

    create_normalized_preview(source, output, declared_size=(10, 5))

    with Image.open(source) as image:
        assert image.size == (20, 12)
    with Image.open(output) as image:
        assert image.size == (10, 6)
```

- [ ] **Step 2: Run preview tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_size_experiment.py::test_create_normalized_preview_writes_resized_copy tests/test_size_experiment.py::test_create_normalized_preview_does_not_modify_source -q
```

Expected: FAIL because `create_normalized_preview` is not implemented.

- [ ] **Step 3: Implement preview generation**

Add to `app/size_experiment.py`:

```python
def create_normalized_preview(
    source_path: Path,
    output_path: Path,
    declared_size: DesignSize,
) -> DesignSize:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source_path) as image:
        target_size = normalized_preview_size(image.size, declared_size)
        resized = image.convert("RGB").resize(target_size, Image.Resampling.LANCZOS)
        resized.save(output_path)
    return target_size
```

- [ ] **Step 4: Run preview tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_size_experiment.py -q
```

Expected: PASS.

## Task 3: Measurement Tool Design-Size Support

**Files:**
- Modify: `app/evidence_tools.py`
- Test: `tests/test_size_experiment.py`

- [ ] **Step 1: Write failing test for `run_measurements` argument forwarding**

Append to `tests/test_size_experiment.py`:

```python
from app import evidence_tools


def test_run_measurements_passes_design_size(monkeypatch, tmp_path):
    captured = {}

    def fake_run(args):
        captured["args"] = args

    monkeypatch.setattr(evidence_tools, "_run", fake_run)

    evidence_tools.run_measurements(
        tmp_path / "image.png",
        tmp_path / "regions.json",
        tmp_path / "measurements.json",
        tmp_path / "crops",
        design_size=(1440, 900),
    )

    assert "--design-size" in captured["args"]
    design_size_index = captured["args"].index("--design-size")
    assert captured["args"][design_size_index + 1] == "1440x900"
```

- [ ] **Step 2: Run forwarding test to verify it fails**

Run:

```bash
.venv/bin/python -m pytest tests/test_size_experiment.py::test_run_measurements_passes_design_size -q
```

Expected: FAIL because `run_measurements` does not accept `design_size`.

- [ ] **Step 3: Modify `run_measurements` minimally**

In `app/evidence_tools.py`, replace `run_measurements` with:

```python
def run_measurements(
    image_path: Path,
    regions_path: Path,
    output_path: Path,
    crop_dir: Path,
    design_size: tuple[int, int] | None = None,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    args = [
        sys.executable,
        str(SCRIPTS_DIR / "measure_regions.py"),
        str(image_path),
        str(regions_path),
        "--output",
        str(output_path),
        "--crop-dir",
        str(crop_dir),
    ]
    if design_size:
        args.extend(["--design-size", f"{design_size[0]}x{design_size[1]}"])
    _run(args)
```

Existing production callers remain valid because the new parameter defaults to `None`.

- [ ] **Step 4: Run related tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_size_experiment.py tests/test_task_runner.py -q
```

Expected: PASS.

## Task 4: Prompt and Audit Support for Experiment Variants

**Files:**
- Modify: `app/openai_audit.py`
- Test: `tests/test_openai_audit.py`

- [ ] **Step 1: Write failing prompt tests**

Append to `tests/test_openai_audit.py`:

```python
def test_build_audit_prompt_includes_scale_context_for_experiment():
    prompt = build_audit_prompt(
        "SPEC",
        declared_screen_size=(1440, 900),
        actual_image_size=(2880, 1800),
        scale_context={"x": 2.0, "y": 2.0, "uniform": True, "aspect_ratio_mismatch": False},
        experiment_variant="scaled-metrics",
    )

    assert "实验变体：scaled-metrics" in prompt
    assert "scale_x=2.0" in prompt
    assert "scale_y=2.0" in prompt
    assert "所有 bbox 仍必须使用上传原图的像素坐标" in prompt


def test_build_audit_prompt_mentions_normalized_preview_contract():
    prompt = build_audit_prompt(
        "SPEC",
        declared_screen_size=(1440, 900),
        actual_image_size=(2880, 1800),
        normalized_preview_size=(1440, 900),
        experiment_variant="normalized-preview",
    )

    assert "实验变体：normalized-preview" in prompt
    assert "规范化辅助图尺寸：1440px × 900px" in prompt
    assert "规范化辅助图只用于理解布局密度" in prompt
    assert "颜色、细线、截图标注坐标以原图为准" in prompt
```

- [ ] **Step 2: Run prompt tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_openai_audit.py::test_build_audit_prompt_includes_scale_context_for_experiment tests/test_openai_audit.py::test_build_audit_prompt_mentions_normalized_preview_contract -q
```

Expected: FAIL because `build_audit_prompt` lacks these parameters.

- [ ] **Step 3: Extend `build_audit_prompt` without changing default behavior**

In `app/openai_audit.py`, change the function signature to:

```python
def build_audit_prompt(
    spec_text: str,
    declared_screen_size: tuple[int, int] | None = None,
    actual_image_size: tuple[int, int] | None = None,
    scale_context: dict[str, Any] | None = None,
    normalized_preview_size: tuple[int, int] | None = None,
    experiment_variant: str | None = None,
) -> str:
```

Inside the existing `if actual_image_size or declared_screen_size:` block, after declared size lines, add:

```python
        if scale_context:
            lines.append(
                "- 缩放上下文："
                f"scale_x={scale_context['x']}, "
                f"scale_y={scale_context['y']}, "
                f"uniform={scale_context['uniform']}。"
            )
            lines.append(
                "- 所有 bbox 仍必须使用上传原图的像素坐标；间距、组件尺寸、字号和布局密度判断可参考折算后的设计像素。"
            )
```

Before the final `lines.append("- 如果实际图片像素尺寸...")`, add:

```python
        if experiment_variant:
            lines.append(f"- 实验变体：{experiment_variant}。")
        if normalized_preview_size:
            lines.append(
                f"- 规范化辅助图尺寸：{normalized_preview_size[0]}px × {normalized_preview_size[1]}px。"
            )
            lines.append(
                "- 规范化辅助图只用于理解布局密度；颜色、细线、截图标注坐标以原图为准。"
            )
```

- [ ] **Step 4: Add optional normalized image input to audit functions**

Change `audit_image` signature to:

```python
def audit_image(
    client: _OpenAIClient,
    model: str,
    image_path: Path,
    spec_text: str,
    reasoning_effort: str | None = None,
    declared_screen_size: tuple[int, int] | None = None,
    scale_context: dict[str, Any] | None = None,
    normalized_preview_path: Path | None = None,
    experiment_variant: str | None = None,
) -> dict[str, Any]:
```

Before building the request, compute:

```python
    normalized_size = _image_size(normalized_preview_path) if normalized_preview_path else None
```

Pass new values to `build_audit_prompt`.

Build content as a local list:

```python
    content: list[dict[str, Any]] = [
        {
            "type": "input_text",
            "text": build_audit_prompt(
                spec_text,
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
```

Use `content` in the request.

Apply the same signature extension to `audit_image_with_chat`, with chat image content:

```python
    content: list[dict[str, Any]] = [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": image_data_url(image_path)}},
    ]
    if normalized_preview_path:
        content.append({"type": "image_url", "image_url": {"url": image_data_url(normalized_preview_path)}})
```

Existing callers remain valid because new parameters default to `None`.

- [ ] **Step 5: Run OpenAI audit tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_openai_audit.py -q
```

Expected: PASS.

## Task 5: Variant Runner and Comparison Data

**Files:**
- Modify: `app/size_experiment.py`
- Test: `tests/test_size_experiment.py`

- [ ] **Step 1: Write failing tests for variant result and comparison resilience**

Append to `tests/test_size_experiment.py`:

```python
from app.size_experiment import (
    VariantResult,
    build_comparison,
    issue_key,
    summarize_variant,
)


def test_issue_key_uses_category_location_and_observation():
    issue = {
        "category": "间距 - 布局",
        "location": "主内容区",
        "current_observation": "卡片间距过小",
    }

    assert issue_key(issue) == "间距 - 布局|主内容区|卡片间距过小"


def test_summarize_variant_handles_empty_audit():
    result = VariantResult(name="baseline", status="succeeded", audit={}, paths={})

    summary = summarize_variant(result)

    assert summary["status"] == "succeeded"
    assert summary["issue_count"] == 0
    assert summary["cannot_verify_count"] == 0
    assert summary["bbox_coverage"] == {"with_bbox": 0, "total": 0}


def test_build_comparison_keeps_failed_variant():
    comparison = build_comparison(
        image_path="image.png",
        actual_size=(2880, 1800),
        declared_size=(1440, 900),
        scale={"x": 2.0, "y": 2.0, "uniform": True, "aspect_ratio_mismatch": False},
        variants=[
            VariantResult(name="baseline", status="failed", audit={}, paths={}, error_message="model failed"),
            VariantResult(name="scaled_metrics", status="succeeded", audit={"issues": []}, paths={"audit": "scaled/audit.json"}),
        ],
    )

    assert comparison["variants"]["baseline"]["status"] == "failed"
    assert comparison["variants"]["baseline"]["error_message"] == "model failed"
    assert comparison["variants"]["scaled_metrics"]["status"] == "succeeded"
    assert "diff" in comparison
```

- [ ] **Step 2: Run comparison tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_size_experiment.py::test_issue_key_uses_category_location_and_observation tests/test_size_experiment.py::test_summarize_variant_handles_empty_audit tests/test_size_experiment.py::test_build_comparison_keeps_failed_variant -q
```

Expected: FAIL because comparison helpers do not exist.

- [ ] **Step 3: Implement comparison helpers**

Add to `app/size_experiment.py`:

```python
@dataclass(frozen=True)
class VariantResult:
    name: str
    status: str
    audit: dict[str, Any]
    paths: dict[str, str]
    error_message: str | None = None


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def issue_key(issue: dict[str, Any]) -> str:
    return "|".join(
        [
            str(issue.get("category") or ""),
            str(issue.get("location") or ""),
            str(issue.get("current_observation") or ""),
        ]
    )


def _bbox_coverage(issues: list[Any]) -> dict[str, int]:
    total = len([item for item in issues if isinstance(item, dict)])
    with_bbox = 0
    for item in issues:
        if isinstance(item, dict) and isinstance(item.get("bbox"), list):
            with_bbox += 1
    return {"with_bbox": with_bbox, "total": total}


def summarize_variant(result: VariantResult) -> dict[str, Any]:
    issues = [item for item in _list(result.audit.get("issues")) if isinstance(item, dict)]
    cannot_verify = _list(result.audit.get("cannot_verify"))
    summary = {
        "status": result.status,
        "error_message": result.error_message,
        "paths": result.paths,
        "overall_conclusion": result.audit.get("overall_conclusion"),
        "screen_context": result.audit.get("screen_context"),
        "issue_count": len(issues),
        "cannot_verify_count": len(cannot_verify),
        "bbox_coverage": _bbox_coverage(issues),
    }
    return summary


def _issue_map(result: VariantResult) -> dict[str, dict[str, Any]]:
    output = {}
    for issue in _list(result.audit.get("issues")):
        if isinstance(issue, dict):
            output[issue_key(issue)] = issue
    return output


def build_comparison(
    image_path: str,
    actual_size: DesignSize,
    declared_size: DesignSize,
    scale: dict[str, Any],
    variants: list[VariantResult],
) -> dict[str, Any]:
    variant_summaries = {result.name: summarize_variant(result) for result in variants}
    issue_maps = {result.name: _issue_map(result) for result in variants if result.status == "succeeded"}
    baseline = issue_maps.get("baseline", {})
    diff = {
        "issue_count_by_category": {},
        "new_issues": [],
        "removed_issues": [],
        "changed_severity": [],
        "changed_confidence": [],
        "cannot_verify_count": {
            name: summary["cannot_verify_count"] for name, summary in variant_summaries.items()
        },
        "bbox_coverage": {
            name: summary["bbox_coverage"] for name, summary in variant_summaries.items()
        },
        "layout_context": {
            name: summary.get("screen_context") for name, summary in variant_summaries.items()
        },
    }
    for name, issues in issue_maps.items():
        counts: dict[str, int] = {}
        for issue in issues.values():
            category = str(issue.get("category") or "未分类")
            counts[category] = counts.get(category, 0) + 1
        diff["issue_count_by_category"][name] = counts
        if name != "baseline":
            diff["new_issues"].extend(
                {"variant": name, "key": key} for key in sorted(set(issues) - set(baseline))
            )
            diff["removed_issues"].extend(
                {"variant": name, "key": key} for key in sorted(set(baseline) - set(issues))
            )
            for key in sorted(set(issues) & set(baseline)):
                before = baseline[key]
                after = issues[key]
                if before.get("severity") != after.get("severity"):
                    diff["changed_severity"].append(
                        {
                            "variant": name,
                            "key": key,
                            "baseline": before.get("severity"),
                            "current": after.get("severity"),
                        }
                    )
                if before.get("confidence") != after.get("confidence"):
                    diff["changed_confidence"].append(
                        {
                            "variant": name,
                            "key": key,
                            "baseline": before.get("confidence"),
                            "current": after.get("confidence"),
                        }
                    )
    return {
        "image": image_path,
        "actual_size": list(actual_size),
        "declared_size": list(declared_size),
        "scale": scale,
        "variants": variant_summaries,
        "diff": diff,
    }
```

- [ ] **Step 4: Run comparison tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_size_experiment.py -q
```

Expected: PASS.

## Task 6: Comparison HTML Rendering

**Files:**
- Modify: `app/size_experiment.py`
- Test: `tests/test_size_experiment.py`

- [ ] **Step 1: Write failing HTML escaping test**

Append to `tests/test_size_experiment.py`:

```python
from app.size_experiment import render_comparison_html


def test_render_comparison_html_escapes_model_text():
    html = render_comparison_html(
        {
            "image": "image.png",
            "actual_size": [100, 50],
            "declared_size": [100, 50],
            "scale": {"x": 1.0, "y": 1.0, "uniform": True, "aspect_ratio_mismatch": False},
            "variants": {
                "baseline": {
                    "status": "succeeded",
                    "overall_conclusion": "<script>alert(1)</script>",
                    "screen_context": "主界面",
                    "issue_count": 0,
                    "cannot_verify_count": 0,
                    "bbox_coverage": {"with_bbox": 0, "total": 0},
                    "paths": {},
                    "error_message": None,
                }
            },
            "diff": {
                "issue_count_by_category": {},
                "new_issues": [],
                "removed_issues": [],
                "changed_severity": [],
                "changed_confidence": [],
                "cannot_verify_count": {},
                "bbox_coverage": {},
                "layout_context": {},
            },
        }
    )

    assert "<script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
```

- [ ] **Step 2: Run HTML test to verify it fails**

Run:

```bash
.venv/bin/python -m pytest tests/test_size_experiment.py::test_render_comparison_html_escapes_model_text -q
```

Expected: FAIL because renderer does not exist.

- [ ] **Step 3: Implement simple HTML renderer**

Add to `app/size_experiment.py`:

```python
def _html_text(value: Any) -> str:
    return escape("" if value is None else str(value))


def render_comparison_html(comparison: dict[str, Any]) -> str:
    variants = comparison.get("variants", {})
    rows = []
    for name, data in variants.items():
        rows.append(
            "<tr>"
            f"<td>{_html_text(name)}</td>"
            f"<td>{_html_text(data.get('status'))}</td>"
            f"<td>{_html_text(data.get('issue_count'))}</td>"
            f"<td>{_html_text(data.get('cannot_verify_count'))}</td>"
            f"<td>{_html_text(data.get('overall_conclusion'))}</td>"
            f"<td>{_html_text(data.get('screen_context'))}</td>"
            f"<td>{_html_text(data.get('error_message'))}</td>"
            "</tr>"
        )
    scale = comparison.get("scale", {})
    warning = ""
    if scale.get("aspect_ratio_mismatch"):
        warning = "<p class=\"warning\">声明尺寸与图片比例不一致，几何结论需要降低置信度。</p>"
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>尺寸实验对照报告</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 32px; color: #202024; }}
    table {{ width: 100%; border-collapse: collapse; table-layout: fixed; }}
    th, td {{ border: 1px solid #dedee6; padding: 8px; vertical-align: top; word-break: break-word; }}
    th {{ background: #f6f6fa; }}
    .warning {{ color: #9f3a00; font-weight: 600; }}
    pre {{ white-space: pre-wrap; background: #f6f6fa; padding: 12px; border: 1px solid #dedee6; }}
  </style>
</head>
<body>
  <h1>尺寸实验对照报告</h1>
  <p>原图：{_html_text(comparison.get("image"))}</p>
  <p>实际尺寸：{_html_text(comparison.get("actual_size"))}</p>
  <p>声明尺寸：{_html_text(comparison.get("declared_size"))}</p>
  <p>缩放：scale_x={_html_text(scale.get("x"))}, scale_y={_html_text(scale.get("y"))}, uniform={_html_text(scale.get("uniform"))}</p>
  {warning}
  <h2>变体对照</h2>
  <table>
    <thead>
      <tr><th>变体</th><th>状态</th><th>问题数</th><th>无法确认</th><th>总体结论</th><th>屏幕理解</th><th>错误</th></tr>
    </thead>
    <tbody>
      {"".join(rows)}
    </tbody>
  </table>
  <h2>差异 JSON</h2>
  <pre>{_html_text(comparison.get("diff"))}</pre>
</body>
</html>
"""
```

- [ ] **Step 4: Run HTML tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_size_experiment.py -q
```

Expected: PASS.

## Task 7: Experiment Orchestration

**Files:**
- Modify: `app/size_experiment.py`
- Test: `tests/test_size_experiment.py`

- [ ] **Step 1: Write failing orchestration test with mocked auditor**

Append to `tests/test_size_experiment.py`:

```python
import json

from app.size_experiment import run_image_experiment


def test_run_image_experiment_writes_isolated_outputs(tmp_path):
    image = tmp_path / "image.png"
    Image.new("RGB", (20, 10), color=(107, 54, 250)).save(image)

    calls = []

    def fake_auditor(**kwargs):
        calls.append(kwargs)
        return {
            "screen_context": kwargs["variant"],
            "overall_conclusion": "ok",
            "issues": [],
            "regions": [],
            "distances": [],
            "cannot_verify": [],
        }

    def fake_measurements(**kwargs):
        kwargs["output_path"].write_text("{}", encoding="utf-8")

    output_dir = tmp_path / "experiment"

    comparison = run_image_experiment(
        image_path=image,
        declared_size=(10, 5),
        output_dir=output_dir,
        auditor=fake_auditor,
        run_measurements_func=fake_measurements,
    )

    assert (output_dir / "baseline" / "audit.json").exists()
    assert (output_dir / "scaled-metrics" / "audit.json").exists()
    assert (output_dir / "normalized-preview" / "audit.json").exists()
    assert (output_dir / "normalized-preview" / "normalized.png").exists()
    assert (output_dir / "comparison.json").exists()
    assert (output_dir / "comparison.html").exists()
    assert comparison["scale"]["uniform"] is True
    assert [call["variant"] for call in calls] == ["baseline", "scaled-metrics", "normalized-preview"]
    assert calls[2]["normalized_preview_path"] == output_dir / "normalized-preview" / "normalized.png"


def test_run_image_experiment_records_variant_failure(tmp_path):
    image = tmp_path / "image.png"
    Image.new("RGB", (20, 10), color=(107, 54, 250)).save(image)

    def fake_auditor(**kwargs):
        if kwargs["variant"] == "scaled-metrics":
            raise RuntimeError("model failed")
        return {
            "screen_context": kwargs["variant"],
            "overall_conclusion": "ok",
            "issues": [],
            "regions": [],
            "distances": [],
            "cannot_verify": [],
        }

    def fake_measurements(**kwargs):
        kwargs["output_path"].write_text("{}", encoding="utf-8")

    comparison = run_image_experiment(
        image_path=image,
        declared_size=(10, 5),
        output_dir=tmp_path / "experiment",
        auditor=fake_auditor,
        run_measurements_func=fake_measurements,
    )

    assert comparison["variants"]["scaled-metrics"]["status"] == "failed"
    assert "model failed" in comparison["variants"]["scaled-metrics"]["error_message"]
    assert comparison["variants"]["baseline"]["status"] == "succeeded"
```

- [ ] **Step 2: Run orchestration tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_size_experiment.py::test_run_image_experiment_writes_isolated_outputs tests/test_size_experiment.py::test_run_image_experiment_records_variant_failure -q
```

Expected: FAIL because `run_image_experiment` is not implemented.

- [ ] **Step 3: Implement `run_image_experiment`**

Add imports in `app/size_experiment.py`:

```python
import json
import shutil
```

Add implementation:

```python
AuditorFunc = Callable[..., dict[str, Any]]
MeasurementsFunc = Callable[..., None]


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _short_error(exc: Exception) -> str:
    return str(exc)[:500] or exc.__class__.__name__


def _run_measurements_wrapper(
    run_measurements_func: MeasurementsFunc,
    image_path: Path,
    regions_path: Path,
    output_path: Path,
    crop_dir: Path,
    design_size: DesignSize | None,
) -> None:
    run_measurements_func(
        image_path=image_path,
        regions_path=regions_path,
        output_path=output_path,
        crop_dir=crop_dir,
        design_size=design_size,
    )


def run_image_experiment(
    image_path: Path,
    declared_size: DesignSize,
    output_dir: Path,
    auditor: AuditorFunc,
    run_measurements_func: MeasurementsFunc,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    original_copy = output_dir / f"original{image_path.suffix.lower() or '.png'}"
    if image_path.resolve() != original_copy.resolve():
        shutil.copyfile(image_path, original_copy)

    with Image.open(image_path) as image:
        actual_size: DesignSize = image.size
    scale = compute_scale(actual_size, declared_size)
    variants: list[VariantResult] = []

    for variant in ["baseline", "scaled-metrics", "normalized-preview"]:
        variant_dir = output_dir / variant
        variant_dir.mkdir(parents=True, exist_ok=True)
        audit_path = variant_dir / "audit.json"
        regions_path = variant_dir / "regions.json"
        measurements_path = variant_dir / "measurements.json"
        crop_dir = variant_dir / "region-crops"
        normalized_path = None
        paths = {
            "audit": str(audit_path.relative_to(output_dir)),
            "regions": str(regions_path.relative_to(output_dir)),
            "measurements": str(measurements_path.relative_to(output_dir)),
        }
        try:
            if variant == "normalized-preview":
                normalized_path = variant_dir / "normalized.png"
                create_normalized_preview(image_path, normalized_path, declared_size)
                paths["normalized"] = str(normalized_path.relative_to(output_dir))

            audit = auditor(
                image_path=image_path,
                declared_size=declared_size,
                scale=scale if variant in {"scaled-metrics", "normalized-preview"} else None,
                normalized_preview_path=normalized_path,
                variant=variant,
            )
            _write_json(audit_path, audit)
            _write_json(regions_path, {"regions": audit.get("regions", []), "distances": audit.get("distances", [])})
            _run_measurements_wrapper(
                run_measurements_func,
                image_path=image_path,
                regions_path=regions_path,
                output_path=measurements_path,
                crop_dir=crop_dir,
                design_size=declared_size if variant == "scaled-metrics" else None,
            )
            variants.append(VariantResult(name=variant, status="succeeded", audit=audit, paths=paths))
        except Exception as exc:  # noqa: BLE001 - per-variant isolation is intentional.
            variants.append(
                VariantResult(
                    name=variant,
                    status="failed",
                    audit={},
                    paths=paths,
                    error_message=_short_error(exc),
                )
            )

    comparison = build_comparison(
        image_path=str(image_path),
        actual_size=actual_size,
        declared_size=declared_size,
        scale=scale,
        variants=variants,
    )
    _write_json(output_dir / "comparison.json", comparison)
    (output_dir / "comparison.html").write_text(render_comparison_html(comparison), encoding="utf-8")
    return comparison
```

- [ ] **Step 4: Run orchestration tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_size_experiment.py -q
```

Expected: PASS.

## Task 8: CLI Wrapper

**Files:**
- Create: `scripts/run_size_experiment.py`
- Test: `tests/test_size_experiment.py`

- [ ] **Step 1: Write failing CLI parser test**

Append to `tests/test_size_experiment.py`:

```python
import importlib.util


def _load_cli_module():
    path = Path("scripts/run_size_experiment.py")
    spec = importlib.util.spec_from_file_location("run_size_experiment", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_cli_requires_task_id_or_image():
    cli = _load_cli_module()

    with pytest.raises(SystemExit):
        cli.parse_args(["--design-size", "1440x900"])


def test_cli_parses_image_and_design_size():
    cli = _load_cli_module()

    args = cli.parse_args(["--image", "screen.png", "--design-size", "1440x900"])

    assert args.image == Path("screen.png")
    assert args.design_size == "1440x900"
```

- [ ] **Step 2: Run CLI tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_size_experiment.py::test_cli_requires_task_id_or_image tests/test_size_experiment.py::test_cli_parses_image_and_design_size -q
```

Expected: FAIL because CLI script does not exist.

- [ ] **Step 3: Create CLI wrapper**

Create `scripts/run_size_experiment.py`:

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import sys
from typing import Any

from openai import OpenAI

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import Settings, load_settings
from app.db import connect
from app.evidence_tools import run_measurements
from app.openai_audit import audit_image, audit_image_with_chat
from app.repositories import get_task_by_id, list_task_images
from app.size_experiment import DesignSizeError, parse_design_size, run_image_experiment
from app.storage import resolve_data_path


SPEC_PATH = ROOT / "references" / "jm-ai-design-spec.md"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run offline manuscript size experiment.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--task-id", type=int)
    source.add_argument("--image", type=Path)
    parser.add_argument("--design-size", required=True, help="Declared design size, e.g. 1440x900")
    parser.add_argument("--output-root", type=Path, default=ROOT / "data" / "experiments")
    return parser.parse_args(argv)


def _build_auditor(settings: Settings):
    spec_text = SPEC_PATH.read_text(encoding="utf-8")
    client = OpenAI(
        api_key=settings.audit_api_key,
        base_url=settings.audit_base_url,
        timeout=settings.audit_timeout_seconds,
        max_retries=0,
    )
    audit = audit_image_with_chat if settings.audit_model_provider == "jdcloud" else audit_image

    def run(
        *,
        image_path: Path,
        declared_size: tuple[int, int],
        scale: dict[str, Any] | None,
        normalized_preview_path: Path | None,
        variant: str,
    ) -> dict[str, Any]:
        return audit(
            client,
            settings.audit_model,
            image_path,
            spec_text,
            reasoning_effort=settings.audit_reasoning_effort,
            declared_screen_size=declared_size,
            scale_context=scale,
            normalized_preview_path=normalized_preview_path,
            experiment_variant=variant,
        )

    return run


def _task_images(settings: Settings, task_id: int) -> list[Path]:
    conn = connect(settings.db_path)
    try:
        task = get_task_by_id(conn, task_id)
        if task is None:
            raise SystemExit(f"task not found: {task_id}")
        return [resolve_data_path(settings, image.original_path) for image in list_task_images(conn, task_id)]
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        declared_size = parse_design_size(args.design_size)
    except DesignSizeError as exc:
        raise SystemExit(str(exc)) from exc

    settings = load_settings()
    images = _task_images(settings, args.task_id) if args.task_id else [args.image]
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    auditor = _build_auditor(settings)

    for index, image_path in enumerate(images, start=1):
        image_key = f"image-{index:03d}"
        output_dir = args.output_root / run_id / image_key
        comparison = run_image_experiment(
            image_path=image_path,
            declared_size=declared_size,
            output_dir=output_dir,
            auditor=auditor,
            run_measurements_func=run_measurements,
        )
        print(f"{image_path} -> {output_dir / 'comparison.html'} ({len(comparison['variants'])} variants)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

The root-path insertion is required so `scripts/run_size_experiment.py --help` works when run directly from the project root without an external `PYTHONPATH`.

- [ ] **Step 4: Make script executable**

Run:

```bash
chmod +x scripts/run_size_experiment.py
```

Expected: command succeeds.

- [ ] **Step 5: Run CLI tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_size_experiment.py -q
```

Expected: PASS.

## Task 9: End-to-End Dry Run Without Model Calls

**Files:**
- Modify only if tests expose a deterministic bug.

- [ ] **Step 1: Run focused test suite**

Run:

```bash
.venv/bin/python -m pytest tests/test_size_experiment.py tests/test_openai_audit.py tests/test_task_runner.py -q
```

Expected: PASS.

- [ ] **Step 2: Run full test suite**

Run:

```bash
.venv/bin/python -m pytest -q
```

Expected: PASS. If this environment hits the known readline issue from the README, run:

```bash
PYTHONPATH=/private/tmp/pytest-no-readline:. .venv/bin/python -m pytest -q
```

Expected: PASS.

- [ ] **Step 3: Verify production flow remains untouched**

Run:

```bash
rg -n "run_size_experiment|size_experiment|normalized_preview|experiment_variant" app/routes app/task_runner.py app/templates
```

Expected: no matches in `app/routes`, `app/task_runner.py`, or templates. Matches in `app/openai_audit.py` are acceptable because default parameters preserve existing behavior.

- [ ] **Step 4: Optional real dry run on one local image**

Only run this when model credentials are configured and cost is acceptable:

```bash
.venv/bin/python scripts/run_size_experiment.py --image data/uploads/123/originals/image-001.png --design-size 1440x900
```

Expected:

- command prints a `comparison.html` path
- files are written under `data/experiments/<run_id>/image-001/`
- no files under `data/uploads/123/` are modified

## Self-Review Checklist

- Spec coverage:
  - Offline sidecar tool: Task 8
  - Three variants: Task 7
  - Baseline current behavior: Task 7
  - Scaled-metrics design-size measurement: Task 3 and Task 7
  - Normalized preview without original mutation: Task 2 and Task 7
  - Comparison JSON and HTML: Task 5 and Task 6
  - Variant failure isolation: Task 5 and Task 7
  - Production isolation: Task 9
- Placeholder scan:
  - No `TBD`, `TODO`, or vague implementation steps.
- Type consistency:
  - `DesignSize` is `tuple[int, int]`.
  - Variant names are `baseline`, `scaled-metrics`, and `normalized-preview`.
  - `run_measurements` accepts `design_size: tuple[int, int] | None = None`.
  - Audit functions accept optional `scale_context`, `normalized_preview_path`, and `experiment_variant`.

## Execution Notes

This directory is currently not a Git repository, so commit steps are intentionally omitted. If this plan is executed inside a Git worktree later, commit after each task with the files listed in that task.
