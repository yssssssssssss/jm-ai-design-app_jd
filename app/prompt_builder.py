from __future__ import annotations

from typing import Any


PROMPT_VERSION = "jm-audit-prompt-v1"
SCHEMA_VERSION = "jm-audit-schema-v1"


def prompt_metadata() -> dict[str, str]:
    return {
        "prompt_version": PROMPT_VERSION,
        "schema_version": SCHEMA_VERSION,
    }


def build_audit_prompt(
    spec_text: str,
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
    return (
        f"Prompt版本：{PROMPT_VERSION}；Schema版本：{SCHEMA_VERSION}。"
        "你是 JM AI 设计规范审核助手。必须根据下面的 JM AI 规范审核图片。"
        "输出必须是 JSON，字段必须完整。证据和推断要分开，无法确认的项目放入 cannot_verify。"
        "问题 bbox 使用 [x, y, w, h] 截图像素坐标；无法可靠定位时 bbox 为 null。"
        "不要编造测量数据；只有能从截图判断或后续工具可测量的内容才写入证据请求。"
        "regions 字段用于请求测量区域，distances 字段用于请求间距测量。"
        "必须覆盖色彩、字体、间距、AI 按钮、AI 标签、AI 图标、Header 层级、"
        "页面布局和组件状态，不要只围绕顶部或右上角做判断。"
        "右上角操作区仍需逐项盘点可见元素，包括下载客户端、邀好友赚套餐、"
        "续费套餐、头像/徽章/皇冠、营销按钮、状态标签和品牌徽标。"
        "其中橙色、红色、绿色、青色、黄色等非 JM AI 色彩如果用于主操作、营销入口、"
        "续费标签、头像徽章或品牌感知，应结合截图证据写入 issues；"
        "多个不同违规元素应拆成独立问题。"
        f"{size_context}"
        "\n\nJM AI SPEC:\n"
        f"{spec_text}"
    )


def build_light_audit_prompt(
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
    return (
        f"Prompt版本：{PROMPT_VERSION}；Schema版本：{SCHEMA_VERSION}。"
        "你是 JM AI 设计规范轻量审核助手。目标是在云端稳定返回可用 JSON，"
        "不要做长篇推理，不要逐条复述规范。只根据截图可见证据判断。"
        f"{size_context}"
        "\n\n核心规则摘要："
        "1. JM AI 品牌强调优先使用紫色系与 AI 渐变，主按钮、选中态、链接、状态强调不要随意使用普通蓝、橙、绿、红、黄。"
        "2. 检查字体层级、字号观感、行高和文本密度；截图无法确认精确字体族时写入 cannot_verify。"
        "3. 检查间距、内边距、卡片/表单密度、嵌套滚动和 Header 层级；无法精确测量时写入 cannot_verify。"
        "4. 检查 AI 按钮、AI 标签、AI 图标、Header、右上角商业入口和状态徽章是否符合 JM AI 品牌感知。"
        "\n\n输出要求："
        "必须只输出一个 JSON 对象。顶层字段使用：screen_context(string), overall_conclusion(string), "
        "major_issues(array), passes(array), issues(array), sample_points(array), regions(array), "
        "distances(array), checklist(array), cannot_verify(array)。"
        "最多输出 8 个高价值 issues；每个 issue 包含 id, category, severity(高/中/低), location, "
        "current_observation, spec_expectation, recommendation, confidence, bbox。"
        "bbox 使用截图像素 [x,y,w,h]，无法定位填 null。"
        "sample_points、regions、distances 只在确实有助于后续本地取证时输出，否则为空数组。"
        "所有字段值使用简体中文。"
    )


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
