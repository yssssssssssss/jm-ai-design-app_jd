import pytest

from app.audit_merge import merge_audit_attempts, merge_audits, merge_primary_with_candidates


def _audit(model: str, issues: list[dict]) -> dict:
    return {
        "model": model,
        "screen_context": "首页",
        "overall_conclusion": "存在问题",
        "major_issues": [],
        "passes": [],
        "issues": issues,
        "sample_points": [],
        "regions": [],
        "distances": [],
        "checklist": [],
        "cannot_verify": [],
    }


def test_merge_audits_combines_overlapping_issues_from_both_models():
    gpt = _audit(
        "GPT-5.5",
        [
            {
                "severity": "中",
                "location": "顶部主按钮",
                "bbox": {"x": 10, "y": 10, "width": 100, "height": 40},
                "current_observation": "主按钮颜色明显偏离 JM AI 主色",
                "spec_expectation": "使用 JM AI 规范主色 token",
                "recommendation": "改为 JM AI 主色 token",
            }
        ],
    )
    kimi = _audit(
        "Kimi-K2.6",
        [
            {
                "severity": "高",
                "location": "顶部主按钮区域",
                "bbox": {"x": 15, "y": 12, "width": 90, "height": 36},
                "current_observation": "主按钮颜色明显偏离 JM AI 规范主色",
                "spec_expectation": "使用 JM AI 规范主色 token",
                "recommendation": "改为 JM AI 主色 token",
            }
        ],
    )

    result = merge_audits([gpt, kimi])

    assert len(result["issues"]) == 1
    issue = result["issues"][0]
    assert issue["id"] == "问题-001"
    assert issue["agreement"] == "both"
    assert issue["source_models"] == ["GPT-5.5", "Kimi-K2.6"]
    assert issue["severity"] == "高"
    assert len(result["model_comparison"]["agreed_issues"]) == 1


def test_merge_audits_keeps_non_overlapping_model_only_findings():
    gpt = _audit(
        "GPT-5.5",
        [{"severity": "低", "location": "左侧导航", "bbox": {"x": 0, "y": 0, "width": 40, "height": 100}}],
    )
    kimi = _audit(
        "Kimi-K2.6",
        [{"severity": "中", "location": "底部按钮", "bbox": {"x": 300, "y": 500, "width": 80, "height": 40}}],
    )

    result = merge_audits([gpt, kimi])

    assert [issue["agreement"] for issue in result["issues"]] == ["gpt_only", "kimi_only"]
    assert len(result["model_comparison"]["gpt_only_issues"]) == 1
    assert len(result["model_comparison"]["kimi_only_issues"]) == 1
    assert result["model_comparison"]["agreed_issues"] == []


def test_merge_audits_uses_non_null_bbox_for_matching_issue():
    gpt = _audit(
        "GPT-5.5",
        [{"severity": "低", "location": "标题区域", "bbox": None, "current_observation": "标题颜色偏浅"}],
    )
    kimi = _audit(
        "Kimi-K2.6",
        [
            {
                "severity": "低",
                "location": "标题区域",
                "bbox": {"x": 1, "y": 2, "width": 30, "height": 12},
                "current_observation": "标题颜色偏浅",
            }
        ],
    )

    result = merge_audits([gpt, kimi])

    assert result["issues"][0]["bbox"] == {"x": 1, "y": 2, "width": 30, "height": 12}


def test_merge_audit_attempts_degrades_when_one_model_fails():
    attempts = [
        {"model": "GPT-5.5", "audit": _audit("GPT-5.5", [{"severity": "中", "location": "卡片标题"}])},
        {"model": "Kimi-K2.6", "error": "timeout"},
    ]

    result = merge_audit_attempts(attempts)

    assert result["issues"][0]["agreement"] == "gpt_only"
    assert result["model_comparison"]["model_failures"] == [
        {
            "model": "Kimi-K2.6",
            "error": "timeout",
            "error_type": "timeout",
            "retriable": True,
            "degraded": True,
        }
    ]
    assert "单模型降级" in result["overall_conclusion"]


