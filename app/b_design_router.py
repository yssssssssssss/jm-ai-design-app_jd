from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BDesignComponent:
    id: str
    heading: str
    aliases: tuple[str, ...]
    description: str
    source_type: str = "pdf_text"
    section_heading: str | None = None


B_DESIGN_COMPONENTS = [
    BDesignComponent(
        id="task-planning",
        heading="任务规划",
        aliases=("任务规划", "任务计划", "执行计划", "大纲"),
        description="智能体将复杂任务分解为可执行步骤，展示执行计划、步骤大纲和展开收起状态。",
    ),
    BDesignComponent(
        id="task-node",
        heading="任务节点",
        aliases=("任务节点", "一级节点", "二级节点", "生成链", "节点状态"),
        description="呈现智能体执行任务时的节点、状态和流程，包含进行中、已完成、失败等节点状态。",
    ),
    BDesignComponent(
        id="data-collection",
        heading="数据收集",
        aliases=("数据收集", "上传文件", "文件上传", "资料收集", "收集组件"),
        description="用于收集用户输入、文件或数据资料，包含收集进度、停止、完成和简易版收集形态。",
    ),
    BDesignComponent(
        id="deep-thinking",
        heading="深度思考",
        aliases=("深度思考", "思考过程", "推理过程"),
        description="展示智能体深度思考过程、完成状态、交互和窄屏适配。",
    ),
    BDesignComponent(
        id="status-bar",
        heading="状态栏",
        aliases=("状态栏", "状态提示", "任务状态", "开启新任务"),
        description="展示任务状态信息或开启新任务操作，覆盖纯信息展示和操作型状态栏。",
    ),
    BDesignComponent(
        id="generating-card-code",
        heading="生成中卡片-代码",
        aliases=("生成中卡片-代码", "代码卡片", "生成代码"),
        description="生成中卡片的代码类型，包含组件构成和待确认状态。",
    ),
    BDesignComponent(
        id="generating-card-product",
        heading="生成中卡片-商品卡",
        aliases=("生成中卡片-商品卡", "商品卡", "商品生成"),
        description="生成中卡片的商品卡类型，包含已确认和收起状态。",
    ),
    BDesignComponent(
        id="generating-card-image",
        heading="生成中卡片-图片",
        aliases=("生成中卡片-图片", "图片卡片", "图片生成"),
        description="生成中卡片的图片类型，包含组件状态和收起状态。",
    ),
    BDesignComponent(
        id="generating-card-file",
        heading="生成中卡片-文件",
        aliases=("生成中卡片-文件", "文件卡片", "文件生成"),
        description="生成中卡片的文件类型，包含文件生成内容和状态。",
    ),
    BDesignComponent(
        id="generating-card-form",
        heading="生成中卡片-表单",
        aliases=("生成中卡片-表单", "表单卡片", "表单生成"),
        description="生成中卡片的表单类型，包含表单生成、确认和收起状态。",
    ),
    BDesignComponent(
        id="generating-card-table",
        heading="生成中卡片-表格",
        aliases=("生成中卡片-表格", "表格卡片", "表格生成"),
        description="生成中卡片的表格类型，包含表格生成、确认和收起状态。",
    ),
    BDesignComponent(
        id="b-design-visual-patterns",
        heading="PDF 示意图归纳规则",
        aliases=("示意图规则", "视觉示例", "视觉参考", "PDF示意图", "规范示意图"),
        description="从 B-design PDF 示意图归纳出的视觉参考规则，用于补足无明文描述的组件状态。",
        source_type="pdf_visual_example",
        section_heading="扩展审核规则",
    ),
    BDesignComponent(
        id="title-optimization-flow",
        heading="标题优化/违规检测流程",
        aliases=("标题优化", "商品标题", "违规检测", "黑词", "标题生成", "标题预览"),
        description="alpha 案例沉淀的标题优化、黑词/违规检测、预览确认等流程场景。",
        source_type="alpha_case",
        section_heading="扩展审核规则",
    ),
    BDesignComponent(
        id="quality-dashboard",
        heading="质检/诊断/风险看板",
        aliases=("实时质检", "质检看板", "风险列表", "全店诊断", "智能诊断", "告警"),
        description="alpha 案例沉淀的质检、诊断、风险列表和告警类页面场景。",
        source_type="alpha_case",
        section_heading="扩展审核规则",
    ),
    BDesignComponent(
        id="legacy-printing-page",
        heading="打单/订单配置页",
        aliases=("打单", "快递单", "订单列表", "打印配置", "批量发货", "配置页"),
        description="alpha 案例沉淀的传统订单、打单、配置页等非 Agent 页面场景。",
        source_type="alpha_case",
        section_heading="扩展审核规则",
    ),
    BDesignComponent(
        id="form-confirmation-flow",
        heading="表单确认/预览提交流程",
        aliases=("表单确认", "预览确认", "保存取消", "下一步", "底部按钮", "提交确认"),
        description="alpha 案例沉淀的表单、预览、保存、取消、下一步等底部操作区场景。",
        source_type="alpha_case",
        section_heading="扩展审核规则",
    ),
    BDesignComponent(
        id="alpha-visual-rules",
        heading="alpha 案例视觉规则命中",
        aliases=("按钮顺序", "灰卡", "白卡", "容器嵌套", "紫色", "蓝色", "绿色", "emoji", "下拉箭头", "图标大小"),
        description="当截图出现 alpha 案例覆盖的按钮顺序、容器嵌套、颜色语义、图标、emoji 或下拉箭头模式时适用。",
        source_type="alpha_case",
        section_heading="扩展审核规则",
    ),
]

