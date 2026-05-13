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


def test_normalize_subcategory_preserves_canonical_ids():
    assert normalize_subcategory("off_token_color", "color_gradient") == "off_token_color"
    assert (
        normalize_subcategory("wrong_gradient_direction", "color_gradient")
        == "wrong_gradient_direction"
    )
    assert (
        normalize_subcategory("non_ai_primary_action", "color_gradient")
        == "non_ai_primary_action"
    )
    assert normalize_subcategory("low_contrast", "color_gradient") == "low_contrast"


def test_normalize_subcategory_does_not_expand_short_partial_aliases():
    assert normalize_subcategory("off", "color_gradient") == "off"
    assert normalize_subcategory("ai", "color_gradient") == "ai"
    assert normalize_subcategory("low", "color_gradient") == "low"
    assert normalize_subcategory("button", "component_spec") == "button"


def test_normalize_category_prioritizes_color_in_mixed_labels():
    assert normalize_category("颜色和品牌") == "color_gradient"
    assert normalize_category("Brand/logo/accent color inventory") == "color_gradient"


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