def test_merge_audit_attempts_raises_when_all_models_fail():
    with pytest.raises(RuntimeError, match="全部模型审核失败"):
        merge_audit_attempts(
            [
                {"model": "GPT-5.5", "error": "bad gateway"},
                {"model": "Kimi-K2.6", "error": "timeout"},
            ]
        )


def test_merge_audits_preserves_required_top_level_fields():
    gpt = _audit("GPT-5.5", [])
    gpt.update(
        {
            "screen_context": "订单页",
            "major_issues": ["按钮颜色偏差"],
            "passes": [{"item": "字号", "result": "符合"}],
            "sample_points": [{"label": "SP-001", "x": 10, "y": 20}],
            "regions": [{"label": "主按钮", "bbox": {"x": 1, "y": 2, "width": 3, "height": 4}}],
            "distances": [{"from": "标题", "to": "按钮", "distance": 24}],
            "checklist": [{"item": "颜色", "status": "fail"}],
            "cannot_verify": [{"item": "字体族", "reason": "截图无法确认"}],
        }
    )
    kimi = _audit("Kimi-K2.6", [])

    result = merge_audits([gpt, kimi])

    for key in [
        "screen_context",
        "overall_conclusion",
        "major_issues",
        "passes",
        "sample_points",
        "regions",
        "distances",
        "checklist",
        "cannot_verify",
    ]:
        assert key in result
    assert result["screen_context"] == "订单页"
    assert result["major_issues"] == ["按钮颜色偏差"]
    assert result["passes"] == [{"item": "字号", "result": "符合"}]
    assert result["sample_points"] == [{"label": "SP-001", "x": 10, "y": 20}]
    assert result["regions"] == [{"label": "主按钮", "bbox": {"x": 1, "y": 2, "width": 3, "height": 4}}]
    assert result["distances"] == [{"from": "标题", "to": "按钮", "distance": 24}]
    assert result["checklist"] == [{"item": "颜色", "status": "fail"}]
    assert result["cannot_verify"] == [{"item": "字体族", "reason": "截图无法确认"}]


def test_merge_audits_returns_complete_model_comparison_shape():
    result = merge_audits(
        [
            _audit("Kimi-K2.6", [{"severity": "中", "location": "右侧卡片"}]),
            _audit("GPT-5.5", [{"severity": "低", "location": "左侧导航"}]),
        ]
    )

    assert set(result["model_comparison"]) == {
        "models",
        "agreed_issues",
        "gpt_only_issues",
        "kimi_only_issues",
        "conflicts",
        "model_failures",
    }
    assert result["model_comparison"]["models"] == ["GPT-5.5", "Kimi-K2.6"]
    assert result["model_comparison"]["conflicts"] == []
    assert result["model_comparison"]["model_failures"] == []


def test_merge_audits_uses_smaller_area_bbox_when_both_matching_issues_have_bboxes():
    gpt = _audit(
        "GPT-5.5",
        [
            {
                "severity": "中",
                "location": "主按钮",
                "bbox": {"x": 10, "y": 10, "width": 100, "height": 50},
                "current_observation": "按钮颜色偏离 JM AI 主色",
            }
        ],
    )
    kimi = _audit(
        "Kimi-K2.6",
        [
            {
                "severity": "中",
                "location": "主按钮",
                "bbox": {"x": 20, "y": 15, "width": 60, "height": 30},
                "current_observation": "按钮颜色偏离 JM AI 主色",
            }
        ],
    )

    result = merge_audits([gpt, kimi])

    assert result["issues"][0]["bbox"] == {"x": 20, "y": 15, "width": 60, "height": 30}


