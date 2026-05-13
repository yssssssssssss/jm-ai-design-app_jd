from app.bbox_validator import DROPPED, SUSPICIOUS, TRUSTED, validate_bbox


def test_validate_bbox_trusts_in_bounds_matching_right_top_position():
    issue = {
        "location": "右上角按钮",
        "bbox": [820, 20, 120, 40],
    }

    result = validate_bbox(issue, image_size=(1000, 800))

    assert result["bbox_status"] == TRUSTED
    assert result["bbox_confidence"] >= 0.8
    assert result["bbox"] == [820.0, 20.0, 120.0, 40.0]


def test_validate_bbox_drops_out_of_bounds_bbox():
    issue = {
        "location": "右上角按钮",
        "bbox": [950, 20, 120, 40],
    }

    result = validate_bbox(issue, image_size=(1000, 800))

    assert result["bbox_status"] == DROPPED
    assert result["bbox_confidence"] == 0.0
    assert result["bbox"] is None
    assert "越界" in result["bbox_reason"]


def test_validate_bbox_marks_position_conflict_suspicious():
    issue = {
        "location": "右上角按钮",
        "bbox": [20, 20, 120, 40],
    }

    result = validate_bbox(issue, image_size=(1000, 800))

    assert result["bbox_status"] == SUSPICIOUS
    assert result["bbox_confidence"] < 0.8
    assert result["bbox"] == [20.0, 20.0, 120.0, 40.0]


def test_validate_bbox_drops_invalid_bbox():
    result = validate_bbox({"bbox": [1, 2, 0, 4]}, image_size=(1000, 800))

    assert result["bbox_status"] == DROPPED
    assert result["bbox_confidence"] == 0.0
    assert result["bbox"] is None
    assert "无效" in result["bbox_reason"]


def test_validate_bbox_drops_non_finite_bbox():
    result = validate_bbox({"bbox": [float("nan"), 2, 10, 4]}, image_size=(1000, 800))

    assert result["bbox_status"] == DROPPED
    assert result["bbox"] is None
    assert "无效" in result["bbox_reason"]


def test_validate_bbox_ignores_direction_words_in_observation_text():
    issue = {
        "location": "左侧列表项",
        "current_observation": "右侧图标颜色不符合规范",
        "bbox": [20, 20, 120, 40],
    }

    result = validate_bbox(issue, image_size=(1000, 800))

    assert result["bbox_status"] == TRUSTED
