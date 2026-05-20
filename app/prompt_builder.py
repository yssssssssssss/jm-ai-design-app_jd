from __future__ import annotations

from typing import Any

from app.b_design_router import b_design_component_catalog_text


PROMPT_VERSION = "jm-audit-prompt-v1"
SCHEMA_VERSION = "jm-audit-schema-v1"
B_DESIGN_PROMPT_VERSION = "b-design-audit-prompt-v1"
B_DESIGN_SCHEMA_VERSION = "b-design-audit-schema-v1"


def prompt_metadata(audit_spec_label: str = "JM AI 设计规范") -> dict[str, str]:
    if _is_b_design_label(audit_spec_label):
        return {
            "prompt_version": B_DESIGN_PROMPT_VERSION,
            "schema_version": B_DESIGN_SCHEMA_VERSION,
        }
    return {
        "prompt_version": PROMPT_VERSION,
        "schema_version": SCHEMA_VERSION,
    }


def build_audit_prompt(
    spec_text: str,
    audit_spec_label: str = "JM AI 设计规范",
    declared_screen_size: tuple[int, int] | None = None,
    actual_image_size: tuple[int, int] | None = None,
    scale_context: dict[str, Any] | None = None,
    normalized_preview_size: tuple[int, int] | None = None,
    experiment_variant: str | None = None,
) -> str:
    size_context = _size_context(
        declared_screen_size=declared_screen_size,
        actual_image_size=actual_image_size,
        scale_context=scale_context,
        normalized_preview_size=normalized_preview_size,
        experiment_variant=experiment_variant,
        include_measurement_guidance=True,
    )
    profile = _audit_profile(audit_spec_label)
    metadata = prompt_metadata(audit_spec_label)
    return (
        f"Prompt版本：{metadata['prompt_version']}；Schema版本：{metadata['schema_version']}。"
        f"{profile['identity']}"
        "输出必须是 JSON，字段必须完整。证据和推断要分开，无法确认的项目放入 cannot_verify。"
        "问题 bbox 使用 [x, y, w, h] 截图像素坐标；无法可靠定位时 bbox 为 null。"
        "每个 issue 可用 rule_source_type 与 rule_source_ref 标注规范来源；"
        "B-design 审核必须填写 pdf_text、pdf_visual_example 或 alpha_case 之一，其他规范可填 null。"
        "不要编造测量数据；只有能从截图判断或后续工具可测量的内容才写入证据请求。"
        "regions 字段用于请求测量区域，distances 字段用于请求间距测量。"
        f"{profile['focus']}"
        f"{size_context}"
        f"\n\n{profile['spec_heading']}:\n"
        f"{spec_text}"
    )


def build_light_audit_prompt(
    audit_spec_label: str = "JM AI 设计规范",
    declared_screen_size: tuple[int, int] | None = None,
    actual_image_size: tuple[int, int] | None = None,
    scale_context: dict[str, Any] | None = None,
    normalized_preview_size: tuple[int, int] | None = None,
    experiment_variant: str | None = None,
) -> str:
    size_context = _size_context(
        declared_screen_size=declared_screen_size,
        actual_image_size=actual_image_size,
        scale_context=scale_context,
        normalized_preview_size=normalized_preview_size,
        experiment_variant=experiment_variant,
        include_measurement_guidance=False,
    )
    profile = _audit_profile(audit_spec_label)
    metadata = prompt_metadata(audit_spec_label)
    return (
        f"Prompt版本：{metadata['prompt_version']}；Schema版本：{metadata['schema_version']}。"
        f"{profile['light_identity']}目标是在云端稳定返回可用 JSON，"
        "不要做长篇推理，不要逐条复述规范。只根据截图可见证据判断。"
        f"{size_context}"
        f"\n\n核心规则摘要：{profile['light_rules']}"
        "\n\n输出要求："
        "必须只输出一个 JSON 对象。顶层字段使用：screen_context(string), overall_conclusion(string), "
        "major_issues(array), passes(array), issues(array), sample_points(array), regions(array), "
        "distances(array), checklist(array), cannot_verify(array)。"
        "最多输出 8 个高价值 issues；每个 issue 包含 id, category, severity(高/中/低), location, "
        "current_observation, spec_expectation, recommendation, confidence, bbox, "
        "rule_source_type, rule_source_ref。"
        "bbox 使用截图像素 [x,y,w,h]，无法定位填 null。"
        "非 B-design 审核的 rule_source_type 和 rule_source_ref 可填 null。"
        "sample_points、regions、distances 只在确实有助于后续本地取证时输出，否则为空数组。"
        "所有字段值使用简体中文。"
    )