def test_merge_audits_uses_longer_text_when_merging_same_issue():
    gpt = _audit(
        "GPT-5.5",
        [
            {
                "category": "color",
                "severity": "中",
                "location": "顶部主按钮",
                "current_observation": "颜色偏差",
                "recommendation": "调整颜色",
            }
        ],
    )
    kimi = _audit(
        "Kimi-K2.6",
        [
            {
                "category": "color",
                "severity": "中",
                "location": "顶部主按钮",
                "current_observation": "顶部主按钮使用了明显偏离 JM AI 主色的蓝色",
                "recommendation": "将顶部主按钮背景改为 JM AI 规范主色 token",
            }
        ],
    )

    result = merge_audits([gpt, kimi])

    assert result["issues"][0]["current_observation"] == "顶部主按钮使用了明显偏离 JM AI 主色的蓝色"
    assert result["issues"][0]["recommendation"] == "将顶部主按钮背景改为 JM AI 规范主色 token"


def test_merge_audits_no_issues_uses_exact_conclusion_string():
    result = merge_audits([_audit("GPT-5.5", []), _audit("Kimi-K2.6", [])])

    assert result["issues"] == []
    assert result["overall_conclusion"] == "双模型审核未发现明确 JM AI 设计规范问题。"


def test_merge_audits_accepts_wrapper_shape_and_merges_overlapping_issues():
    gpt = _audit(
        "ignored",
        [
            {
                "severity": "低",
                "location": "头像徽章",
                "bbox": {"x": 10, "y": 10, "width": 40, "height": 40},
                "current_observation": "头像徽章颜色偏离 JM AI 主色",
                "spec_expectation": "头像徽章应使用 JM AI 主色 token",
            }
        ],
    )
    kimi = _audit(
        "ignored",
        [
            {
                "severity": "中",
                "location": "头像徽章区域",
                "bbox": {"x": 12, "y": 12, "width": 36, "height": 36},
                "current_observation": "头像徽章颜色偏离 JM AI 主色",
                "spec_expectation": "头像徽章应使用 JM AI 主色 token",
            }
        ],
    )

    result = merge_audits(
        [
            {"model": "GPT-5.5", "audit": gpt},
            {"model": "Kimi-K2.6", "audit": kimi},
        ]
    )

    assert len(result["issues"]) == 1
    assert result["issues"][0]["agreement"] == "both"
    assert result["issues"][0]["source_models"] == ["GPT-5.5", "Kimi-K2.6"]
    assert result["issues"][0]["severity"] == "中"


def test_merge_audits_recognizes_array_bboxes_for_iou_and_selection():
    gpt = _audit(
        "GPT-5.5",
        [{"category": "color", "severity": "中", "location": "卡片按钮", "bbox": [10, 10, 100, 50]}],
    )
    kimi = _audit(
        "Kimi-K2.6",
        [{"category": "color", "severity": "中", "location": "卡片按钮区域", "bbox": [20, 15, 60, 30]}],
    )

    result = merge_audits([gpt, kimi])

    assert len(result["issues"]) == 1
    assert result["issues"][0]["agreement"] == "both"
    assert result["issues"][0]["bbox"] == [20, 15, 60, 30]


def test_merge_audits_does_not_merge_different_findings_on_same_bbox():
    gpt = _audit(
        "GPT-5.5",
        [
            {
                "category": "color",
                "severity": "中",
                "location": "主按钮",
                "bbox": [10, 10, 100, 40],
                "current_observation": "按钮使用了非规范绿色",
                "spec_expectation": "按钮应使用 JM AI 主色 token",
            }
        ],
    )
    kimi = _audit(
        "Kimi-K2.6",
        [
            {
                "category": "spacing",
                "severity": "中",
                "location": "主按钮",
                "bbox": [10, 10, 100, 40],
                "current_observation": "按钮上下内边距过小",
                "spec_expectation": "按钮垂直内边距应符合间距规范",
            }
        ],
    )

    result = merge_audits([gpt, kimi])

    assert len(result["issues"]) == 2
    assert [issue["agreement"] for issue in result["issues"]] == ["gpt_only", "kimi_only"]


def test_merge_audits_does_not_merge_same_location_without_bbox_for_different_categories():
    gpt = _audit(
        "GPT-5.5",
        [
            {
                "category": "color",
                "severity": "中",
                "location": "主按钮",
                "current_observation": "按钮颜色不是 JM AI 主色",
                "spec_expectation": "使用主色 token",
            }
        ],
    )
    kimi = _audit(
        "Kimi-K2.6",
        [
            {
                "category": "typography",
                "severity": "低",
                "location": "主按钮",
                "current_observation": "按钮文字字号偏小",
                "spec_expectation": "使用按钮文字字号规范",
            }
        ],
    )

    result = merge_audits([gpt, kimi])

    assert len(result["issues"]) == 2
    assert [issue["agreement"] for issue in result["issues"]] == ["gpt_only", "kimi_only"]


def test_merge_audits_does_not_merge_categoryless_different_findings_on_same_bbox():
    gpt = _audit(
        "GPT-5.5",
        [
            {
                "severity": "中",
                "location": "主按钮",
                "bbox": [10, 10, 100, 40],
                "current_observation": "按钮颜色不是 JM AI 主色",
                "spec_expectation": "按钮应使用 JM AI 主色 token",
            }
        ],
    )
    kimi = _audit(
        "Kimi-K2.6",
        [
            {
                "severity": "中",
                "location": "主按钮",
                "bbox": [10, 10, 100, 40],
                "current_observation": "按钮上下内边距过小",
                "spec_expectation": "按钮垂直内边距应符合间距规范",
            }
        ],
    )

    result = merge_audits([gpt, kimi])

    assert len(result["issues"]) == 2
    assert [issue["agreement"] for issue in result["issues"]] == ["gpt_only", "kimi_only"]


def test_merge_audits_does_not_merge_categoryless_different_findings_without_bbox():
    gpt = _audit(
        "GPT-5.5",
        [
            {
                "severity": "中",
                "location": "主按钮",
                "current_observation": "按钮颜色不是 JM AI 主色",
                "spec_expectation": "按钮应使用 JM AI 主色 token",
            }
        ],
    )
    kimi = _audit(
        "Kimi-K2.6",
        [
            {
                "severity": "中",
                "location": "主按钮",
                "current_observation": "按钮上下内边距过小",
                "spec_expectation": "按钮垂直内边距应符合间距规范",
            }
        ],
    )

    result = merge_audits([gpt, kimi])

    assert len(result["issues"]) == 2
    assert [issue["agreement"] for issue in result["issues"]] == ["gpt_only", "kimi_only"]


def test_merge_audits_uses_neutral_agreement_for_unknown_single_model():
    result = merge_audits([_audit("OtherModel", [{"severity": "低", "location": "页脚"}])])

    assert result["issues"][0]["agreement"] == "model_only"
    assert result["model_comparison"]["gpt_only_issues"] == []
    assert result["model_comparison"]["kimi_only_issues"] == []


def test_merge_audit_attempts_treats_empty_audit_dict_as_success():
    with pytest.raises(RuntimeError, match="有效审核内容"):
        merge_audit_attempts([{"model": "GPT-5.5", "audit": {}}])


def test_merge_primary_with_candidates_keeps_primary_text_and_sends_unmatched_to_review():
    primary = _audit(
        "GPT-5.5",
        [
            {
                "id": "gpt-1",
                "category": "颜色和渐变",
                "severity": "中",
                "location": "顶部右上角“邀好友赚套餐”营销按钮",
                "current_observation": "该按钮使用橙色到红色的醒目渐变，并处在顶部右侧商业操作区。",
                "spec_expectation": "营销入口应使用 JM AI 紫色 token。",
                "recommendation": "改为 JM AI 紫色主导样式。",
                "confidence": 0.86,
                "bbox": [2586.0, 20.0, 216.0, 56.0],
            }
        ],
    )
    candidate = _audit(
        "Kimi-K2.6",
        [
            {
                "id": "kimi-1",
                "category": "Color",
                "severity": "高",
                "location": "顶部右上角操作区",
                "current_observation": '"邀好友赚套餐"按钮使用橙色填充背景，白色文字。',
                "spec_expectation": "营销入口应使用 JM AI 紫色品牌色。",
                "recommendation": "替换为 JM AI 紫色 token。",
                "confidence": 0.75,
                "bbox": [2623.616, 29.512, 219.696, 50.344],
            },
            {
                "id": "kimi-2",
                "category": "Brand/logo/accent color inventory",
                "severity": "中",
                "location": "左上角品牌区",
                "current_observation": "CHATEXCEL品牌徽标使用黑白配色，未体现JM AI紫色品牌色系。",
                "spec_expectation": "品牌区域应协调 JM AI 色彩。",
                "recommendation": "请人工判断是否属于产品品牌豁免。",
                "confidence": 0.6,
                "bbox": [19.104, 29.512, 280.192, 79.856],
            },
        ],
    )

    result = merge_primary_with_candidates(
        {"model": "GPT-5.5", "audit": primary, "image_size": (3184, 1736)},
        [{"model": "Kimi-K2.6", "audit": candidate, "image_size": (3184, 1736)}],
    )

    assert len(result["issues"]) == 1
    assert result["issues"][0]["current_observation"] == primary["issues"][0]["current_observation"]
    assert result["issues"][0]["severity"] == "高"
    assert result["issues"][0]["source_models"] == ["GPT-5.5", "Kimi-K2.6"]
    assert result["issues"][0]["agreement"] == "promoted_candidate"
    assert result["model_comparison"]["promoted_issues"] == result["issues"]
    assert result["model_comparison"]["primary_only_issues"] == []
    assert result["model_comparison"]["review_candidates"][0]["id"] == "kimi-2"
    assert result["model_comparison"]["review_candidates"][0]["source_model"] == "Kimi-K2.6"


def test_merge_primary_with_candidates_keeps_candidate_out_of_official_issues_by_default():
    primary = _audit("GPT-5.5", [])
    candidate = _audit(
        "Kimi-K2.6",
        [
            {
                "id": "kimi-only",
                "category": "Brand/logo/accent color inventory",
                "severity": "中",
                "location": "左上角品牌区",
                "current_observation": "品牌徽标未使用 JM AI 紫色。",
                "bbox": [20, 20, 100, 40],
            }
        ],
    )

    result = merge_primary_with_candidates(
        {"model": "GPT-5.5", "audit": primary, "image_size": (3184, 1736)},
        [{"model": "Kimi-K2.6", "audit": candidate, "image_size": (3184, 1736)}],
    )

    assert result["issues"] == []
    assert result["model_comparison"]["promoted_issues"] == []
    assert result["model_comparison"]["primary_only_issues"] == []
    assert len(result["model_comparison"]["review_candidates"]) == 1


def test_merge_audits_combines_same_real_world_issue_with_different_wording():
    gpt = _audit(
        "GPT-5.5",
        [
            {
                "category": "颜色和渐变",
                "severity": "中",
                "location": "顶部右上角“邀好友赚套餐”营销按钮",
                "current_observation": "该按钮使用橙色到红色的醒目渐变，并处在顶部右侧商业操作区。",
                "spec_expectation": "营销入口应使用 JM AI 紫色 token。",
                "recommendation": "改为 JM AI 紫色主导样式。",
                "bbox": [2586.0, 20.0, 216.0, 56.0],
            }
        ],
    )
    kimi = _audit(
        "Kimi-K2.6",
        [
            {
                "category": "Color",
                "severity": "中",
                "location": "顶部右上角操作区",
                "current_observation": '"邀好友赚套餐"按钮使用橙色填充背景，白色文字，带有礼物图标。该按钮属于营销入口，位于顶部操作区显著位置。',
                "spec_expectation": "营销入口应使用 JM AI 紫色品牌色。",
                "recommendation": "替换为 JM AI 紫色 token。",
                "bbox": [2623.616, 29.512, 219.696, 50.344],
            }
        ],
    )

    result = merge_audits([gpt, kimi])

    assert len(result["issues"]) == 1
    assert result["issues"][0]["agreement"] == "both"
    assert result["issues"][0]["source_models"] == ["GPT-5.5", "Kimi-K2.6"]
    assert len(result["model_comparison"]["agreed_issues"]) == 1
    assert result["model_comparison"]["gpt_only_issues"] == []
    assert result["model_comparison"]["kimi_only_issues"] == []


