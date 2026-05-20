from app.b_design_router import (
    has_selected_b_design_components,
    normalize_b_design_applicability,
    select_b_design_spec_context,
)


def test_select_b_design_spec_context_loads_only_matched_component_sections():
    spec_text = """# B-design Agent 组件规范

## 通用审核原则
- 只能依据 B-design PDF 内容。

## 任务规划
任务规划规则。

## 数据收集
数据收集规则。

## 任务节点
任务节点规则。
"""

    context = select_b_design_spec_context(spec_text, ["data-collection"])

    assert context["component_ids"] == ["data-collection"]
    assert context["loaded_sections"] == ["通用审核原则", "数据收集"]
    assert "只能依据 B-design PDF 内容" in context["spec_text"]
    assert "数据收集规则" in context["spec_text"]
    assert "任务规划规则" not in context["spec_text"]
    assert "任务节点规则" not in context["spec_text"]


def test_select_b_design_spec_context_loads_extension_rules_for_alpha_cases():
    spec_text = """# B-design Agent 组件规范

## 通用审核原则
- 只能依据 B-design 规则来源。

## 数据收集
数据收集规则。

## 扩展审核规则
alpha 案例沉淀规则。

## 任务节点
任务节点规则。
"""

    context = select_b_design_spec_context(spec_text, ["quality-dashboard"])

    assert context["component_ids"] == ["quality-dashboard"]
    assert context["loaded_sections"] == ["通用审核原则", "扩展审核规则"]
    assert "只能依据 B-design 规则来源" in context["spec_text"]
    assert "alpha 案例沉淀规则" in context["spec_text"]
    assert "数据收集规则" not in context["spec_text"]
    assert "任务节点规则" not in context["spec_text"]


def test_normalize_b_design_applicability_accepts_weak_component_matches():
    applicability = normalize_b_design_applicability(
        {
            "screen_context": "上传文件页面",
            "matched_components": [
                {
                    "component_id": "数据收集",
                    "confidence": 0.52,
                    "applicability": "weak",
                    "evidence": "截图中出现上传文件区域。",
                }
            ],
        }
    )

    assert has_selected_b_design_components(applicability)
    assert applicability["applicability"] == "weak"
    assert applicability["selected_component_ids"] == ["data-collection"]
    assert applicability["matched_components"][0]["component_name"] == "数据收集"


def test_normalize_b_design_applicability_accepts_alpha_extension_scenarios():
    applicability = normalize_b_design_applicability(
        {
            "screen_context": "质检看板",
            "matched_components": [
                {
                    "component_id": "quality-dashboard",
                    "confidence": 0.74,
                    "applicability": "strong",
                    "evidence": "截图中出现风险列表和诊断卡片。",
                }
            ],
        }
    )

    assert has_selected_b_design_components(applicability)
    assert applicability["applicability"] == "strong"
    assert applicability["selected_component_ids"] == ["quality-dashboard"]
    assert applicability["matched_components"][0]["component_name"] == "质检/诊断/风险看板"
    assert applicability["matched_components"][0]["source_type"] == "alpha_case"