_COMPONENTS_BY_ID = {component.id: component for component in B_DESIGN_COMPONENTS}
_COMPONENT_IDS_BY_HEADING = {component.heading: component.id for component in B_DESIGN_COMPONENTS}


def is_b_design_label(label: str) -> bool:
    normalized = (label or "").lower()
    return "b-design" in normalized or "agent 组件" in normalized


def b_design_component_catalog_text() -> str:
    lines = []
    for component in B_DESIGN_COMPONENTS:
        aliases = "、".join(component.aliases)
        lines.append(
            f"- {component.id}｜{component.heading}｜来源：{component.source_type}｜"
            f"别名：{aliases}｜{component.description}"
        )
    return "\n".join(lines)


def normalize_b_design_component_id(value: Any) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    normalized = raw.lower().replace("_", "-").replace(" ", "-")
    if normalized in _COMPONENTS_BY_ID:
        return normalized
    for component in B_DESIGN_COMPONENTS:
        if raw == component.heading or raw in component.aliases:
            return component.id
        if normalized == component.heading.lower():
            return component.id
    return None


def parse_b_design_sections(spec_text: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    current_heading: str | None = None
    current_lines: list[str] = []
    for line in spec_text.splitlines():
        if line.startswith("## "):
            if current_heading is not None:
                sections[current_heading] = "\n".join(current_lines).strip()
            current_heading = line[3:].strip()
            current_lines = [line]
            continue
        if current_heading is not None:
            current_lines.append(line)
    if current_heading is not None:
        sections[current_heading] = "\n".join(current_lines).strip()
    return sections


def select_b_design_spec_context(
    spec_text: str,
    component_ids: list[str],
) -> dict[str, Any]:
    sections = parse_b_design_sections(spec_text)
    selected_ids: list[str] = []
    selected_sections: list[str] = []
    output_parts = ["# B-design Agent 组件规范"]

    general = sections.get("通用审核原则")
    if general:
        output_parts.append(general)
        selected_sections.append("通用审核原则")

    for raw_component_id in component_ids:
        component_id = normalize_b_design_component_id(raw_component_id)
        if component_id is None or component_id in selected_ids:
            continue
        component = _COMPONENTS_BY_ID[component_id]
        heading = component.section_heading or component.heading
        section = sections.get(heading)
        if not section:
            continue
        selected_ids.append(component_id)
        if heading not in selected_sections:
            selected_sections.append(heading)
            output_parts.append(section)

    return {
        "spec_text": "\n\n".join(part for part in output_parts if part).strip(),
        "component_ids": selected_ids,
        "loaded_sections": selected_sections,
    }


def normalize_b_design_applicability(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        data = {}
    matches = _component_matches(data)
    selected_ids: list[str] = []
    for match in matches:
        if match["applicability"] in {"strong", "weak"} or match["confidence"] >= 0.35:
            if match["component_id"] not in selected_ids:
                selected_ids.append(match["component_id"])

    explicit = str(data.get("applicability") or "").strip().lower()
    if explicit not in {"strong", "weak", "none"}:
        explicit = ""
    if explicit:
        applicability = explicit
    elif any(match["applicability"] == "strong" for match in matches):
        applicability = "strong"
    elif selected_ids:
        applicability = "weak"
    else:
        applicability = "none"

    return {
        "screen_context": str(data.get("screen_context") or "").strip(),
        "applicability": applicability,
        "matched_components": matches,
        "selected_component_ids": selected_ids,
        "reason": str(data.get("reason") or data.get("evidence") or "").strip(),
        "cannot_verify": _text_list(data.get("cannot_verify")),
    }


def has_selected_b_design_components(applicability: dict[str, Any]) -> bool:
    return bool(applicability.get("selected_component_ids"))


def component_names(component_ids: list[str]) -> list[str]:
    names: list[str] = []
    for component_id in component_ids:
        component = _COMPONENTS_BY_ID.get(component_id)
        if component is not None:
            names.append(component.heading)
    return names


def _component_matches(data: dict[str, Any]) -> list[dict[str, Any]]:
    raw_matches = (
        data.get("matched_components")
        or data.get("component_matches")
        or data.get("components")
        or []
    )
    if not isinstance(raw_matches, list):
        raw_matches = [raw_matches]
    matches: list[dict[str, Any]] = []
    for raw_match in raw_matches:
        match = _component_match(raw_match)
        if match is None:
            continue
        if any(existing["component_id"] == match["component_id"] for existing in matches):
            continue
        matches.append(match)
    return matches


def _component_match(raw_match: Any) -> dict[str, Any] | None:
    if isinstance(raw_match, str):
        component_id = normalize_b_design_component_id(raw_match)
        confidence = 0.5
        evidence = ""
        applicability = "weak"
    elif isinstance(raw_match, dict):
        component_id = normalize_b_design_component_id(
            raw_match.get("component_id")
            or raw_match.get("id")
            or raw_match.get("component")
            or raw_match.get("name")
            or raw_match.get("component_name")
        )
        confidence = _confidence(raw_match.get("confidence"))
        evidence = str(raw_match.get("evidence") or raw_match.get("reason") or "").strip()
        applicability = str(raw_match.get("applicability") or "").strip().lower()
        if applicability not in {"strong", "weak", "none"}:
            applicability = "strong" if confidence >= 0.7 else "weak"
    else:
        return None
    if component_id is None:
        return None
    component = _COMPONENTS_BY_ID[component_id]
    return {
        "component_id": component_id,
        "component_name": component.heading,
        "source_type": component.source_type,
        "confidence": confidence,
        "applicability": applicability,
        "evidence": evidence,
    }


def _confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.5
    return max(0.0, min(1.0, confidence))


def _text_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []
