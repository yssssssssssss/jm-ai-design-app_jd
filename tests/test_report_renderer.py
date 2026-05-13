from app.report_renderer import render_report_html


def _audit_payload():
    return {
        "screen_context": "首页",
        "overall_conclusion": "基本符合",
        "major_issues": ["中：按钮颜色偏差"],
        "passes": ["字号层级清晰"],
        "issues": [
            {
                "id": "color-01",
                "severity": "中",
                "category": "色彩",
                "location": "主按钮",
                "current_observation": "偏蓝",
                "spec_expectation": "应使用 #6B36FA",
                "recommendation": "改为 JM AI 主色",
                "confidence": 0.9,
                "bbox": [1, 2, 3, 4],
            }
        ],
        "checklist": [{"item": "AI 主色", "status": "不通过", "evidence": "偏蓝"}],
        "cannot_verify": [],
    }


def test_render_report_html_escapes_user_text_and_includes_image_sections():
    html = render_report_html(
        task={"title": "<script>alert(1)</script>", "summary": "部分图片存在问题"},
        image_results=[
            {
                "filename": "image-001.png",
                "audit": _audit_payload(),
                "artifacts": {
                    "annotated": "artifacts/image-001/annotated.png",
                    "tokens": "artifacts/image-001/tokens.json",
                },
            }
        ],
    )

    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "JM AI 设计规范审核报告" in html
    assert "image-001.png" in html
    assert "审核综述" in html
    assert "AI 主色" in html
    assert "artifacts/image-001/annotated.png" in html


def test_render_report_html_includes_declared_screen_size_when_present():
    html = render_report_html(
        task={
            "title": "审核",
            "summary": "完成",
            "screen_width_px": 1440,
            "screen_height_px": 900,
        },
        image_results=[],
    )

    assert "稿件基准尺寸：1440 × 900 px" in html


def test_render_report_html_includes_model_comparison_when_present():
    audit = _audit_payload()
    audit["model_comparison"] = {
        "models": ["GPT-5.5", "Kimi-K2.6"],
        "agreed_issues": [
            {
                "id": "问题-001",
                "location": "邀好友赚套餐",
                "current_observation": "橙色按钮",
            }
        ],
        "gpt_only_issues": [
            {
                "id": "问题-002",
                "location": "生成PPT",
                "current_observation": "橙色图标",
            }
        ],
        "kimi_only_issues": [
            {
                "id": "问题-003",
                "location": "续费套餐",
                "current_observation": "绿色标签",
            }
        ],
        "conflicts": [
            {
                "location": "头像徽章",
                "summary": "一个模型认为违规，另一个模型未提及",
            }
        ],
        "model_failures": [{"model": "Kimi-K2.6", "error": "timeout"}],
    }

    html = render_report_html(
        task={"title": "审核", "summary": "完成"},
        image_results=[{"filename": "image-001.png", "audit": audit, "artifacts": {}}],
    )

    assert "模型对比" in html
    assert "合并后问题总数" in html
    assert "双方一致：1" in html
    assert "单模型补充：2" in html
    assert "仅 GPT-5.5：1" not in html
    assert "仅 Kimi-K2.6：1" not in html
    assert "仅 GPT-5.5 发现的问题" not in html
    assert "仅 Kimi-K2.6 发现的问题" not in html
    assert "需人工复核" in html
    assert "模型失败信息" not in html
    assert "timeout" not in html


def test_render_report_html_includes_primary_candidate_review_items():
    audit = _audit_payload()
    audit["issues"][0]["agreement"] = "promoted_candidate"
    audit["model_comparison"] = {
        "models": ["GPT-5.5", "Kimi-K2.6"],
        "agreed_issues": [],
        "promoted_issues": [audit["issues"][0]],
        "primary_only_issues": [],
        "gpt_only_issues": [],
        "kimi_only_issues": [],
        "conflicts": [],
        "review_candidates": [
            {
                "id": "kimi-2",
                "location": "左上角品牌区",
                "current_observation": "候选模型认为品牌色需人工确认",
                "source_model": "Kimi-K2.6",
            }
        ],
        "model_failures": [],
    }

    html = render_report_html(
        task={"title": "审核", "summary": "完成"},
        image_results=[{"filename": "image-001.png", "audit": audit, "artifacts": {}}],
    )

    assert "双方一致：1" in html
    assert "单模型补充：0" in html
    assert "kimi-2" in html
    assert "候选模型认为品牌色需人工确认" in html


