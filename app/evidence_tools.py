from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from app.bbox_validator import DROPPED, SUSPICIOUS, validate_bbox


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"


class EvidenceToolError(Exception):
    pass


def _sample_label(value: Any) -> str:
    label = re.sub(r"[^0-9A-Za-z_-]+", "-", str(value)).strip("-")
    return label or "sample"


def _run(args: list[str]) -> None:
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "evidence tool failed"
        raise EvidenceToolError(message)


def _valid_bbox(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 4
        and all(isinstance(item, (int, float)) for item in value)
        and value[2] > 0
        and value[3] > 0
    )


def build_issues_json(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return _build_issues_json(issues, scale_x=1.0)


def build_issues_json_for_image(
    issues: list[dict[str, Any]],
    image_size: tuple[int, int],
) -> list[dict[str, Any]]:
    return _build_issues_json(issues, scale_x=1.0, scale_y=1.0, image_size=image_size)


def _build_issues_json(
    issues: list[dict[str, Any]],
    scale_x: float,
    scale_y: float | None = None,
    image_size: tuple[int, int] | None = None,
) -> list[dict[str, Any]]:
    scale_y = scale_x if scale_y is None else scale_y
    output: list[dict[str, Any]] = []
    for issue in issues:
        if issue.get("bbox_status") in {SUSPICIOUS, DROPPED}:
            continue
        if image_size is not None:
            issue = validate_bbox(issue, image_size)
            if issue.get("bbox_status") != "trusted":
                continue
        bbox = issue.get("bbox")
        if not _valid_bbox(bbox):
            continue
        output.append(
            {
                "id": str(issue.get("id") or "issue"),
                "title": str(
                    issue.get("title")
                    or issue.get("current_observation")
                    or issue.get("id")
                    or "问题"
                ),
                "severity": str(issue.get("severity") or "中"),
                "category": str(issue.get("category") or "其他"),
                "bbox": [
                    float(bbox[0]) * scale_x,
                    float(bbox[1]) * scale_y,
                    float(bbox[2]) * scale_x,
                    float(bbox[3]) * scale_y,
                ],
            }
        )
    return output


def _bbox_scale_for_image(
    bboxes: list[Any],
    image_size: tuple[int, int],
) -> tuple[float, float]:
    valid_bboxes = [bbox for bbox in bboxes if _valid_bbox(bbox)]
    if not valid_bboxes:
        return 1.0, 1.0

    width, height = image_size
    if width < 2000 or height < 1000:
        return 1.0, 1.0

    max_right = max(float(bbox[0]) + float(bbox[2]) for bbox in valid_bboxes)
    max_bottom = max(float(bbox[1]) + float(bbox[3]) for bbox in valid_bboxes)
    scale_x = _half_canvas_scale(max_right, width)
    scale_y = _half_canvas_scale(max_bottom, height)
    if scale_x == 2.0 and scale_y == 1.0 and max_bottom <= height / 2 * 1.05:
        scale_y = 2.0
    if scale_y == 2.0 and scale_x == 1.0 and max_right <= width / 2 * 1.05:
        scale_x = 2.0
    if scale_x == 1.0:
        scale_x = _axis_bbox_scale(max_right, width)
    if scale_y == 1.0:
        scale_y = _axis_bbox_scale(max_bottom, height)
    return scale_x, scale_y


def _half_canvas_scale(max_extent: float, image_extent: int) -> float:
    half_extent = image_extent / 2
    if max_extent <= half_extent * 1.05 and max_extent >= image_extent * 0.35:
        return 2.0
    return 1.0


def _axis_bbox_scale(max_extent: float, image_extent: int) -> float:
    if max_extent <= 0:
        return 1.0
    coverage = max_extent / image_extent
    if coverage < 0.25 or coverage > 0.72:
        return 1.0
    scale = image_extent / max_extent
    if 1.35 <= scale <= 2.35:
        return round(scale, 1)
    return 1.0


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_regions_json(
    path: Path,
    regions: list[dict[str, Any]],
    distances: list[dict[str, Any]],
) -> None:
    write_json(path, {"regions": regions, "distances": distances})


def run_color_analysis(
    image_path: Path,
    output_path: Path,
    sample_points: list[dict[str, Any]],
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    args = [
        sys.executable,
        str(SCRIPTS_DIR / "analyze_image_tokens.py"),
        str(image_path),
        "--output",
        str(output_path),
    ]
    for point in sample_points:
        args.extend(["--sample", f"{_sample_label(point['label'])}:{point['x']}:{point['y']}"])
    _run(args)


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


def run_annotations(image_path: Path, issues_path: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    _run(
        [
            sys.executable,
            str(SCRIPTS_DIR / "annotate_issues.py"),
            str(image_path),
            str(issues_path),
            str(output_dir),
        ]
    )
