from app.rule_engine import apply_rule_review


def _audit(**overrides):
    payload = {
        "screen_context": "测试页",
        "overall_conclusion": "模型未发现问题",
        "major_issues": [],
        "passes": [],
        "issues": [],
        "sample_points": [],
        "regions": [],
        "distances": [],
        "checklist": [],
        "cannot_verify": [],
    }
    payload.update(overrides)
    return payload


def test_rule_review_adds_color_issue_from_off_token_sample():
    audit = _audit(sample_points=[{"label": "邀好友赚套餐按钮", "x": 20, "y": 20}])
    tokens = {
        "samples": [
            {
                "label": "邀好友赚套餐按钮",
                "x": 20,
                "y": 20,
                "hex": "#F37021",
                "family": "red/orange",
                "nearest_jm_token": {
                    "name": "ai/ai-normal",
                    "hex": "#6B36FA",
                    "distance": 190.0,
                    "is_close": False,
                },
                "off_token_candidate": True,
            }
        ]
    }

    result = apply_rule_review(audit, tokens=tokens, measurements={}, image_size=(100, 100))

    assert len(result["issues"]) == 1
    assert result["issues"][0]["category"] == "色彩"
    assert result["issues"][0]["location"] == "邀好友赚套餐按钮"
    assert result["issues"][0]["bbox"] == [8, 8, 24, 24]
    assert result["issues"][0]["rule_source"] == "color_sample"
    assert result["checklist"][0]["status"] == "不通过"


def test_rule_review_enriches_existing_color_issue_instead_of_duplicating():
    audit = _audit(
        issues=[
            {
                "id": "model-001",
                "category": "色彩",
                "severity": "中",
                "location": "邀好友赚套餐按钮",
                "current_observation": "按钮颜色不符合 JM AI 色彩规范。",
                "spec_expectation": "应使用 JM AI 色彩 token。",
                "recommendation": "替换为规范色。",
                "confidence": 0.7,
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

    assert len(result["issues"]) == 1
    assert result["issues"][0]["id"] == "问题-001"
    assert result["issues"][0]["bbox"] == [10, 10, 40, 20]
    assert result["issues"][0]["rule_source"] == "color_sample"
    assert "实测颜色 #F37021" in result["issues"][0]["current_observation"]


def test_rule_review_adds_spacing_issue_from_failed_distance_measurement():
    measurements = {
        "distances": [
            {
                "id": "header-gap",
                "from": "logo",
                "to": "actions",
                "axis": "x",
                "gap_design_px": 18.4,
                "nearest_spacing": {
                    "token": 16,
                    "delta": 2.4,
                    "passes_with_1px_tolerance": False,
                },
            }
        ]
    }

    result = apply_rule_review(_audit(), tokens={}, measurements=measurements, image_size=(100, 100))

    assert len(result["issues"]) == 1
    assert result["issues"][0]["category"] == "间距"
    assert result["issues"][0]["location"] == "header-gap"
    assert result["issues"][0]["rule_source"] == "spacing_measurement"
    assert "18.4px" in result["issues"][0]["current_observation"]


def test_rule_review_drops_untrusted_bbox_but_keeps_text_issue():
    audit = _audit(
        issues=[
            {
                "id": "model-001",
                "category": "布局",
                "severity": "中",
                "location": "右下角输入框区域",
                "current_observation": "输入框位置异常。",
                "spec_expectation": "输入框应在规范位置。",
                "recommendation": "调整输入框。",
                "confidence": 0.6,
                "bbox": [5, 5, 20, 20],
            }
        ]
    )

    result = apply_rule_review(audit, tokens={}, measurements={}, image_size=(100, 100))

    assert result["issues"][0]["bbox"] is None
    assert result["issues"][0]["bbox_rule_status"] == "dropped_untrusted"