def test_render_report_html_includes_rule_warnings():
    audit = _audit_payload()
    audit["rule_warnings"] = [
        {
            "category": "色彩",
            "location": "邀好友赚套餐按钮",
            "current_observation": "实测颜色 #F37021 偏离 JM AI 规范色。",
            "rule_source": "color_sample",
        }
    ]

    html = render_report_html(
        task={"title": "审核", "summary": "完成"},
        image_results=[{"filename": "image-001.png", "audit": audit, "artifacts": {}}],
    )

    assert "规则证据提示" in html
    assert "邀好友赚套餐按钮" in html
    assert "color_sample" in html


def test_issues_table_hides_spec_expectation_and_shows_reference_asset_image():
    html = render_report_html(
        task={"title": "审核", "summary": "完成"},
        image_results=[{"filename": "image-001.png", "audit": _audit_payload(), "artifacts": {}}],
    )

    issues_html = html.split("详细问题清单", 1)[1].split("符合规范的点", 1)[0]
    assert "<th>规范要求</th>" not in issues_html
    assert "应使用 #6B36FA" not in issues_html
    assert "<th>编号</th>" in issues_html
    assert "<td>color-01</td>" in issues_html
    assert "<th>参考素材</th>" in issues_html
    assert 'class="spec-reference"' in issues_html
    assert 'src="/spec-snippets/color-ai-main-color.png"' in issues_html
    assert 'alt="AI 主纯色"' in issues_html
    assert "修改建议" in issues_html


def test_issues_table_falls_back_to_category_asset_when_no_snippet_matches():
    audit = _audit_payload()
    audit["issues"][0]["location"] = "品牌区域"
    audit["issues"][0]["current_observation"] = "颜色偏差"
    audit["issues"][0]["recommendation"] = "统一为规范配色，不指定具体 token"

    html = render_report_html(
        task={"title": "审核", "summary": "完成"},
        image_results=[{"filename": "image-001.png", "audit": audit, "artifacts": {}}],
    )

    issues_html = html.split("详细问题清单", 1)[1].split("符合规范的点", 1)[0]
    assert 'src="/spec-assets/color.png"' in issues_html
    assert 'alt="色彩规范参考"' in issues_html


def test_issues_table_prefers_specific_spec_snippet_when_index_matches():
    audit = _audit_payload()
    audit["issues"][0]["recommendation"] = "改为 ai/ai-normal 主色 token"

    html = render_report_html(
        task={"title": "审核", "summary": "完成"},
        image_results=[{"filename": "image-001.png", "audit": audit, "artifacts": {}}],
    )

    issues_html = html.split("详细问题清单", 1)[1].split("符合规范的点", 1)[0]
    assert 'src="/spec-snippets/color-ai-main-color.png"' in issues_html
    assert 'src="/spec-assets/color.png"' not in issues_html
    assert "ai/ai-normal" in issues_html


def test_reference_asset_images_open_zoom_modal():
    html = render_report_html(
        task={"title": "审核", "summary": "完成"},
        image_results=[{"filename": "image-001.png", "audit": _audit_payload(), "artifacts": {}}],
    )

    issues_html = html.split("详细问题清单", 1)[1].split("符合规范的点", 1)[0]
    assert '<label class="spec-reference-trigger" for="image-1-reference-1-open"' in issues_html
    assert 'aria-label="放大查看 AI 主纯色"' in issues_html
    assert '<input type="checkbox" class="image-modal-toggle" id="image-1-reference-1-open">' in issues_html
    assert 'class="image-modal" role="dialog" aria-modal="true" aria-label="AI 主纯色"' in issues_html
    assert '<label class="image-modal-close" for="image-1-reference-1-open" role="button" aria-label="关闭">×</label>' in issues_html
    assert 'href="#report-top"' not in issues_html
    assert 'href="#image-1-reference-1"' not in issues_html
    assert 'class="image-modal-viewport"' not in issues_html
    assert 'data-zoomable-image' in issues_html
    assert 'draggable="false"' in issues_html
    assert "滚轮或触控板缩放" in issues_html
    assert "拖动图片查看不同位置" in issues_html
    assert ".image-modal-toggle:checked + .image-modal" in html
    assert ".image-modal-content { position: relative; z-index: 1; max-width: 94vw; max-height: 92vh; margin: 0; background: transparent;" in html
    assert ".image-modal-img.is-dragging" in html
    assert "addEventListener(\"wheel\"" in html
    assert "addEventListener(\"pointerdown\"" in html
    assert "addEventListener(\"pointermove\"" in html
    assert "setPointerCapture" in html
    assert "event.preventDefault()" in html
    assert "image.style.transform = `translate(${panX}px, ${panY}px) scale(${scale})`" in html


