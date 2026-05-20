from __future__ import annotations

import json
from html import escape
from pathlib import Path
import re
from typing import Any


ROOT_DIR = Path(__file__).resolve().parent.parent
SPEC_ASSET_INDEX = ROOT_DIR / "references" / "spec-assets.json"
COMMON_ENGLISH_REPLACEMENTS = [
    ("JM AI color token", "规范色彩令牌"),
    ("color token", "色彩令牌"),
    ("JM AI tag/button", "规范标签/按钮"),
    ("tag/button", "标签/按钮"),
    ("JM AI", "规范"),
    ("CTA", "主操作"),
    ("token", "令牌"),
    ("off-token", "未使用规范令牌"),
    ("padding", "内边距"),
    ("spacing", "间距"),
    ("gap", "间距"),
    ("button", "按钮"),
    ("tag", "标签"),
    ("header", "顶部区域"),
    ("icon", "图标"),
    ("font", "字体"),
    ("text", "文本"),
    ("primary", "主"),
    ("normal", "常规"),
]
B_DESIGN_INTERNAL_REPLACEMENTS = [
    ("pdf_visual_example", "视觉示意规则"),
    ("alpha_case", "扩展案例"),
    ("pdf_text", "明文规则"),
]


def _text(value: Any) -> str:
    return escape("" if value is None else str(value), quote=True)


def _display_recommendation(value: Any) -> str:
    text = str(value or "").strip()
    protected_tokens = re.findall(r"\b(?:ai|assist)/[a-zA-Z0-9-]+\b", text, flags=re.IGNORECASE)
    placeholders: dict[str, str] = {}
    for index, token in enumerate(protected_tokens):
        placeholder = f"__{index}__"
        placeholders[placeholder] = token
        text = text.replace(token, placeholder, 1)
    for source, target in COMMON_ENGLISH_REPLACEMENTS:
        text = re.sub(re.escape(source), target, text, flags=re.IGNORECASE)
    text = re.sub(r"\b[a-zA-Z]{2,}\b", "", text)
    for placeholder, token in placeholders.items():
        text = text.replace(placeholder, token)
    text = re.sub(r"\s{2,}", " ", text).strip()
    return text or "请按设计规范调整。"


def _display_b_design_text(value: Any) -> str:
    text = str(value or "")
    for source, target in B_DESIGN_INTERNAL_REPLACEMENTS:
        text = text.replace(source, target)
    return text


def _list(items: list[Any], empty: str = "无") -> str:
    if not items:
        return f'<p class="meta">{_text(empty)}</p>'
    return "<ul>" + "".join(f"<li>{_text(item)}</li>" for item in items) + "</ul>"


def _category_slug(category: Any) -> str:
    value = str(category or "").strip().lower()
    if any(token in value for token in ["色", "color", "colour"]):
        return "color"
    if any(token in value for token in ["标签", "胶囊", "按钮", "button", "tag"]):
        return "tag"
    if any(token in value for token in ["品牌", "视觉", "icon", "图标", "brand"]):
        return "brand"
    if any(token in value for token in ["间距", "留白", "spacing", "padding", "gap"]):
        return "spacing"
    if any(token in value for token in ["字体", "字号", "文本", "typography", "font", "text"]):
        return "type"
    return "issue"


def _specific_spec_reference(
    issue: dict[str, Any],
    spec_asset_index_path: Path | None = None,
) -> tuple[str, str] | None:
    index = _spec_asset_index(spec_asset_index_path)
    if not index:
        return None
    text = _normalized_asset_text(issue)
    best_score = 0
    best: dict[str, Any] | None = None
    for asset in index:
        score = sum(1 for keyword in asset.get("keywords", []) if _normalized_keyword(keyword) in text)
        if score > best_score:
            best_score = score
            best = asset
    if not best:
        return None
    return str(best.get("url") or ""), str(best.get("label") or "规范参考")


def _spec_asset_index(spec_asset_index_path: Path | None = None) -> list[dict[str, Any]]:
    path = spec_asset_index_path or SPEC_ASSET_INDEX
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    assets = data.get("assets") if isinstance(data, dict) else None
    return [item for item in assets or [] if isinstance(item, dict)]


def _normalized_asset_text(issue: dict[str, Any]) -> str:
    return _normalized_keyword(
        " ".join(
            str(issue.get(field) or "")
            for field in ["category", "location", "current_observation", "recommendation"]
        )
    )


def _normalized_keyword(value: Any) -> str:
    return str(value or "").lower().replace(" ", "")