def build_kimi_light_audit_prompt(
    audit_spec_label: str = "JM AI 设计规范",
    declared_screen_size: tuple[int, int] | None = None,
    actual_image_size: tuple[int, int] | None = None,
    scale_context: dict[str, Any] | None = None,
    normalized_preview_size: tuple[int, int] | None = None,
    experiment_variant: str | None = None,
) -> str:
    size_context = _size_context(
        declared_screen_size=declared_screen_size,
        actual_image_size=actual_image_size,
        scale_context=scale_context,
        normalized_preview_size=normalized_preview_size,
        experiment_variant=experiment_variant,
        include_measurement_guidance=False,
    )
    profile = _audit_profile(audit_spec_label)
    metadata = prompt_metadata(audit_spec_label)
    return (
        f"Prompt版本：{metadata['prompt_version']}；Schema版本：{metadata['schema_version']}。"
        f"{profile['kimi_identity']}只输出一个紧凑 JSON 对象，不要解释过程，不要 Markdown。"
        "禁止输出思考过程、分析草稿、规范复述。"
        f"{size_context}"
        f"\n\n只检查截图中最明显的规范偏差：{profile['kimi_focus']}。"
        "\n\n输出字段固定为：screen_context, overall_conclusion, major_issues, passes, issues, sample_points, regions, distances, checklist, cannot_verify。"
        "最多输出 5 个 issues。每个 issue 只包含 id, category, severity, location, current_observation, spec_expectation, recommendation, confidence, bbox。"
        "可附带 rule_source_type, rule_source_ref；非 B-design 审核可填 null。"
        "每个中文文本字段不超过 60 字；overall_conclusion 不超过 90 字；major_issues 最多 3 条；passes 最多 2 条。"
        "checklist、sample_points、regions、distances 默认输出空数组；只有非常确定且必要时才填写。"
        "bbox 使用截图像素 [x,y,w,h]，无法可靠定位填 null。所有字段值使用简体中文。"
    )


def build_b_design_applicability_prompt(
    audit_spec_label: str = "京东 B 端设计规范（B-design Agent 组件规范）",
    actual_image_size: tuple[int, int] | None = None,
    declared_screen_size: tuple[int, int] | None = None,
    scale_context: dict[str, Any] | None = None,
) -> str:
    size_context = _size_context(
        declared_screen_size=declared_screen_size,
        actual_image_size=actual_image_size,
        scale_context=scale_context,
        normalized_preview_size=None,
        experiment_variant=None,
        include_measurement_guidance=False,
    )
    metadata = prompt_metadata(audit_spec_label)
    return (
        f"Prompt版本：{metadata['prompt_version']}；Schema版本：{metadata['schema_version']}。"
        f"你是 {audit_spec_label} 适用性识别助手。"
        "你的任务只是在截图中识别是否出现 B-design 覆盖组件或扩展规则场景。"
        "覆盖来源只包括三类：pdf_text（PDF 明文规则）、pdf_visual_example（PDF 示意图归纳规则）、"
        "alpha_case（alpha 审核案例沉淀规则）。"
        "不要输出未被这些来源覆盖的通用 B 端界面问题，不要套用其他设计体系，不要输出规范违规。"
        f"{size_context}"
        "\n\nB-design 覆盖目录：\n"
        f"{b_design_component_catalog_text()}"
        "\n\n只输出 JSON 对象，字段为："
        "screen_context(string), applicability(strong/weak/none), "
        "matched_components(array), reason(string), cannot_verify(array)。"
        "matched_components 每项包含 component_id, component_name, confidence(0-1), "
        "applicability(strong/weak/none), evidence。"
        "strong 表示截图明确出现该组件；weak 表示语义或局部结构接近但需确认；"
        "none 表示未命中。未命中时 matched_components 输出空数组。"
    )


