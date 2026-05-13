import json

from PIL import Image

from app.evidence_tools import (
    EvidenceToolError,
    build_issues_json,
    build_issues_json_for_image,
    run_annotations,
    run_color_analysis,
    run_measurements,
    write_regions_json,
    write_json,
)


def test_build_issues_json_keeps_only_issues_with_bbox():
    issues = [
        {
            "id": "color-01",
            "title": "颜色错误",
            "severity": "中",
            "category": "色彩",
            "bbox": [1, 2, 3, 4],
        },
        {
            "id": "text-01",
            "title": "字体偏小",
            "severity": "低",
            "category": "字体",
            "bbox": None,
        },
    ]

    result = build_issues_json(issues)

    assert result == [
        {
            "id": "color-01",
            "title": "颜色错误",
            "severity": "中",
            "category": "色彩",
            "bbox": [1, 2, 3, 4],
        }
    ]


def test_build_issues_json_skips_untrusted_bbox_statuses():
    issues = [
        {"id": "trusted", "bbox": [1, 2, 3, 4], "bbox_status": "trusted"},
        {"id": "suspicious", "bbox": [1, 2, 3, 4], "bbox_status": "suspicious"},
        {"id": "dropped", "bbox": [1, 2, 3, 4], "bbox_status": "dropped"},
    ]

    result = build_issues_json(issues)

    assert [issue["id"] for issue in result] == ["trusted"]


def test_build_issues_json_for_image_validates_bbox_before_screenshot():
    issues = [
        {"id": "right-top", "location": "右上角按钮", "bbox": [820, 20, 120, 40]},
        {"id": "wrong-side", "location": "右上角按钮", "bbox": [20, 20, 120, 40]},
        {"id": "out-of-bounds", "location": "底部按钮", "bbox": [10, 780, 120, 40]},
    ]

    result = build_issues_json_for_image(issues, image_size=(1000, 800))

    assert [issue["id"] for issue in result] == ["right-top"]


def test_build_issues_json_for_image_keeps_half_size_model_bboxes_unscaled():
    issues = [
        {
            "id": "invite-button",
            "title": "橙色按钮",
            "severity": "高",
            "category": "色彩",
            "bbox": [1190, 14, 145, 38],
        },
        {
            "id": "warning-bar",
            "title": "橙色警告条",
            "severity": "中",
            "category": "色彩",
            "bbox": [241, 72, 470, 40],
        },
    ]

    result = build_issues_json_for_image(issues, image_size=(3184, 1736))

    assert result[0]["bbox"] == [1190.0, 14.0, 145.0, 38.0]
    assert result[1]["bbox"] == [241.0, 72.0, 470.0, 40.0]


def test_build_issues_json_for_image_keeps_logical_canvas_bboxes_unscaled():
    issues = [
        {
            "id": "renew-pill",
            "title": "绿色续费标签",
            "severity": "中",
            "category": "色彩",
            "bbox": [1432, 27, 80, 32],
        },
        {
            "id": "topic-tags",
            "title": "行业专题标签",
            "severity": "低",
            "category": "标签",
            "bbox": [248, 882, 715, 220],
        },
    ]

    result = build_issues_json_for_image(issues, image_size=(3184, 1736))

    assert result[0]["bbox"] == [1432.0, 27.0, 80.0, 32.0]
    assert result[1]["bbox"] == [248.0, 882.0, 715.0, 220.0]


def test_write_regions_json(tmp_path):
    path = tmp_path / "regions.json"
    write_regions_json(
        path,
        [{"id": "a", "bbox": [0, 0, 10, 10]}],
        [{"id": "gap", "from": "a", "to": "a", "axis": "x"}],
    )

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["regions"][0]["id"] == "a"
    assert data["distances"][0]["id"] == "gap"


def test_run_color_analysis_creates_tokens_json(tmp_path):
    image = tmp_path / "input.png"
    Image.new("RGB", (20, 20), color=(107, 54, 250)).save(image)
    output = tmp_path / "tokens.json"

    run_color_analysis(image, output, [{"label": "center", "x": 10, "y": 10}])

    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["image_size_px"]["width"] == 20
    assert data["samples"][0]["label"] == "center"


def test_run_color_analysis_sanitizes_sample_labels(tmp_path):
    image = tmp_path / "input.png"
    Image.new("RGB", (20, 20), color=(107, 54, 250)).save(image)
    output = tmp_path / "nested" / "tokens.json"

    run_color_analysis(image, output, [{"label": "cta:primary", "x": 10, "y": 10}])

    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["samples"][0]["label"] == "cta-primary"


def test_run_color_analysis_reports_script_failure(tmp_path):
    try:
        run_color_analysis(tmp_path / "missing.png", tmp_path / "tokens.json", [])
    except EvidenceToolError as exc:
        assert str(exc)
    else:
        raise AssertionError("missing image should fail")


def test_run_measurements_creates_json_and_crops(tmp_path):
    image = tmp_path / "input.png"
    Image.new("RGB", (20, 20), color=(107, 54, 250)).save(image)
    regions = tmp_path / "regions.json"
    output = tmp_path / "measurements.json"
    crop_dir = tmp_path / "crops"
    write_regions_json(
        regions,
        [{"id": "button", "bbox": [2, 2, 10, 8], "measure_kind": "component"}],
        [],
    )

    run_measurements(image, regions, output, crop_dir)

    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["regions"][0]["id"] == "button"
    assert (crop_dir / "region-button.png").exists()


def test_run_annotations_creates_annotated_image_and_crop(tmp_path):
    image = tmp_path / "input.png"
    Image.new("RGB", (20, 20), color=(107, 54, 250)).save(image)
    issues = tmp_path / "issues.json"
    output_dir = tmp_path / "annotations"
    write_json(
        issues,
        [
            {
                "id": "color-01",
                "title": "颜色错误",
                "severity": "中",
                "category": "色彩",
                "bbox": [2, 2, 10, 8],
            }
        ],
    )

    run_annotations(image, issues, output_dir)

    assert (output_dir / "annotated.png").exists()
    assert (output_dir / "issue-color-01.png").exists()


def test_run_annotations_draws_high_visibility_border(tmp_path):
    image = tmp_path / "input.png"
    Image.new("RGB", (80, 80), color=(107, 54, 250)).save(image)
    issues = tmp_path / "issues.json"
    output_dir = tmp_path / "annotations"
    write_json(
        issues,
        [
            {
                "id": "color-01",
                "title": "颜色错误",
                "severity": "中",
                "category": "色彩",
                "bbox": [20, 20, 30, 30],
            }
        ],
    )

    run_annotations(image, issues, output_dir)

    annotated = Image.open(output_dir / "annotated.png").convert("RGB")
    assert annotated.getpixel((35, 25)) == (181, 71, 8)
