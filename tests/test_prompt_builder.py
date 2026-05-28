from app.prompt_builder import (
    B_DESIGN_PROMPT_VERSION,
    B_DESIGN_SCHEMA_VERSION,
    PROMPT_VERSION,
    SCHEMA_VERSION,
    build_audit_prompt,
    build_b_design_applicability_prompt,
    build_light_audit_prompt,
    prompt_metadata,
)


def test_prompt_metadata_exposes_prompt_and_schema_versions():
    assert prompt_metadata() == {
        "prompt_version": PROMPT_VERSION,
        "schema_version": SCHEMA_VERSION,
    }


def test_prompt_metadata_uses_b_design_versions_for_b_design():
    assert prompt_metadata("京东 B 端设计规范（B-design Agent 组件规范）") == {
        "prompt_version": B_DESIGN_PROMPT_VERSION,
        "schema_version": B_DESIGN_SCHEMA_VERSION,
    }


def test_bottom_nav_prompt_uses_navigation_focus_without_other_spec_rules():
    prompt = build_audit_prompt(
        "BOTTOM NAV SPEC",
        audit_spec_label="导航类-底部导航栏规范",
    )

    assert "BOTTOM NAV SPEC" in prompt
    assert PROMPT_VERSION in prompt
    assert SCHEMA_VERSION in prompt
    assert "底部导航栏" in prompt
    assert "Tabbar" in prompt
    assert "灵动岛" in prompt
    assert "Joy Agent" in prompt
    assert "不要套用 JM AI 或 B-design" in prompt
    assert "Agent 任务规划" not in prompt
    assert "右上角操作区" not in prompt


def test_build_audit_prompt_includes_versions_and_spec():
    prompt = build_audit_prompt("SPEC TEXT")

    assert PROMPT_VERSION in prompt
    assert SCHEMA_VERSION in prompt
    assert "SPEC TEXT" in prompt
    assert "必须覆盖色彩、字体、间距" in prompt


def test_build_light_audit_prompt_omits_full_spec_but_keeps_versions():
    prompt = build_light_audit_prompt(actual_image_size=(1000, 800))

    assert PROMPT_VERSION in prompt
    assert SCHEMA_VERSION in prompt
    assert "轻量审核" in prompt
    assert "上传图片实际像素尺寸：1000px × 800px" in prompt
    assert "JM AI SPEC" not in prompt


def test_b_design_full_prompt_uses_agent_component_focus_without_jm_ai_rules():
    prompt = build_audit_prompt(
        "B-DESIGN SPEC",
        audit_spec_label="京东 B 端设计规范（B-design Agent 组件规范）",
    )

    assert "B-DESIGN SPEC" in prompt
    assert B_DESIGN_PROMPT_VERSION in prompt
    assert B_DESIGN_SCHEMA_VERSION in prompt
    assert PROMPT_VERSION not in prompt
    assert SCHEMA_VERSION not in prompt
    assert "Agent 任务规划" in prompt
    assert "生成中卡片" in prompt
    assert "不要套用其他设计体系的色彩、按钮、标签" in prompt
    assert "JM AI" not in prompt
    assert "右上角操作区" not in prompt
    assert "邀好友赚套餐" not in prompt


def test_b_design_light_prompt_uses_agent_component_focus():
    prompt = build_light_audit_prompt(
        audit_spec_label="京东 B 端设计规范（B-design Agent 组件规范）",
        actual_image_size=(1000, 800),
    )

    assert "Agent 任务规划" in prompt
    assert "任务节点" in prompt
    assert "生成中卡片" in prompt
    assert B_DESIGN_PROMPT_VERSION in prompt
    assert PROMPT_VERSION not in prompt
    assert "JM AI" not in prompt
    assert "普通蓝、橙、绿、红、黄" not in prompt


def test_b_design_applicability_prompt_uses_b_design_catalog_and_rule_sources():
    prompt = build_b_design_applicability_prompt(
        actual_image_size=(1000, 800),
        audit_spec_label="京东 B 端设计规范（B-design Agent 组件规范）",
    )

    assert "适用性识别" in prompt
    assert "B-design 覆盖目录" in prompt
    assert "data-collection" in prompt
    assert "quality-dashboard" in prompt
    assert "任务规划" in prompt
    assert "pdf_text" in prompt
    assert "pdf_visual_example" in prompt
    assert "alpha_case" in prompt
    assert "不要输出未被这些来源覆盖的通用 B 端界面问题" in prompt
    assert "JM AI" not in prompt
