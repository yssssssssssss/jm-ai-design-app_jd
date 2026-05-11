from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from PIL import Image

from app import evidence_tools
from app.size_experiment import (
    create_normalized_preview,
    DesignSizeError,
    VariantResult,
    build_comparison,
    compute_scale,
    issue_key,
    normalized_preview_size,
    parse_design_size,
    render_comparison_html,
    run_image_experiment,
    summarize_variant,
)


def test_parse_design_size_accepts_width_x_height():
    assert parse_design_size("1440x900") == (1440, 900)
    assert parse_design_size("1440X900") == (1440, 900)
    assert parse_design_size(" 1440 x 900 ") == (1440, 900)


@pytest.mark.parametrize(
    "value",
    ["", "1440", "1440x", "x900", "0x900", "1440x0", "-1x900", "1440.5x900"],
)
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
    assert normalized_preview_size(actual_size=(2880, 1800), declared_size=(1440, 900)) == (
        1440,
        900,
    )
    assert normalized_preview_size(actual_size=(2880, 2000), declared_size=(1440, 900)) == (
        1440,
        1000,
    )


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
            VariantResult(
                name="baseline",
                status="failed",
                audit={},
                paths={},
                error_message="model failed",
            ),
            VariantResult(
                name="scaled_metrics",
                status="succeeded",
                audit={"issues": []},
                paths={"audit": "scaled/audit.json"},
            ),
        ],
    )

    assert comparison["variants"]["baseline"]["status"] == "failed"
    assert comparison["variants"]["baseline"]["error_message"] == "model failed"
    assert comparison["variants"]["scaled_metrics"]["status"] == "succeeded"
    assert "diff" in comparison


def test_render_comparison_html_escapes_model_text():
    html = render_comparison_html(
        {
            "image": "image.png",
            "actual_size": [100, 50],
            "declared_size": [100, 50],
            "scale": {
                "x": 1.0,
                "y": 1.0,
                "uniform": True,
                "aspect_ratio_mismatch": False,
            },
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
    assert [call["variant"] for call in calls] == [
        "baseline",
        "scaled-metrics",
        "normalized-preview",
    ]
    assert calls[2]["normalized_preview_path"] == output_dir / "normalized-preview" / "normalized.png"
    assert json.loads((output_dir / "comparison.json").read_text(encoding="utf-8"))["scale"][
        "uniform"
    ]


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


def test_cli_help_runs_as_script():
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    result = subprocess.run(
        [sys.executable, "scripts/run_size_experiment.py", "--help"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )

    assert result.returncode == 0
    assert "--design-size" in result.stdout