def test_merge_audits_rebuilds_checklist_from_merged_issues():
    gpt = _audit(
        "GPT-5.5",
        [
            {
                "category": "颜色和渐变",
                "severity": "中",
                "location": "顶部右上角“邀好友赚套餐”营销按钮",
                "current_observation": "该按钮使用橙色到红色的醒目渐变。",
                "bbox": [2586.0, 20.0, 216.0, 56.0],
            }
        ],
    )
    gpt["checklist"] = [
        {"item": "顶部/右上角：邀好友赚套餐", "status": "不通过", "evidence": ""}
    ]
    kimi = _audit(
        "Kimi-K2.6",
        [
            {
                "category": "Color",
                "severity": "中",
                "location": "顶部右上角操作区",
                "current_observation": '"邀好友赚套餐"按钮使用橙色填充背景，属于营销入口。',
                "bbox": [2623.616, 29.512, 219.696, 50.344],
            }
        ],
    )
    kimi["checklist"] = [
        {
            "item": "Color：顶部右上角操作区",
            "status": "不通过",
            "evidence": '"邀好友赚套餐"按钮使用橙色填充背景，属于营销入口。',
        }
    ]

    result = merge_audits([gpt, kimi])

    assert len(result["issues"]) == 1
    assert result["checklist"] == [
        {
            "item": "顶部右上角“邀好友赚套餐”营销按钮",
            "status": "不通过",
            "evidence": '"邀好友赚套餐"按钮使用橙色填充背景，属于营销入口。',
        }
    ]


def test_merge_audits_conclusion_reports_merged_counts_not_model_split():
    result = merge_audits(
        [
            _audit(
                "GPT-5.5",
                [
                    {
                        "category": "color",
                        "location": "主按钮",
                        "current_observation": "主按钮颜色偏离 JM AI 主色",
                    }
                ],
            ),
            _audit(
                "Kimi-K2.6",
                [
                    {
                        "category": "color",
                        "location": "主按钮",
                        "current_observation": "主按钮颜色偏离 JM AI 主色",
                    },
                    {
                        "category": "color",
                        "location": "续费标签",
                        "current_observation": "续费标签使用绿色",
                    },
                ],
            ),
        ]
    )

    assert "共发现 2 个" in result["overall_conclusion"]
    assert "双方共同确认 1 个" in result["overall_conclusion"]
    assert "单模型补充 1 个" in result["overall_conclusion"]
    assert "GPT-5.5 单独" not in result["overall_conclusion"]
    assert "Kimi-K2.6 单独" not in result["overall_conclusion"]


def test_merge_audits_combines_nested_region_with_specific_child_bbox():
    gpt = _audit(
        "GPT-5.5",
        [
            {
                "category": "颜色和状态标签",
                "severity": "中",
                "location": "右侧上传说明区域的绿色勾选状态",
                "current_observation": "上传文件要求说明下方使用绿色勾选图标表达支持格式和上传限制。",
                "spec_expectation": "状态强调应使用 JM AI 紫色或中性色。",
                "recommendation": "将绿色勾选改为 JM AI 紫色。",
                "bbox": [2118.0, 535.0, 520.0, 104.0],
            }
        ],
    )
    kimi = _audit(
        "Kimi-K2.6",
        [
            {
                "category": "Color",
                "severity": "中",
                "location": "右侧上传说明区",
                "current_observation": "上传文件要求说明中的对勾标记使用绿色，表示成功/支持状态。",
                "spec_expectation": "状态图标应符合 JM AI 色彩规范。",
                "recommendation": "改为 JM AI 紫色或中性色图标。",
                "bbox": [2123.728, 564.2, 31.84, 26.04],
            }
        ],
    )

    result = merge_audits([gpt, kimi])

    assert len(result["issues"]) == 1
    assert result["issues"][0]["agreement"] == "both"
    assert result["issues"][0]["bbox"] == [2123.728, 564.2, 31.84, 26.04]


