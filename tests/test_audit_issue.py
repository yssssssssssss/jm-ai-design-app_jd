from app.audit_issue import issue_key, normalize_issue, normalize_issues


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


def test_issue_key_handles_none():
    assert issue_key(None) == "content_hierarchy.general:unknown:issue"


def test_issue_key_handles_empty_dict():
    assert issue_key({}) == "content_hierarchy.general:unknown:issue"