def test_render_report_html_builds_protected_artifact_urls_when_task_id_is_known():
    html = render_report_html(
        task={"title": "审核", "summary": "完成"},
        image_results=[
            {
                "filename": "image-001.png",
                "audit": _audit_payload(),
                "artifacts": {
                    "annotated": "uploads/42/artifacts/image-001/annotated.png",
                    "measurements": "uploads/42/artifacts/image-001/measurements.json",
                },
            }
        ],
        task_id=42,
    )

    assert "/artifacts/42/artifacts/image-001/annotated.png" in html
    assert "/artifacts/42/artifacts/image-001/measurements.json" in html


def test_render_report_html_handles_empty_results():
    html = render_report_html(
        task={"title": "空任务", "summary": ""},
        image_results=[
            {
                "filename": "image-001.png",
                "audit": {
                    "screen_context": "首页",
                    "overall_conclusion": "未发现明确问题",
                    "major_issues": [],
                    "passes": [],
                    "issues": [],
                    "checklist": [],
                    "cannot_verify": [],
                },
                "artifacts": {},
            }
        ],
    )

    assert "未发现明确问题" in html
    assert "本图没有可生成的标注截图" in html


def test_render_report_html_collapses_cannot_verify_by_default():
    audit = _audit_payload()
    audit["cannot_verify"] = [{"item": "字体族", "reason": "截图无法确认"}]

    html = render_report_html(
        task={"title": "审核", "summary": "完成"},
        image_results=[{"filename": "image-001.png", "audit": audit, "artifacts": {}}],
    )

    pending_html = html.split('class="pending-confirmation"', 1)[1].split("</details>", 1)[0]
    assert "<details" in html
    assert 'class="pending-confirmation"' in html
    assert "<summary>" in pending_html
    assert '<span class="section-title">待确认</span>' in pending_html
    assert "open" not in pending_html.split(">", 1)[0]
    assert "字体族" in pending_html
    assert "截图无法确认" in pending_html


def test_core_conclusion_shows_compliance_status_before_summary_analysis():
    html = render_report_html(
        task={"title": "审核", "summary": "完成"},
        image_results=[
            {
                "filename": "image-001.png",
                "audit": {
                    "screen_context": "订单页",
                    "overall_conclusion": "不符合 JM AI strict mode，主按钮颜色偏差明显",
                    "major_issues": ["中：主按钮颜色 off-token"],
                    "passes": [],
                    "issues": [
                        {
                            "id": "color-01",
                            "severity": "中",
                            "category": "色彩",
                            "location": "主按钮",
                            "current_observation": "绿色按钮",
                            "spec_expectation": "应使用 JM AI 紫色",
                            "recommendation": "改为 #6B36FA",
                            "confidence": 0.91,
                            "bbox": [1, 2, 3, 4],
                        }
                    ],
                    "checklist": [],
                    "cannot_verify": [],
                },
                "artifacts": {},
            }
        ],
    )

    core_html = html.split("核心结论", 1)[1].split("审核综述", 1)[0]
    assert "整体结论：不合规" in core_html
    assert "总结分析：不符合 JM AI strict mode，主按钮颜色偏差明显" in core_html
    assert core_html.index("整体结论：不合规") < core_html.index("总结分析：")


def test_report_replaces_major_issues_with_audit_overview():
    html = render_report_html(
        task={"title": "审核", "summary": "完成"},
        image_results=[
            {
                "filename": "image-001.png",
                "audit": _audit_payload(),
                "artifacts": {},
            }
        ],
    )

    assert "主要问题" not in html
    assert "研发/验收 Checklist" not in html
    assert "审核综述" in html
    assert html.index("审核综述") < html.index("问题截图")
    overview_html = html.split("审核综述", 1)[1].split("问题截图", 1)[0]
    assert "按钮颜色偏差" not in overview_html
    assert '<table class="checklist-table">' in overview_html
    assert "AI 主色" in overview_html


def test_report_renders_quality_summary_with_rule_and_version_metadata():
    audit = _audit_payload()
    audit["prompt_version"] = "jm-audit-prompt-v1"
    audit["schema_version"] = "jm-audit-schema-v1"
    audit["rule_hits"] = [{"rule_id": "color_sample"}]
    audit["issues"][0]["bbox_status"] = "trusted"

    html = render_report_html(
        task={"title": "审核", "summary": "完成"},
        image_results=[{"filename": "image-001.png", "audit": audit, "artifacts": {}}],
    )

    quality_html = html.split("质量摘要", 1)[1].split("审核综述", 1)[0]
    assert "问题数量" in quality_html
    assert "规则命中" in quality_html
    assert "jm-audit-prompt-v1" in quality_html
    assert "可信 1" in quality_html