def _audit_profile(audit_spec_label: str) -> dict[str, str]:
    label = (audit_spec_label or "JM AI 设计规范").strip()
    if _is_b_design_label(label):
        return {
            "identity": f"你是 {label}审核助手。必须根据下面的 {label} 审核图片。",
            "light_identity": f"你是 {label}轻量审核助手。",
            "kimi_identity": f"你是 {label}审核助手。",
            "focus": (
                "必须覆盖 Agent 任务规划、任务节点、生成中卡片、状态栏、数据收集、"
                "深度思考、展开收起、状态文案、必有/可选元素和组件状态。"
                "同时允许检查已加载的 PDF 示意图归纳规则与 alpha 案例沉淀规则。"
                "不要套用其他设计体系的色彩、按钮、标签等无关规范；"
                "只有 pdf_text、pdf_visual_example 或 alpha_case 规则明确覆盖时，才判定为问题。"
            ),
            "light_rules": (
                "1. 优先检查 Agent 任务规划、任务节点、生成中卡片、状态栏、数据收集和深度思考组件。"
                "2. 已加载扩展规则时，也检查 PDF 示意图归纳和 alpha 案例沉淀的按钮顺序、容器、颜色语义、图标等问题。"
                "3. 必有元素缺失、状态文案错误、展开收起不清、任务阶段与节点状态不一致，应写入 issues。"
                "4. 可选元素不能因为缺失直接判定违规；截图无法确认的交互和精确尺寸写入 cannot_verify。"
                "5. 每个 issue 必须标注 rule_source_type 与 rule_source_ref，避免泛泛要求品牌色或营销入口样式。"
            ),
            "kimi_focus": "Agent 组件结构、必有元素、状态文案、展开收起、任务节点状态、生成中卡片内容、已加载扩展规则",
            "spec_heading": label,
        }
    return {
        "identity": "你是 JM AI 设计规范审核助手。必须根据下面的 JM AI 规范审核图片。",
        "light_identity": "你是 JM AI 设计规范轻量审核助手。",
        "kimi_identity": "你是 JM AI 设计规范审核助手。",
        "focus": (
            "必须覆盖色彩、字体、间距、AI 按钮、AI 标签、AI 图标、Header 层级、"
            "页面布局和组件状态，不要只围绕顶部或右上角做判断。"
            "右上角操作区仍需逐项盘点可见元素，包括下载客户端、邀好友赚套餐、"
            "续费套餐、头像/徽章/皇冠、营销按钮、状态标签和品牌徽标。"
            "其中橙色、红色、绿色、青色、黄色等非 JM AI 色彩如果用于主操作、营销入口、"
            "续费标签、头像徽章或品牌感知，应结合截图证据写入 issues；"
            "多个不同违规元素应拆成独立问题。"
        ),
        "light_rules": (
            "1. JM AI 品牌强调优先使用紫色系与 AI 渐变，主按钮、选中态、链接、状态强调不要随意使用普通蓝、橙、绿、红、黄。"
            "2. 检查字体层级、字号观感、行高和文本密度；截图无法确认精确字体族时写入 cannot_verify。"
            "3. 检查间距、内边距、卡片/表单密度、嵌套滚动和 Header 层级；无法精确测量时写入 cannot_verify。"
            "4. 检查 AI 按钮、AI 标签、AI 图标、Header、右上角商业入口和状态徽章是否符合 JM AI 品牌感知。"
        ),
        "kimi_focus": "JM AI 规范偏差：品牌紫色/渐变、按钮/标签、AI 图标、Header 层级、间距密度",
        "spec_heading": "JM AI SPEC",
    }


def _is_b_design_label(label: str) -> bool:
    normalized = (label or "").lower()
    return "b-design" in normalized or "agent 组件" in normalized


def _size_context(
    declared_screen_size: tuple[int, int] | None,
    actual_image_size: tuple[int, int] | None,
    scale_context: dict[str, Any] | None,
    normalized_preview_size: tuple[int, int] | None,
    experiment_variant: str | None,
    include_measurement_guidance: bool,
) -> str:
    if not actual_image_size and not declared_screen_size:
        return ""

    lines = ["\n\n尺寸上下文:"]
    if actual_image_size:
        lines.append(
            f"- 上传图片实际像素尺寸：{actual_image_size[0]}px × {actual_image_size[1]}px。"
        )
    if declared_screen_size:
        label = "用户声明的稿件基准尺寸" if include_measurement_guidance else "用户声明稿件基准尺寸"
        lines.append(f"- {label}：{declared_screen_size[0]}px × {declared_screen_size[1]}px。")
        if include_measurement_guidance:
            lines.append("- 请将用户声明尺寸作为判断间距、组件大小、字号比例、布局密度的前置上下文。")
    if scale_context:
        lines.append(
            "- 缩放上下文："
            f"scale_x={scale_context['x']}, "
            f"scale_y={scale_context['y']}, "
            f"uniform={scale_context['uniform']}。"
        )
        if include_measurement_guidance:
            lines.append(
                "- 所有 bbox 仍必须使用上传原图的像素坐标；间距、组件尺寸、字号和布局密度判断可参考折算后的设计像素。"
            )
    if experiment_variant:
        lines.append(f"- 实验变体：{experiment_variant}。")
    if normalized_preview_size:
        lines.append(
            f"- 规范化辅助图尺寸：{normalized_preview_size[0]}px × {normalized_preview_size[1]}px。"
        )
        if include_measurement_guidance:
            lines.append("- 规范化辅助图只用于理解布局密度；颜色、细线、截图标注坐标以原图为准。")
    if include_measurement_guidance:
        lines.append("- 如果实际图片像素尺寸与用户声明尺寸不一致，请说明差异，不要编造无法确认的测量结论。")
    return "\n".join(lines)
