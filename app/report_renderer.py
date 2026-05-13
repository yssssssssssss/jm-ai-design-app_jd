from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parent.parent
SPEC_ASSET_INDEX = ROOT_DIR / "references" / "spec-assets.json"


def _text(value: Any) -> str:
    return escape("" if value is None else str(value), quote=True)


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


def _specific_spec_reference(issue: dict[str, Any]) -> tuple[str, str] | None:
    index = _spec_asset_index()
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


def _spec_asset_index() -> list[dict[str, Any]]:
    try:
        data = json.loads(SPEC_ASSET_INDEX.read_text(encoding="utf-8"))
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


def _spec_reference(issue: dict[str, Any]) -> tuple[str, str]:
    specific = _specific_spec_reference(issue)
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
    return "/spec-assets/color.png", "JM AI 规范参考"


def _spec_reference_cell(issue: dict[str, Any], modal_id: str) -> str:
    url, alt = _spec_reference(issue)
    open_id = f"{modal_id}-open"
    return (
        '<figure class="spec-reference">'
        f'<label class="spec-reference-trigger" for="{_text(open_id)}" '
        f'aria-label="放大查看 {_text(alt)}">'
        f'<img src="{_text(url)}" alt="{_text(alt)}">'
        "</label>"
        f"<figcaption>{_text(alt)}</figcaption>"
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
        f'<p class="image-modal-caption">{_text(alt)}</p>'
        "</div>"
        "</div>"
    )


def _issue_number(issue: dict[str, Any], fallback_index: int) -> str:
    issue_id = str(issue.get("id") or "").strip()
    if issue_id:
        return issue_id
    return f"{_category_slug(issue.get('category'))}-{fallback_index:02d}"


def _issues_table(issues: list[dict[str, Any]], modal_prefix: str = "issue") -> str:
    if not issues:
        return '<p class="meta">未发现明确问题。</p>'
    rows = []
    for index, issue in enumerate(issues, start=1):
        modal_id = f"{modal_prefix}-reference-{index}"
        rows.append(
            "<tr>"
            f"<td>{_text(_issue_number(issue, index))}</td>"
            f"<td>{_text(issue.get('category'))}</td>"
            f"<td>{_text(issue.get('location'))}</td>"
            f"<td>{_text(issue.get('current_observation'))}</td>"
            f"<td>{_text(issue.get('recommendation'))}</td>"
            f"<td>{_spec_reference_cell(issue, modal_id)}</td>"
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


def _comparison_issue_list(items: list[dict[str, Any]]) -> str:
    if not items:
        return '<p class="meta">无</p>'

    rows = []
    for item in items:
        label = item.get("id") or item.get("location") or "问题"
        detail = (
            item.get("current_observation")
            or item.get("summary")
            or item.get("recommendation")
            or ""
        )
        rows.append(f"<li><strong>{_text(label)}</strong>：{_text(detail)}</li>")
    return "<ul>" + "".join(rows) + "</ul>"


def _model_comparison(comparison: dict[str, Any] | None) -> str:
    if not comparison:
        return ""

    models = comparison.get("models") or []
    model_names = "、".join(str(model) for model in models) if models else "无"
    agreed_count = len(comparison.get("agreed_issues") or []) + len(
        comparison.get("promoted_issues") or []
    )
    model_a_count = len(comparison.get("gpt_only_issues") or []) + len(
        comparison.get("primary_only_issues") or []
    )
    model_b_count = len(comparison.get("kimi_only_issues") or [])
    supplemental_count = model_a_count + model_b_count
    total_count = agreed_count + model_a_count + model_b_count
    review_items = (comparison.get("conflicts") or []) + (
        comparison.get("review_candidates") or []
    )

    return f"""
      <h3>模型对比</h3>
      <p class="meta">参与模型：{_text(model_names)}</p>
      <p class="meta">合并后问题总数：{_text(total_count)}；双方一致：{_text(agreed_count)}；单模型补充：{_text(supplemental_count)}。详细问题以合并后的完整问题清单为准。</p>

      <h4>需人工复核</h4>
      {_comparison_issue_list(review_items)}
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
      <h3>质量摘要</h3>
      {_kv_table(rows, [("item", "指标"), ("value", "结果")], table_class="quality-table")}
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
) -> str:
    figures: list[str] = []
    annotated = _artifact_url(artifacts.get("annotated"), task_id)
    if annotated:
        figures.append(
            '<figure class="screenshot-card wide">'
            "<figcaption>全图标注</figcaption>"
            f'<img src="{_text(annotated)}" alt="全图标注">'
            "</figure>"
        )

    for crop in artifacts.get("issue_crops") or []:
        url = _artifact_url(crop, task_id)
        if not url:
            continue
        caption = "修改建议"
        figures.append(
            '<figure class="screenshot-card">'
            f"<figcaption>{_text(caption)}</figcaption>"
            f'<img src="{_text(url)}" alt="{_text(caption)}">'
            "</figure>"
        )

    if not figures:
        return '<p class="meta">本图没有可生成的标注截图。</p>'
    return "".join(figures)


def _image_section(index: int, result: dict[str, Any], task_id: int | None) -> str:
    audit = result.get("audit", {})
    artifacts = result.get("artifacts", {})
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
      <p class="meta">页面识别：{_text(audit.get("screen_context"))}</p>

      <h3>核心结论</h3>
      {_core_conclusion(audit)}
      {_model_comparison(audit.get("model_comparison"))}
      {_report_quality_summary(audit)}

      <h3>审核综述</h3>
      {_checklist_table(audit.get("checklist", []))}

      <h3>问题截图</h3>
      <div class="screenshots">{_screenshots(artifacts, task_id)}</div>

      <h3>详细问题清单</h3>
      {_issues_table(audit.get("issues", []), modal_prefix=f"image-{index}")}
      {_rule_warnings(audit.get("rule_warnings", []))}

      <h3>符合规范的点</h3>
      {_list(audit.get("passes", []))}

      {_cannot_verify_details(audit.get("cannot_verify", []))}

      <h3>测量证据</h3>
      <p>{evidence_html}</p>
    </section>
    """


def _back_link(task_id: int | None) -> str:
    if task_id is None:
        return ""
    return '<a class="back-link" href="/tasks">返回</a>'


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
) -> str:
    sections = "".join(
        _image_section(index, result, task_id)
        for index, result in enumerate(image_results, start=1)
    )
    if not sections:
        sections = '<section class="card"><p class="meta">暂无图片审核结果。</p></section>'

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>JM AI 设计规范审核报告</title>
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
    .back-link {{ flex: 0 0 auto; display: inline-flex; align-items: center; min-height: 32px; padding: 0 10px; border: 1px solid var(--line); border-radius: 6px; background: var(--card); text-decoration: none; font-weight: 600; }}
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
    .screenshot-card img {{ display: block; width: 100%; height: auto; }}
    .screenshot-card:not(.wide) img {{ flex: 1 1 auto; min-height: 0; object-fit: contain; background: #fbfbfc; }}
    figcaption {{ min-height: 52px; padding: 10px 12px; color: #6f6f7a; font-weight: 600; overflow-wrap: anywhere; }}
    @media (max-width: 860px) {{
      .screenshots {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    }}
    @media (max-width: 560px) {{
      main {{ padding: 20px 12px 40px; }}
      .report-header {{ display: block; }}
      .back-link {{ margin-top: 10px; }}
      .screenshots {{ grid-template-columns: 1fr; }}
      th, td {{ padding: 8px; }}
    }}
  </style>
</head>
<body>
  <main id="report-top">
    <div class="report-header">
      <h1>JM AI 设计规范审核报告</h1>
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
