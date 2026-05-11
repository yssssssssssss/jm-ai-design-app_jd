from __future__ import annotations

from dataclasses import dataclass
from html import escape
import json
from pathlib import Path
import shutil
from typing import Any, Callable

from PIL import Image

from app.size_context import DesignSize, compute_scale


class DesignSizeError(ValueError):
    pass


AuditorFunc = Callable[..., dict[str, Any]]
MeasurementsFunc = Callable[..., None]


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


def normalized_preview_size(actual_size: DesignSize, declared_size: DesignSize) -> DesignSize:
    actual_width, actual_height = actual_size
    declared_width, _ = declared_size
    normalized_height = round(actual_height * declared_width / actual_width)
    return declared_width, normalized_height


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
    return {
        "status": result.status,
        "error_message": result.error_message,
        "paths": result.paths,
        "overall_conclusion": result.audit.get("overall_conclusion"),
        "screen_context": result.audit.get("screen_context"),
        "issue_count": len(issues),
        "cannot_verify_count": len(cannot_verify),
        "bbox_coverage": _bbox_coverage(issues),
    }


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
    issue_maps = {
        result.name: _issue_map(result)
        for result in variants
        if result.status == "succeeded"
    }
    baseline = issue_maps.get("baseline", {})
    diff: dict[str, Any] = {
        "issue_count_by_category": {},
        "new_issues": [],
        "removed_issues": [],
        "changed_severity": [],
        "changed_confidence": [],
        "cannot_verify_count": {
            name: summary["cannot_verify_count"]
            for name, summary in variant_summaries.items()
        },
        "bbox_coverage": {
            name: summary["bbox_coverage"] for name, summary in variant_summaries.items()
        },
        "layout_context": {
            name: summary.get("screen_context")
            for name, summary in variant_summaries.items()
        },
    }
    for name, issues in issue_maps.items():
        counts: dict[str, int] = {}
        for issue in issues.values():
            category = str(issue.get("category") or "未分类")
            counts[category] = counts.get(category, 0) + 1
        diff["issue_count_by_category"][name] = counts
        if name == "baseline":
            continue
        diff["new_issues"].extend(
            {"variant": name, "key": key}
            for key in sorted(set(issues) - set(baseline))
        )
        diff["removed_issues"].extend(
            {"variant": name, "key": key}
            for key in sorted(set(baseline) - set(issues))
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
        warning = '<p class="warning">声明尺寸与图片比例不一致，几何结论需要降低置信度。</p>'
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


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


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
            _write_json(
                regions_path,
                {
                    "regions": audit.get("regions", []),
                    "distances": audit.get("distances", []),
                },
            )
            _run_measurements_wrapper(
                run_measurements_func,
                image_path=image_path,
                regions_path=regions_path,
                output_path=measurements_path,
                crop_dir=crop_dir,
                design_size=declared_size if variant == "scaled-metrics" else None,
            )
            variants.append(
                VariantResult(name=variant, status="succeeded", audit=audit, paths=paths)
            )
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
    (output_dir / "comparison.html").write_text(
        render_comparison_html(comparison),
        encoding="utf-8",
    )
    return comparison