def test_merge_audits_normalizes_model_scale_before_deduping_and_output():
    gpt = _audit(
        "GPT-5.5",
        [
            {
                "category": "颜色和品牌",
                "severity": "高",
                "location": "顶部右上角“邀好友赚套餐”营销按钮",
                "current_observation": "该营销按钮使用明显橙色渐变或橙色填充。",
                "bbox": [2609.0, 18.0, 226.0, 63.0],
            }
        ],
    )
    kimi = _audit(
        "Kimi-K2.6",
        [
            {
                "category": "Brand/logo/accent color inventory",
                "severity": "高",
                "location": "顶部右上角操作区-邀好友赚套餐按钮",
                "current_observation": '按钮使用橙红色渐变背景，内有礼物图标和白色文字"邀好友赚套餐"',
                "bbox": [1177.0, 21.0, 139.0, 36.0],
            },
            {
                "category": "Brand/logo/accent color inventory",
                "severity": "高",
                "location": "右侧区域-ChatExcel Pro头部卡片",
                "current_observation": "整个右侧上部卡片使用大面积绿色渐变背景。",
                "bbox": [1264.0, 96.0, 915.0, 84.0],
            },
        ],
    )

    result = merge_audits(
        [
            {"model": "GPT-5.5", "audit": gpt, "image_size": (3184, 1736)},
            {"model": "Kimi-K2.6", "audit": kimi, "image_size": (3184, 1736)},
        ]
    )

    assert len(result["issues"]) == 2
    assert result["issues"][0]["agreement"] == "both"
    assert result["issues"][0]["bbox"] == [2609.0, 18.0, 226.0, 63.0]
    assert result["issues"][0]["source_models"] == ["GPT-5.5", "Kimi-K2.6"]
    assert result["issues"][1]["bbox"] is None


def test_merge_audits_keeps_trusted_pixel_bbox_when_same_audit_has_other_position_variance():
    gpt = _audit(
        "GPT-5.5",
        [
            {
                "category": "颜色和品牌",
                "severity": "高",
                "location": "顶部右上角“邀好友赚套餐”营销按钮",
                "current_observation": "该营销按钮使用明显橙色渐变或橙色填充。",
                "bbox": [2609.0, 18.0, 226.0, 63.0],
            },
            {
                "category": "AI 按钮",
                "severity": "高",
                "location": "右侧底部上传分析需求输入框",
                "current_observation": "底部输入框外边框和左侧附件图标使用明显绿色。",
                "bbox": [2131.0, 1428.0, 995.0, 242.0],
            },
        ],
    )
    kimi = _audit(
        "Kimi-K2.6",
        [
            {
                "category": "Brand/logo/accent color inventory",
                "severity": "高",
                "location": "顶部右上角操作区-邀好友赚套餐按钮",
                "current_observation": '按钮使用橙红色渐变背景，内有礼物图标和白色文字"邀好友赚套餐"',
                "bbox": [1177.0, 21.0, 139.0, 36.0],
            }
        ],
    )

    result = merge_audits(
        [
            {"model": "GPT-5.5", "audit": gpt, "image_size": (3184, 1736)},
            {"model": "Kimi-K2.6", "audit": kimi, "image_size": (3184, 1736)},
        ]
    )

    assert result["issues"][0]["agreement"] == "both"
    assert result["issues"][0]["bbox"] == [2609.0, 18.0, 226.0, 63.0]
    assert result["issues"][1]["bbox"] == [2131.0, 1428.0, 995.0, 242.0]


def test_merge_audits_drops_untrusted_right_bottom_logical_bbox():
    result = merge_audits(
        [
            {
                "model": "Kimi-K2.6",
                "audit": _audit(
                    "Kimi-K2.6",
                    [
                        {
                            "category": "Brand/logo/accent color inventory",
                            "severity": "高",
                            "location": "右下角输入框区域",
                            "current_observation": "输入框外边框使用绿色，默认模型标签有绿色圆点。",
                            "bbox": [1264.0, 895.0, 915.0, 138.0],
                        }
                    ],
                ),
                "image_size": (3184, 1736),
            }
        ]
    )

    assert result["issues"][0]["bbox"] is None