def _spec_reference(
    issue: dict[str, Any],
    spec_asset_index_path: Path | None = None,
) -> tuple[str, str]:
    specific = _specific_spec_reference(issue, spec_asset_index_path)
    if specific:
        return specific

    category = str(issue.get("category") or "").lower()
    if any(token in category for token in ["色", "color", "colour"]):
        return "/spec-assets/color.png", "色彩规范参考"
    if any(token in category for token in ["间距", "留白", "spacing", "padding", "gap"]):
        return "/spec-assets/space.png", "间距规范参考"
    if any(token in category for token in ["字体", "字号", "文本", "typography", "font", "text"]):
        return "/spec-assets/font.png", "字体规范参考"
    if any(token in category for token in ["标签", "胶囊", "tag"]):
        return "/spec-assets/tags.png", "标签规范参考"
    if any(token in category for token in ["按钮", "button"]):
        return "/spec-assets/buttons.png", "按钮规范参考"
    if any(token in category for token in ["顶部", "header", "导航"]):
        return "/spec-assets/header.png", "顶部区域规范参考"

    text = " ".join(
        str(issue.get(field) or "")
        for field in ["location", "current_observation", "recommendation"]
    ).lower()
    if any(token in text for token in ["色", "color", "colour", "#"]):
        return "/spec-assets/color.png", "色彩规范参考"
    if any(token in text for token in ["间距", "留白", "spacing", "padding", "gap"]):
        return "/spec-assets/space.png", "间距规范参考"
    if any(token in text for token in ["字体", "字号", "文本", "typography", "font", "text"]):
        return "/spec-assets/font.png", "字体规范参考"
    if any(token in text for token in ["标签", "胶囊", "tag"]):
        return "/spec-assets/tags.png", "标签规范参考"
    if any(token in text for token in ["按钮", "button"]):
        return "/spec-assets/buttons.png", "按钮规范参考"
    if any(token in text for token in ["顶部", "header", "导航"]):
        return "/spec-assets/header.png", "顶部区域规范参考"
    return "/spec-assets/color.png", "规范参考"


def _spec_reference_cell(
    issue: dict[str, Any],
    modal_id: str,
    spec_asset_index_path: Path | None = None,
) -> str:
    url, alt = _spec_reference(issue, spec_asset_index_path)
    return _image_modal_trigger(
        url=url,
        alt=alt,
        modal_id=modal_id,
        figure_class="spec-reference",
        trigger_class="spec-reference-trigger",
        caption="",
    )


def _image_modal_trigger(
    *,
    url: str,
    alt: str,
    modal_id: str,
    figure_class: str,
    trigger_class: str,
    caption: str,
    caption_first: bool = False,
) -> str:
    open_id = f"{modal_id}-open"
    caption_text = str(caption or "").strip()
    figcaption = f"<figcaption>{_text(caption_text)}</figcaption>" if caption_text else ""
    modal_caption = (
        f'<p class="image-modal-caption">{_text(caption_text)}</p>'
        if caption_text
        else ""
    )
    trigger = (
        f'<label class="{_text(trigger_class)}" for="{_text(open_id)}" '
        f'aria-label="放大查看 {_text(alt)}">'
        f'<img src="{_text(url)}" alt="{_text(alt)}">'
        "</label>"
    )
    return (
        f'<figure class="{_text(figure_class)}">'
        f"{figcaption if caption_first else ''}"
        f"{trigger}"
        f"{'' if caption_first else figcaption}"
        "</figure>"
        f'<input type="checkbox" class="image-modal-toggle" id="{_text(open_id)}">'
        f'<div class="image-modal" role="dialog" '
        f'aria-modal="true" aria-label="{_text(alt)}">'
        f'<label class="image-modal-backdrop" for="{_text(open_id)}" aria-label="关闭"></label>'
        '<div class="image-modal-content">'
        f'<label class="image-modal-close" for="{_text(open_id)}" role="button" aria-label="关闭">×</label>'
        f'<img class="image-modal-img" src="{_text(url)}" alt="{_text(alt)}" '
        'data-zoomable-image draggable="false">'
        '<p class="image-modal-hint">悬停后使用滚轮或触控板缩放，拖动图片查看不同位置</p>'
        f"{modal_caption}"
        "</div>"
        "</div>"
    )


def _issue_number(issue: dict[str, Any], fallback_index: int) -> str:
    issue_id = str(issue.get("id") or "").strip()
    if issue_id:
        return issue_id
    return f"{_category_slug(issue.get('category'))}-{fallback_index:02d}"


def _crop_key_from_path(path: str) -> str:
    stem = Path(path).stem
    return stem.removeprefix("issue-")