def test_report_includes_back_link_to_history_when_task_id_is_known():
    html = render_report_html(
        task={"title": "审核", "summary": "完成"},
        image_results=[],
        task_id=42,
    )

    assert '<a class="back-link" href="/tasks">返回</a>' in html
    assert "返回任务详情" not in html
    assert 'href="/tasks/42"' not in html


def test_render_report_html_matches_skill_report_structure():
    html = render_report_html(
        task={"title": "JoyHR 审核", "summary": "不符合 JM AI strict mode"},
        image_results=[
            {
                "filename": "image-001.png",
                "audit": {
                    "screen_context": "培训中心",
                    "overall_conclusion": "不符合 JM AI strict mode",
                    "major_issues": ["中：CTA 颜色 off-token"],
                    "passes": ["标题层级清晰"],
                    "issues": [
                        {
                            "id": "color-01",
                            "severity": "中",
                            "category": "色彩",
                            "location": "主 CTA",
                            "current_observation": "绿色按钮",
                            "spec_expectation": "应使用 JM AI 紫色",
                            "recommendation": "改为 #6B36FA",
                            "confidence": 0.91,
                            "bbox": [1, 2, 3, 4],
                        },
                        {
                            "id": "tag-01",
                            "severity": "中",
                            "category": "标签/按钮",
                            "location": "顶部功能胶囊",
                            "current_observation": "功能胶囊不符合 JM AI tag/button",
                            "spec_expectation": "应使用规范胶囊样式",
                            "recommendation": "改为 JM AI tag/button 样式",
                            "confidence": 0.88,
                            "bbox": [4, 5, 6, 7],
                        }
                    ],
                    "checklist": [
                        {"item": "字号层级", "status": "通过", "evidence": "清晰"},
                        {"item": "AI 主色", "status": "不通过", "evidence": "绿色 off-token"},
                        {"item": "字体族", "status": "无法确认", "evidence": "截图无法确认"},
                    ],
                    "cannot_verify": [{"item": "字体族", "reason": "截图无法确认"}],
                },
                "artifacts": {
                    "annotated": "artifacts/image-001/annotated.png",
                    "issue_crops": [
                        "artifacts/image-001/issue-color-01.png",
                        "artifacts/image-001/issue-tag-01.png",
                    ],
                },
            }
        ],
    )

    assert "核心结论" in html
    assert "整体结论：" in html
    assert "主要问题" not in html
    assert "研发/验收 Checklist" not in html
    assert "审核综述" in html
    assert "问题截图" in html
    assert "全图标注" in html
    assert "issue-color-01.png" in html
    assert "<figcaption>全图标注</figcaption><img" in html
    screenshots_html = html.split("问题截图", 1)[1].split("详细问题清单", 1)[0]
    assert screenshots_html.count("<figcaption>修改建议</figcaption>") == 2
    assert "color-01：绿色按钮" not in screenshots_html
    assert "tag-01：功能胶囊不符合 JM AI tag/button" not in screenshots_html
    assert html.index("全图标注") < html.index("issue-color-01.png")
    assert "<th>优先级</th>" not in html
    assert '<table class="issues-table">' in html
    assert ".issues-table th:nth-child(1), .issues-table td:nth-child(1) { width: 9%; }" in html
    assert ".issues-table th:nth-child(2), .issues-table td:nth-child(2) { width: 13%; }" in html
    assert ".issues-table th:nth-child(6), .issues-table td:nth-child(6) { width: 15%; }" in html
    assert "<th>规范要求</th>" not in html
    assert "<th>参考素材</th>" in html
    assert "/spec-snippets/color-ai-main-color.png" in html
    assert "/spec-snippets/tag-ai-capsule.png" in html
    assert "置信度" not in html
    assert "待确认" in html
    assert "无法确认项" not in html
    checklist_html = html.split("审核综述", 1)[1].split("问题截图", 1)[0]
    assert "无法确认" not in checklist_html
    assert "字体族" not in checklist_html
    assert '<table class="checklist-table">' in html
    assert '<span class="status-pass">通过</span>' in html
    assert '<span class="status-fail">不通过</span>' in html
    assert ".checklist-table th:nth-child(2), .checklist-table td:nth-child(2) { width: 16%; }" in html
    assert ".screenshots { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }" in html
    assert ".screenshot-card:not(.wide) { aspect-ratio: 1 / 1;" in html
    assert html.index("字号层级") < html.index("AI 主色")
