from __future__ import annotations

import re
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
        "offtoken": "off_token_color",
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

CANONICAL_SUBCATEGORIES = {
    subcategory
    for aliases in SUBCATEGORY_ALIASES.values()
    for subcategory in aliases.values()
}

CATEGORY_KEYWORDS = (
    ("color_gradient", {"color", "colour", "gradient"}, ("颜色", "色彩", "渐变")),
    ("brand_identity", {"brand"}, ("品牌",)),
    ("typography", {"typography", "font"}, ("字体", "字号", "文本")),
    ("spacing_layout", {"spacing", "layout", "padding", "gap"}, ("间距", "布局")),
    ("component_spec", {"component", "button", "tag"}, ("按钮", "标签", "组件")),
    ("icon_ai_mark", {"icon", "sparkle"}, ("图标", "闪光")),
    ("header_navigation", {"header"}, ("头部", "导航")),
    ("interaction_state", {"state"}, ("状态", "交互")),
    ("accessibility", {"accessibility", "a11y"}, ("可访问性",)),
    ("content_hierarchy", {"content"}, ("文案", "信息层级")),
)


def _normalized(value: Any) -> str:
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


def _english_tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", value.lower()))


def normalize_category(value: Any) -> str:
    raw = str(value or "").strip()
    if raw in CATEGORY_LABELS:
        return raw
    key = _normalized(raw)
    if not key:
        return "content_hierarchy"
    if key in CATEGORY_ALIASES:
        return CATEGORY_ALIASES[key]
    tokens = _english_tokens(raw)
    for category, english_terms, cjk_terms in CATEGORY_KEYWORDS:
        if tokens & english_terms or any(term in raw for term in cjk_terms):
            return category
    return "content_hierarchy"


def normalize_subcategory(value: Any, category: Any) -> str:
    category_key = normalize_category(category)
    raw = str(value or "").strip()
    if not raw:
        return "general"
    raw_key = raw.lower()
    if raw_key in CANONICAL_SUBCATEGORIES:
        return raw_key
    key = _normalized(raw)
    aliases = SUBCATEGORY_ALIASES.get(category_key, {})
    if raw_key in aliases:
        return aliases[raw_key]
    if key in aliases:
        return aliases[key]
    for alias, subcategory in aliases.items():
        if alias in key or key in alias:
            return subcategory
    return key or "general"