def _issue_screenshot_context(
    issues: list[dict[str, Any]],
    artifacts: dict[str, Any],
    task_id: int | None,
) -> dict[int, dict[str, str]]:
    crops = [
        crop
        for crop in artifacts.get("issue_crops") or []
        if _artifact_url(crop, task_id)
    ]
    by_key = {_crop_key_from_path(str(crop)): str(crop) for crop in crops}
    used: set[str] = set()
    context: dict[int, dict[str, str]] = {}

    for index, issue in enumerate(issues, start=1):
        number = _issue_number(issue, index)
        crop = by_key.get(number)
        if crop is None and index <= len(crops):
            fallback = str(crops[index - 1])
            if fallback not in used:
                crop = fallback
        if crop is None:
            continue
        used.add(crop)
        url = _artifact_url(crop, task_id)
        if not url:
            continue
        recommendation = _display_recommendation(issue.get("recommendation"))
        context[index] = {
            "url": url,
            "number": number,
            "recommendation": recommendation,
            "caption": f"{number}：{recommendation}",
        }
    return context


def _issue_screenshot_cell(
    screenshot: dict[str, str] | None,
    modal_id: str,
    fallback_location: Any,
) -> str:
    if not screenshot:
        return f'<span class="meta">{_text(fallback_location or "无截图")}</span>'
    return _image_modal_trigger(
        url=screenshot["url"],
        alt=screenshot["caption"],
        modal_id=modal_id,
        figure_class="issue-crop-reference",
        trigger_class="issue-crop-trigger",
        caption=screenshot["number"],
    )


def _issues_table(
    issues: list[dict[str, Any]],
    screenshots: dict[int, dict[str, str]],
    modal_prefix: str = "issue",
    spec_asset_index_path: Path | None = None,
) -> str:
    if not issues:
        return '<p class="meta">未发现明确问题。</p>'
    rows = []
    for index, issue in enumerate(issues, start=1):
        modal_id = f"{modal_prefix}-reference-{index}"
        screenshot_modal_id = f"{modal_prefix}-screenshot-{index}"
        rows.append(
            "<tr>"
            f"<td>{_text(_issue_number(issue, index))}</td>"
            f"<td>{_text(issue.get('category'))}</td>"
            f"<td>{_issue_screenshot_cell(screenshots.get(index), screenshot_modal_id, issue.get('location'))}</td>"
            f"<td>{_text(issue.get('current_observation'))}</td>"
            f"<td>{_text(_display_recommendation(issue.get('recommendation')))}</td>"
            f"<td>{_spec_reference_cell(issue, modal_id, spec_asset_index_path)}</td>"
            "</tr>"
        )
    return (
        '<table class="issues-table"><thead><tr>'
        "<th>编号</th><th>分类</th><th>位置</th><th>当前表现</th>"
        "<th>修改建议</th><th>参考素材</th>"
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def _checklist_table(items: list[dict[str, Any]]) -> str:
    visible = [item for item in items if item.get("status") in {"通过", "不通过"}]
    visible.sort(key=lambda item: 0 if item.get("status") == "通过" else 1)
    return _kv_table(
        visible,
        [("item", "检查项"), ("status", "状态"), ("evidence", "说明")],
        table_class="checklist-table",
        cell_renderer=_checklist_cell,
    )


def _checklist_cell(key: str, value: Any) -> str:
    if key != "status":
        return _text(value)
    status = str(value or "")
    if status == "通过":
        return '<span class="status-pass">通过</span>'
    if status == "不通过":
        return '<span class="status-fail">不通过</span>'
    return _text(value)


def _kv_table(
    items: list[dict[str, Any]],
    columns: list[tuple[str, str]],
    table_class: str | None = None,
    cell_renderer: Any | None = None,
) -> str:
    if not items:
        return '<p class="meta">无</p>'
    header = "".join(f"<th>{_text(label)}</th>" for _, label in columns)
    rows = []
    for item in items:
        cells = "".join(
            f"<td>{cell_renderer(key, item.get(key)) if cell_renderer else _text(item.get(key))}</td>"
            for key, _ in columns
        )
        rows.append(f"<tr>{cells}</tr>")
    class_attr = f' class="{_text(table_class)}"' if table_class else ""
    return f"<table{class_attr}><thead><tr>{header}</tr></thead><tbody>{''.join(rows)}</tbody></table>"


def _artifact_url(path: str | None, task_id: int | None) -> str | None:
    if not path:
        return None
    if path.startswith("/"):
        return path
    if task_id is None:
        return path

    prefix = f"uploads/{task_id}/"
    normalized = path[len(prefix) :] if path.startswith(prefix) else path
    return f"/artifacts/{task_id}/{normalized}"


def _artifact_link(label: str, path: str | None, task_id: int | None) -> str:
    url = _artifact_url(path, task_id)
    if not url:
        return ""
    return f'<a href="{_text(url)}">{_text(label)}</a>'


def _compliance_status(audit: dict[str, Any]) -> str:
    conclusion = str(audit.get("overall_conclusion") or "")
    if "不符合" in conclusion or "不合规" in conclusion or audit.get("issues"):
        return "不合规"
    return "合规"


def _core_conclusion(audit: dict[str, Any]) -> str:
    summary = audit.get("overall_conclusion") or audit.get("summary") or "审核完成"
    return f"""
      <section class="core-conclusion">
        <strong>整体结论：{_text(_compliance_status(audit))}</strong>
        <p>总结分析：{_text(summary)}</p>
      </section>
    """


def _comparison_issue_list(items: list[dict[str, Any]], prefix: str | None = None) -> str:
    if not items:
        return '<p class="meta">无</p>'

    rows = []
    for index, item in enumerate(items, start=1):
        label = f"ISSUE-{prefix}-{index:02d}" if prefix else item.get("id") or item.get("location") or "问题"
        location = str(item.get("location") or "").strip()
        detail = str(
            item.get("current_observation")
            or item.get("summary")
            or item.get("recommendation")
            or ""
        ).strip()
        if location and location not in detail:
            detail = f"{location}：{detail}" if detail else location
        rows.append(f"<li><strong>{_text(label)}</strong>：{_text(detail)}</li>")
    return "<ul>" + "".join(rows) + "</ul>"


def _comparison_issue_section(
    title: str,
    items: list[dict[str, Any]],
    prefix: str | None = None,
    show_empty: bool = False,
) -> str:
    if not items and not show_empty:
        return ""
    return f"""
      <h4>{_text(title)}</h4>
      {_comparison_issue_list(items, prefix)}
    """


def _comparison_model_issues(
    comparison: dict[str, Any],
    model_name: str,
    explicit_keys: list[str],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for key in explicit_keys:
        items.extend(comparison.get(key) or [])
    for item in comparison.get("review_candidates") or []:
        if item.get("source_model") == model_name:
            items.append(item)
    return _unique_comparison_issues(items)


def _comparison_shared_issues(comparison: dict[str, Any]) -> list[dict[str, Any]]:
    return _unique_comparison_issues(
        (comparison.get("agreed_issues") or []) + (comparison.get("promoted_issues") or [])
    )


def _unique_comparison_issues(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in items:
        key = (
            str(item.get("id") or ""),
            str(item.get("location") or ""),
            str(item.get("current_observation") or item.get("summary") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def _model_comparison(comparison: dict[str, Any] | None) -> str:
    if not comparison:
        return ""

    models = comparison.get("models") or []
    model_names = "、".join(str(model) for model in models) if models else "无"
    model_a_name = str(models[0]) if len(models) >= 1 else "模型 A"
    model_b_name = str(models[1]) if len(models) >= 2 else "模型 B"
    shared_issues = _comparison_shared_issues(comparison)
    model_a_issues = _comparison_model_issues(
        comparison,
        model_a_name,
        ["gpt_only_issues", "primary_only_issues"],
    )
    model_b_issues = _unique_comparison_issues(comparison.get("kimi_only_issues") or [])
    explicit_model_a_count = len(comparison.get("gpt_only_issues") or []) + len(
        comparison.get("primary_only_issues") or []
    )
    explicit_model_b_count = len(comparison.get("kimi_only_issues") or [])
    agreed_count = len(comparison.get("agreed_issues") or []) + len(
        comparison.get("promoted_issues") or []
    )
    supplemental_count = explicit_model_a_count + explicit_model_b_count
    total_count = agreed_count + explicit_model_a_count + explicit_model_b_count
    review_items = (comparison.get("conflicts") or []) + (
        comparison.get("review_candidates") or []
    )
    model_b_weight_items = _unique_comparison_issues(model_b_issues + review_items)

    return f"""
      <details class="model-moe report-details">
      <summary>模型Moe</summary>
      <p class="meta">参与模型：{_text(model_names)}</p>
      <p class="meta">合并后问题总数：{_text(total_count)}；双方一致：{_text(agreed_count)}；单模型补充：{_text(supplemental_count)}。详细问题以合并后的完整问题清单为准。</p>

      {_comparison_issue_section("双权重", shared_issues, show_empty=True)}
      {_comparison_issue_section("G 权重", model_a_issues, "G")}
      {_comparison_issue_section("K 权重", model_b_weight_items, "K")}
      </details>
    """


def _report_quality_summary(audit: dict[str, Any]) -> str:
    issues = [issue for issue in audit.get("issues", []) if isinstance(issue, dict)]
    rule_hits = [item for item in audit.get("rule_hits", []) if isinstance(item, dict)]
    failures = (audit.get("model_comparison") or {}).get("model_failures") or []
    bbox_counts = {"trusted": 0, "suspicious": 0, "dropped": 0, "unvalidated": 0}
    for issue in issues:
        status = str(issue.get("bbox_status") or "unvalidated")
        if status not in bbox_counts:
            status = "unvalidated"
        bbox_counts[status] += 1

    rows = [
        {"item": "问题数量", "value": len(issues)},
        {"item": "规则命中", "value": len(rule_hits)},
        {"item": "模型降级", "value": len(failures)},
        {
            "item": "bbox 状态",
            "value": (
                f"可信 {bbox_counts['trusted']} / 可疑 {bbox_counts['suspicious']} / "
                f"丢弃 {bbox_counts['dropped']} / 未校验 {bbox_counts['unvalidated']}"
            ),
        },
    ]
    if audit.get("prompt_version"):
        rows.append({"item": "Prompt 版本", "value": audit.get("prompt_version")})
    if audit.get("schema_version"):
        rows.append({"item": "Schema 版本", "value": audit.get("schema_version")})

    return f"""
      <details class="pending-confirmation report-details">
        <summary><span class="section-title">质量摘要</span></summary>
      {_kv_table(rows, [("item", "指标"), ("value", "结果")], table_class="quality-table")}
      </details>
    """


def _audit_overview_details(audit: dict[str, Any]) -> str:
    return f"""
      <details class="pending-confirmation report-details">
        <summary><span class="section-title">审核综述</span></summary>
        {_checklist_table(audit.get("checklist", []))}
      </details>
    """


def _rule_warnings(items: list[dict[str, Any]]) -> str:
    if not items:
        return ""
    return f"""
      <details class="pending-confirmation">
        <summary><span class="section-title">规则证据提示</span></summary>
        {_kv_table(
            items,
            [
                ("category", "分类"),
                ("location", "位置"),
                ("current_observation", "证据"),
                ("rule_source", "来源"),
            ],
        )}
      </details>
    """


def _cannot_verify_details(items: list[dict[str, Any]]) -> str:
    return f"""
      <details class="pending-confirmation">
        <summary><span class="section-title">待确认</span></summary>
        {_kv_table(items, [("item", "项目"), ("reason", "原因")])}
      </details>
    """


def _screenshots(
    artifacts: dict[str, Any],
    task_id: int | None,
    modal_prefix: str,
    issue_screenshots: dict[int, dict[str, str]],
) -> str:
    figures: list[str] = []
    annotated = _artifact_url(artifacts.get("annotated"), task_id)
    if annotated:
        figures.append(
            _image_modal_trigger(
                url=annotated,
                alt="全图标注",
                modal_id=f"{modal_prefix}-annotated",
                figure_class="screenshot-card wide",
                trigger_class="screenshot-trigger",
                caption="全图标注",
                caption_first=True,
            )
        )

    for index, screenshot in issue_screenshots.items():
        figures.append(
            _image_modal_trigger(
                url=screenshot["url"],
                alt=screenshot["caption"],
                modal_id=f"{modal_prefix}-crop-{index}",
                figure_class="screenshot-card",
                trigger_class="screenshot-trigger",
                caption=screenshot["caption"],
                caption_first=True,
            )
        )

    if not figures:
        return '<p class="meta">本图没有可生成的标注截图。</p>'
    return "".join(figures)


def _image_section(
    index: int,
    result: dict[str, Any],
    task_id: int | None,
    spec_asset_index_path: Path | None = None,
) -> str:
    audit = result.get("audit", {})
    artifacts = result.get("artifacts", {})
    result_spec_asset_index_path = (
        result.get("spec_asset_index_path") or spec_asset_index_path
    )
    if result_spec_asset_index_path is not None and not isinstance(
        result_spec_asset_index_path,
        Path,
    ):
        result_spec_asset_index_path = Path(str(result_spec_asset_index_path))
    audit_spec_label = str(result.get("audit_spec_label") or "").strip()
    audit_spec_meta = (
        f'<p class="meta">审核规范：{_text(audit_spec_label)}</p>'
        if audit_spec_label
        else ""
    )
    issues = [issue for issue in audit.get("issues", []) if isinstance(issue, dict)]
    issue_screenshots = _issue_screenshot_context(issues, artifacts, task_id)
    evidence_links = [
        _artifact_link("颜色证据", artifacts.get("tokens"), task_id),
        _artifact_link("测量证据", artifacts.get("measurements"), task_id),
        _artifact_link("问题 JSON", artifacts.get("issues"), task_id),
        _artifact_link("模型 JSON", artifacts.get("audit_json"), task_id),
    ]
    evidence_html = " ".join(link for link in evidence_links if link)
    if not evidence_html:
        evidence_html = '<span class="meta">无</span>'

    return f"""
    <section class="card">
      <h2>{index}. {_text(result.get("filename"))}</h2>
      {audit_spec_meta}
      <p class="meta">页面识别：{_text(audit.get("screen_context"))}</p>
      {_b_design_applicability(audit)}

      <h3>核心结论</h3>
      {_core_conclusion(audit)}
      {_model_comparison(audit.get("model_comparison"))}

      <h3>问题截图</h3>
      <div class="screenshots">{_screenshots(artifacts, task_id, modal_prefix=f"image-{index}-screenshot", issue_screenshots=issue_screenshots)}</div>

      <h3>详细问题清单</h3>
      {_issues_table(
        issues,
        issue_screenshots,
        modal_prefix=f"image-{index}",
        spec_asset_index_path=result_spec_asset_index_path,
      )}
      {_rule_warnings(audit.get("rule_warnings", []))}

      <h3>符合规范的点</h3>
      {_list(audit.get("passes", []))}

      {_cannot_verify_details(audit.get("cannot_verify", []))}
      {_report_quality_summary(audit)}
      {_audit_overview_details(audit)}

      <h3>测量证据</h3>
      <p>{evidence_html}</p>
    </section>
    """


def _b_design_applicability(audit: dict[str, Any]) -> str:
    applicability = audit.get("b_design_applicability")
    if not isinstance(applicability, dict):
        return ""
    label_map = {"strong": "强适用", "weak": "弱适用", "none": "未命中"}
    status = label_map.get(str(applicability.get("applicability") or ""), "未确认")
    matches = [
        match for match in applicability.get("matched_components", [])
        if isinstance(match, dict)
    ]
    if matches:
        match_items = "".join(
            "<li>"
            f"{_text(match.get('component_name') or match.get('component_id'))}"
            f"（置信度：{_text(match.get('confidence'))}）"
            f"：{_text(_display_b_design_text(match.get('evidence')))}"
            "</li>"
            for match in matches
        )
    else:
        match_items = "<li>未识别到 B-design 覆盖组件或扩展规则场景</li>"
    sections = audit.get("loaded_spec_sections") or []
    section_text = "、".join(str(section) for section in sections) if sections else "未加载详细章节"
    reason = str(applicability.get("reason") or "").strip()
    reason_html = f"<p>{_text(_display_b_design_text(reason))}</p>" if reason else ""
    return f"""
      <details class="audit-routing" open>
        <summary>适用性判断：{_text(status)}</summary>
        {reason_html}
        <p class="meta">已加载规范章节：{_text(section_text)}</p>
        <ul>{match_items}</ul>
      </details>
    """


def _back_link(task_id: int | None) -> str:
    if task_id is None:
        return ""
    return (
        '<div class="report-actions">'
        '<a class="report-action-link" href="/tasks">返回</a>'
        f'<a class="report-action-link" href="/tasks/{task_id}/report.pdf">下载 PDF</a>'
        "</div>"
    )


def _declared_screen_size(task: dict[str, Any]) -> str:
    width = task.get("screen_width_px")
    height = task.get("screen_height_px")
    if not width or not height:
        return ""
    return f'<p>稿件基准尺寸：{_text(width)} × {_text(height)} px</p>'


def _reference_zoom_script() -> str:
    return """
  <script>
    (() => {
      const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
      const updateTransform = (image) => {
        const panX = Number(image.dataset.panX || "0");
        const panY = Number(image.dataset.panY || "0");
        const scale = Number(image.dataset.zoomScale || "1");
        image.style.transform = `translate(${panX}px, ${panY}px) scale(${scale})`;
      };
      const resetImage = (image) => {
        image.dataset.zoomScale = "1";
        image.dataset.panX = "0";
        image.dataset.panY = "0";
        image.dataset.dragging = "false";
        image.style.transformOrigin = "center center";
        image.classList.remove("is-dragging");
        updateTransform(image);
      };
      const stopDragging = (image) => {
        image.dataset.dragging = "false";
        image.classList.remove("is-dragging");
      };

      document.querySelectorAll("[data-zoomable-image]").forEach((image) => {
        resetImage(image);
        image.addEventListener("wheel", (event) => {
          event.preventDefault();
          const currentScale = Number(image.dataset.zoomScale || "1");
          const multiplier = event.deltaY < 0 ? 1.08 : 0.92;
          const nextScale = Math.round(clamp(currentScale * multiplier, 0.5, 5) * 100) / 100;
          image.dataset.zoomScale = String(nextScale);
          updateTransform(image);
        }, { passive: false });
        image.addEventListener("pointerdown", (event) => {
          event.preventDefault();
          image.dataset.dragging = "true";
          image.dataset.dragStartX = String(event.clientX);
          image.dataset.dragStartY = String(event.clientY);
          image.dataset.dragOriginX = image.dataset.panX || "0";
          image.dataset.dragOriginY = image.dataset.panY || "0";
          image.classList.add("is-dragging");
          image.setPointerCapture(event.pointerId);
        });
        image.addEventListener("pointermove", (event) => {
          if (image.dataset.dragging !== "true") return;
          event.preventDefault();
          const startX = Number(image.dataset.dragStartX || event.clientX);
          const startY = Number(image.dataset.dragStartY || event.clientY);
          const originX = Number(image.dataset.dragOriginX || "0");
          const originY = Number(image.dataset.dragOriginY || "0");
          image.dataset.panX = String(originX + event.clientX - startX);
          image.dataset.panY = String(originY + event.clientY - startY);
          updateTransform(image);
        });
        image.addEventListener("pointerup", () => stopDragging(image));
        image.addEventListener("pointercancel", () => stopDragging(image));
      });

      document.querySelectorAll(".image-modal-toggle").forEach((toggle) => {
        toggle.addEventListener("change", () => {
          if (!toggle.checked) return;
          const modal = toggle.nextElementSibling;
          const image = modal ? modal.querySelector("[data-zoomable-image]") : null;
          if (image) resetImage(image);
        });
      });
    })();
  </script>
    """


def render_report_html(
    task: dict[str, Any],
    image_results: list[dict[str, Any]],
    task_id: int | None = None,
    spec_asset_index_path: Path | None = None,
) -> str:
    audit_spec_label = str(task.get("audit_spec_label") or "JM AI 设计规范")
    sections = "".join(
        _image_section(index, result, task_id, spec_asset_index_path)
        for index, result in enumerate(image_results, start=1)
    )
    if not sections:
        sections = '<section class="card"><p class="meta">暂无图片审核结果。</p></section>'

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_text(audit_spec_label)}审核报告</title>
  <style>
    :root {{
      color-scheme: light;
      --ai: #6B36FA;
      --ai-soft: #F3F0FF;
      --text: #1f1f24;
      --muted: #767680;
      --line: #e7e7eb;
      --bg: #f7f7f9;
      --card: #ffffff;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font: 14px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", Arial, sans-serif;
    }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 32px 24px 56px; }}
    h1 {{ margin: 0 0 8px; font-size: 28px; line-height: 40px; font-weight: 600; }}
    h2 {{ margin: 0 0 12px; font-size: 20px; line-height: 30px; font-weight: 600; }}
    h3 {{ margin: 24px 0 8px; font-size: 16px; line-height: 24px; font-weight: 600; }}
    h4 {{ margin: 16px 0 6px; font-size: 14px; line-height: 22px; font-weight: 600; }}
    p {{ margin: 0 0 10px; }}
    a {{ color: var(--ai); }}
    table {{ width: 100%; border-collapse: collapse; table-layout: fixed; background: var(--card); border: 1px solid var(--line); }}
    th, td {{ padding: 10px 12px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }}
    th {{ background: #fafafa; font-weight: 600; }}
    .summary, .card {{ background: var(--card); border: 1px solid var(--line); border-radius: 8px; padding: 16px; margin-top: 16px; }}
    .core-conclusion {{ background: var(--ai-soft); border-radius: 8px; color: var(--text); padding: 12px 14px; }}
    .core-conclusion strong {{ color: var(--ai); display: inline-block; font-size: 16px; margin-bottom: 6px; }}
    .meta {{ color: var(--muted); }}
    .report-header {{ display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }}
    .report-actions {{ flex: 0 0 auto; display: flex; align-items: center; gap: 8px; }}
    .report-action-link {{ display: inline-flex; align-items: center; min-height: 32px; padding: 0 10px; border: 1px solid var(--line); border-radius: 6px; background: var(--card); text-decoration: none; font-weight: 600; }}
    .badge {{ display: inline-flex; align-items: center; min-height: 22px; padding: 0 8px; border-radius: 6px; background: var(--ai-soft); color: var(--ai); font-weight: 600; }}
    .pending-confirmation {{ margin-top: 24px; }}
    .pending-confirmation summary {{ cursor: pointer; font-size: 16px; line-height: 24px; font-weight: 600; }}
    .pending-confirmation table, .pending-confirmation .meta {{ margin-top: 8px; }}
    .section-title {{ display: inline-block; }}
    .issues-table th:nth-child(1), .issues-table td:nth-child(1) {{ width: 9%; }}
    .issues-table th:nth-child(2), .issues-table td:nth-child(2) {{ width: 13%; }}
    .issues-table th:nth-child(3), .issues-table td:nth-child(3) {{ width: 16%; }}
    .issues-table th:nth-child(4), .issues-table td:nth-child(4) {{ width: 24%; }}
    .issues-table th:nth-child(5), .issues-table td:nth-child(5) {{ width: 23%; }}
    .issues-table th:nth-child(6), .issues-table td:nth-child(6) {{ width: 15%; }}
    .spec-reference {{ margin: 0; }}
    .spec-reference-trigger {{ display: block; width: 100%; cursor: zoom-in; }}
    .spec-reference-trigger img {{ display: block; width: 100%; max-height: 150px; object-fit: contain; border: 1px solid var(--line); border-radius: 6px; background: #fbfbfc; }}
    .spec-reference-trigger:focus-visible {{ outline: 2px solid var(--ai); outline-offset: 3px; border-radius: 6px; }}
    .spec-reference figcaption {{ min-height: 0; padding: 6px 0 0; color: var(--muted); font-size: 12px; line-height: 18px; font-weight: 500; }}
    .issue-crop-reference {{ margin: 0; }}
    .issue-crop-trigger {{ display: block; width: 100%; cursor: zoom-in; }}
    .issue-crop-trigger img {{ display: block; width: 100%; max-height: 120px; object-fit: contain; border: 1px solid var(--line); border-radius: 6px; background: #fbfbfc; }}
    .issue-crop-trigger:focus-visible {{ outline: 2px solid var(--ai); outline-offset: 3px; border-radius: 6px; }}
    .issue-crop-reference figcaption {{ min-height: 0; padding: 6px 0 0; color: var(--muted); font-size: 12px; line-height: 18px; font-weight: 500; }}
    .image-modal-toggle {{ position: fixed; width: 1px; height: 1px; opacity: 0; pointer-events: none; }}
    .image-modal {{ display: none; position: fixed; inset: 0; z-index: 1000; align-items: center; justify-content: center; padding: 24px; }}
    .image-modal-toggle:checked + .image-modal {{ display: flex; }}
    .image-modal-backdrop {{ position: absolute; inset: 0; background: rgba(31, 31, 36, 0.62); }}
    .image-modal-content {{ position: relative; z-index: 1; max-width: 94vw; max-height: 92vh; margin: 0; background: transparent; }}
    .image-modal-img {{ display: block; width: auto; height: auto; max-width: 94vw; max-height: 82vh; margin: 0 auto; object-fit: contain; background: transparent; transform-origin: center center; cursor: grab; touch-action: none; user-select: none; }}
    .image-modal-img.is-dragging {{ cursor: grabbing; }}
    .image-modal-hint {{ margin: 10px 0 0; text-align: center; color: rgba(255, 255, 255, 0.86); font-size: 12px; text-shadow: 0 1px 3px rgba(0, 0, 0, 0.45); }}
    .image-modal-caption {{ margin: 10px 0 0; text-align: center; color: #fff; text-shadow: 0 1px 3px rgba(0, 0, 0, 0.45); }}
    .image-modal-close {{ position: absolute; top: 0; right: 0; z-index: 2; width: 32px; height: 32px; border: 1px solid rgba(255, 255, 255, 0.36); border-radius: 6px; background: rgba(31, 31, 36, 0.48); color: #fff; font-size: 22px; line-height: 28px; text-align: center; cursor: pointer; }}
    .checklist-table th:nth-child(1), .checklist-table td:nth-child(1) {{ width: 30%; }}
    .checklist-table th:nth-child(2), .checklist-table td:nth-child(2) {{ width: 16%; }}
    .checklist-table th:nth-child(3), .checklist-table td:nth-child(3) {{ width: 54%; }}
    .status-pass {{ color: #0F8A4C; font-weight: 700; }}
    .status-fail {{ color: #D92D20; font-weight: 700; }}
    .screenshots {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }}
    .screenshot-card {{ margin: 0; background: var(--card); border: 1px solid var(--line); border-radius: 8px; overflow: hidden; }}
    .screenshot-card.wide {{ grid-column: 1 / -1; }}
    .screenshot-card:not(.wide) {{ aspect-ratio: 1 / 1; display: flex; flex-direction: column; }}
    .screenshot-trigger {{ display: block; width: 100%; cursor: zoom-in; }}
    .screenshot-trigger img {{ display: block; width: 100%; height: auto; }}
    .screenshot-trigger:focus-visible {{ outline: 2px solid var(--ai); outline-offset: -3px; }}
    .screenshot-card:not(.wide) .screenshot-trigger {{ flex: 1 1 auto; min-height: 0; display: flex; }}
    .screenshot-card:not(.wide) .screenshot-trigger img {{ flex: 1 1 auto; min-height: 0; object-fit: contain; background: #fbfbfc; }}
    figcaption {{ min-height: 52px; padding: 10px 12px; color: #6f6f7a; font-weight: 600; overflow-wrap: anywhere; }}
    @media (max-width: 860px) {{
      .screenshots {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    }}
    @media (max-width: 560px) {{
      main {{ padding: 20px 12px 40px; }}
      .report-header {{ display: block; }}
      .report-actions {{ margin-top: 10px; }}
      .screenshots {{ grid-template-columns: 1fr; }}
      th, td {{ padding: 8px; }}
    }}
  </style>
</head>
<body>
  <main id="report-top">
    <div class="report-header">
      <h1>{_text(audit_spec_label)}审核报告</h1>
      {_back_link(task_id)}
    </div>
    <section class="summary">
      <span class="badge">{_text(task.get("summary") or "审核结果")}</span>
      <p>任务：{_text(task.get("title"))}</p>
      {_declared_screen_size(task)}
    </section>
    {sections}
  </main>
  {_reference_zoom_script()}
</body>
</html>"""
