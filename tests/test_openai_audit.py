import json

import pytest
from PIL import Image

from app.prompt_builder import (
    B_DESIGN_PROMPT_VERSION,
    B_DESIGN_SCHEMA_VERSION,
    PROMPT_VERSION,
    SCHEMA_VERSION,
)
from app.openai_audit import (
    AuditModelError,
    audit_image_with_chat,
    audit_image_with_chat_light,
    audit_image_with_kimi_light,
    audit_image,
    audit_json_schema,
    build_audit_prompt,
    image_data_url,
    parse_audit_json,
    parse_lenient_chat_audit_json,
    parse_strict_audit_json,
)


def _valid_payload():
    return {
        "screen_context": "首页",
        "overall_conclusion": "整体基本符合",
        "major_issues": [],
        "passes": [],
        "issues": [],
        "sample_points": [],
        "regions": [],
        "distances": [],
        "checklist": [],
        "cannot_verify": [],
    }


def test_build_audit_prompt_includes_spec_rules():
    prompt = build_audit_prompt("SPEC TEXT")

    assert "JM AI" in prompt
    assert "SPEC TEXT" in prompt
    assert "JSON" in prompt
    assert "bbox" in prompt


def test_build_audit_prompt_requires_balanced_audit_categories():
    prompt = build_audit_prompt("SPEC TEXT")

    assert "右上角" in prompt
    assert "色彩" in prompt
    assert "字体" in prompt
    assert "间距" in prompt
    assert "AI 按钮" in prompt
    assert "不要只围绕顶部" in prompt


def test_build_audit_prompt_includes_declared_screen_size_context():
    prompt = build_audit_prompt(
        "SPEC TEXT",
        declared_screen_size=(1440, 900),
        actual_image_size=(2880, 1800),
    )

    assert "尺寸上下文" in prompt
    assert "上传图片实际像素尺寸：2880px × 1800px" in prompt
    assert "用户声明的稿件基准尺寸：1440px × 900px" in prompt
    assert "间距、组件大小、字号比例、布局密度" in prompt


def test_build_audit_prompt_includes_scale_context_for_experiment():
    prompt = build_audit_prompt(
        "SPEC",
        declared_screen_size=(1440, 900),
        actual_image_size=(2880, 1800),
        scale_context={
            "x": 2.0,
            "y": 2.0,
            "uniform": True,
            "aspect_ratio_mismatch": False,
        },
        experiment_variant="scaled-metrics",
    )

    assert "实验变体：scaled-metrics" in prompt
    assert "scale_x=2.0" in prompt
    assert "scale_y=2.0" in prompt
    assert "所有 bbox 仍必须使用上传原图的像素坐标" in prompt


def test_build_audit_prompt_mentions_normalized_preview_contract():
    prompt = build_audit_prompt(
        "SPEC",
        declared_screen_size=(1440, 900),
        actual_image_size=(2880, 1800),
        normalized_preview_size=(1440, 900),
        experiment_variant="normalized-preview",
    )

    assert "实验变体：normalized-preview" in prompt
    assert "规范化辅助图尺寸：1440px × 900px" in prompt
    assert "规范化辅助图只用于理解布局密度" in prompt
    assert "颜色、细线、截图标注坐标以原图为准" in prompt


def test_parse_audit_json_accepts_minimal_valid_payload():
    result = parse_audit_json(json.dumps(_valid_payload(), ensure_ascii=False))

    assert result["screen_context"] == "首页"
    assert result["issues"] == []


def test_parse_audit_json_rejects_missing_required_key():
    try:
        parse_audit_json('{"screen_context":"x"}')
    except AuditModelError as exc:
        assert "overall_conclusion" in str(exc)
    else:
        raise AssertionError("missing keys should fail")


def test_parse_strict_audit_json_rejects_missing_arrays_even_for_chat_shape():
    with pytest.raises(AuditModelError, match="major_issues"):
        parse_strict_audit_json(
            json.dumps(
                {
                    "screen_context": "首页",
                    "overall_conclusion": "基本符合",
                    "issues": [],
                },
                ensure_ascii=False,
            )
        )


def test_parse_lenient_chat_audit_json_fills_missing_arrays_for_fallback_models():
    result = parse_lenient_chat_audit_json(
        json.dumps(
            {
                "screen_context": "首页",
                "overall_conclusion": "基本符合",
                "issues": [],
            },
            ensure_ascii=False,
        ),
        image_size=(1000, 500),
    )

    assert result["major_issues"] == []
    assert result["passes"] == []
    assert result["sample_points"] == []
    assert result["checklist"] == []


def test_parse_audit_json_can_fill_missing_arrays_for_chat_models():
    result = parse_audit_json(
        json.dumps(
            {
                "screen_context": "首页",
                "overall_conclusion": "基本符合",
                "issues": [],
                "regions": [],
                "distances": [],
                "cannot_verify": [],
            },
            ensure_ascii=False,
        ),
        allow_missing_arrays=True,
        image_size=(1000, 500),
    )

    assert result["major_issues"] == []
    assert result["passes"] == []
    assert result["sample_points"] == []
    assert result["checklist"] == []


def test_parse_audit_json_preserves_b_design_rule_source_fields():
    result = parse_lenient_chat_audit_json(
        json.dumps(
            {
                "screen_context": "标题优化页面",
                "overall_conclusion": "模型已完成审核。",
                "issues": [
                    {
                        "id": "button-order-01",
                        "category": "按钮顺序",
                        "severity": "warning",
                        "location": "底部操作区",
                        "current_observation": "取消在左，预览确认在右。",
                        "spec_expectation": "alpha 案例要求确认动作在左、取消动作在右。",
                        "recommendation": "调整为预览确认在左、取消在右。",
                        "rule_source_type": "alpha_case",
                        "rule_source_ref": "references/alpha/image.png_NDR-SQ 1.png",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        audit_spec_label="京东 B 端设计规范（B-design Agent 组件规范）",
    )

    assert result["issues"][0]["rule_source_type"] == "alpha_case"
    assert result["issues"][0]["rule_source_ref"] == "references/alpha/image.png_NDR-SQ 1.png"


def test_parse_audit_json_normalizes_chat_category_payloads():
    result = parse_audit_json(
        json.dumps(
            {
                "conclusion": "pass_with_cautions",
                "categories": {
                    "color": {
                        "status": "fail",
                        "items": [
                            {
                                "issue": "Off-token green accent",
                                "evidence": "绿色按钮不是 JM AI token",
                                "inference": "违反颜色规范",
                                "bbox": [0.1, 0.2, 0.3, 0.4],
                                "severity": "high",
                            }
                        ],
                    }
                },
                "cannot_verify": {"item": "字体族", "reason": "截图无法确认"},
            },
            ensure_ascii=False,
        ),
        allow_missing_arrays=True,
        image_size=(1000, 500),
    )

    assert result["screen_context"] == "模型未返回页面识别"
    assert "需要调整" in result["overall_conclusion"]
    assert result["issues"][0]["severity"] == "高"
    assert result["issues"][0]["bbox"] == [100.0, 100.0, 300.0, 200.0]
    assert result["major_issues"] == ["绿色按钮不是 JM AI token"]
    assert result["cannot_verify"] == [{"item": "字体族", "reason": "截图无法确认"}]


def test_parse_audit_json_normalizes_chat_problem_payloads():
    result = parse_audit_json(
        json.dumps(
            {
                "screen_context": "AI Excel 页面",
                "overall_conclusion": "模型已完成审核。",
                "problems": [
                    {
                        "title": "绿色主按钮不符合 JM AI 色彩",
                        "category": "color",
                        "severity": "warning",
                        "evidence": "右上角按钮使用绿色",
                        "expectation": "AI 品牌按钮应使用紫色 token",
                        "suggestion": "改为 #6B36FA",
                        "bbox": [100, 20, 180, 40],
                    }
                ],
                "cannot_verify": [],
            },
            ensure_ascii=False,
        ),
        allow_missing_arrays=True,
        image_size=(1000, 500),
    )

    assert result["overall_conclusion"] == "存在 1 个需要调整的 JM AI 设计规范问题。"
    assert result["issues"][0]["category"] == "color"
    assert result["issues"][0]["severity"] == "中"
    assert result["issues"][0]["location"] == "绿色主按钮不符合 JM AI 色彩"
    assert result["issues"][0]["current_observation"] == "右上角按钮使用绿色"
    assert result["issues"][0]["spec_expectation"] == "AI 品牌按钮应使用紫色 token"
    assert result["issues"][0]["recommendation"] == "改为 #6B36FA"
    assert result["major_issues"] == ["右上角按钮使用绿色"]
    assert result["checklist"] == [
        {
            "item": "color：绿色主按钮不符合 JM AI 色彩",
            "status": "不通过",
            "evidence": "右上角按钮使用绿色",
        }
    ]


def test_parse_audit_json_normalizes_nested_evidence_payloads():
    result = parse_audit_json(
        json.dumps(
            {
                "issues": [
                    {
                        "id": "1",
                        "category": "Color",
                        "severity": "high",
                        "evidence": {
                            "description": "右上角橙色 pill 按钮",
                            "bbox": [0.793, 0.025, 0.883, 0.05],
                        },
                    }
                ],
                "cannot_verify": [],
            },
            ensure_ascii=False,
        ),
        allow_missing_arrays=True,
        image_size=(2000, 1000),
    )

    assert result["issues"][0]["current_observation"] == "右上角橙色 pill 按钮"
    assert result["issues"][0]["bbox"] == [1586.0, 25.0, 180.0, 25.0]
    assert result["checklist"][0]["evidence"] == "右上角橙色 pill 按钮"


def test_parse_audit_json_flattens_sectioned_chat_payloads():
    result = parse_audit_json(
        json.dumps(
            {
                "audit_summary": {"overall_status": "needs_review"},
                "color_and_gradients": {
                    "issues": [
                        {
                            "id": "COLOR-001",
                            "severity": "warning",
                            "category": "brand_color",
                            "description": "橙色按钮不是 JM AI token",
                            "evidence": {
                                "bbox": [0.848, 0.027, 0.894, 0.052],
                                "description": "右上角橙色按钮",
                            },
                            "inference": "应使用紫色品牌 token",
                        }
                    ],
                    "passed": [
                        {
                            "id": "COLOR-PASS-001",
                            "description": "标题高亮使用紫色",
                        }
                    ],
                    "cannot_verify": [
                        {"description": "渐变角度", "reason": "静态截图无法确认"}
                    ],
                },
                "evidence_requests": {
                    "regions": [
                        {
                            "id": "REG-001",
                            "description": "测量卡片间距",
                            "purpose": "measure_card_gap",
                            "approximate_bbox": [0.1, 0.2, 0.3, 0.4],
                        }
                    ]
                },
            },
            ensure_ascii=False,
        ),
        allow_missing_arrays=True,
        image_size=(2000, 1000),
    )

    assert result["overall_conclusion"] == "存在 1 个需要调整的 JM AI 设计规范问题。"
    assert result["issues"][0]["id"] == "COLOR-001"
    assert result["issues"][0]["current_observation"] == "右上角橙色按钮"
    assert result["issues"][0]["bbox"] == [1696.0, 27.0, 92.0, 25.0]
    assert result["passes"] == ["标题高亮使用紫色"]
    assert result["cannot_verify"] == [{"item": "渐变角度", "reason": "静态截图无法确认"}]
    assert result["regions"][0]["bbox"] == [200.0, 200.0, 600.0, 400.0]


def test_parse_audit_json_normalizes_checklist_statuses():
    result = parse_audit_json(
        json.dumps(
            {
                "screen_context": "首页",
                "overall_conclusion": "基本符合",
                "issues": [],
                "checklist": [
                    {"item": "颜色", "status": "fail", "reason": "绿色 off-token"},
                    {"item": "字体", "status": "pass", "reason": "层级清晰"},
                    {"item": "间距", "status": "uncertain", "reason": "截图无法确认"},
                ],
            },
            ensure_ascii=False,
        ),
        allow_missing_arrays=True,
    )

    assert result["checklist"] == [
        {"item": "颜色", "status": "不通过", "evidence": "绿色 off-token"},
        {"item": "字体", "status": "通过", "evidence": "层级清晰"},
        {"item": "间距", "status": "无法确认", "evidence": "截图无法确认"},
    ]


def test_parse_audit_json_normalizes_bbox_sample_points():
    result = parse_audit_json(
        json.dumps(
            {
                "screen_context": "首页",
                "overall_conclusion": "基本符合",
                "issues": [],
                "sample_points": [
                    {
                        "id": "SP-001",
                        "description": "Measure color",
                        "bbox": [0.1, 0.2, 0.3, 0.4],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        allow_missing_arrays=True,
        image_size=(1000, 500),
    )

    assert result["sample_points"] == [{"label": "SP-001", "x": 250, "y": 150}]


def test_parse_audit_json_promotes_failed_checklist_to_issues():
    result = parse_audit_json(
        json.dumps(
            {
                "screen_context": "首页",
                "overall_conclusion": "模型已完成审核。",
                "issues": [],
                "checklist": [
                    {"item": "颜色", "status": "fail", "reason": "绿色 off-token"},
                    {"item": "字体", "status": "pass", "reason": "层级清晰"},
                ],
            },
            ensure_ascii=False,
        ),
        allow_missing_arrays=True,
    )

    assert result["overall_conclusion"] == "存在 1 个需要调整的 JM AI 设计规范问题。"
    assert result["issues"][0]["location"] == "颜色"
    assert result["issues"][0]["current_observation"] == "绿色 off-token"
    assert result["major_issues"] == ["绿色 off-token"]


def test_lenient_parse_uses_selected_spec_label_for_generic_b_design_conclusion():
    result = parse_lenient_chat_audit_json(
        """
        {
          "screen_context": "Agent 任务页",
          "overall_conclusion": "fail",
          "issues": [
            {
              "category": "任务规划",
              "location": "任务规划卡片",
              "description": "缺少展开收起按钮"
            }
          ]
        }
        """,
        audit_spec_label="京东 B 端设计规范（B-design Agent 组件规范）",
    )

    assert result["overall_conclusion"] == "存在不符合京东 B 端设计规范（B-design Agent 组件规范）的问题。"
    assert result["issues"][0]["recommendation"] == "请按京东 B 端设计规范（B-design Agent 组件规范）调整。"


def test_parse_audit_json_localizes_common_english_chat_output():
    result = parse_audit_json(
        json.dumps(
            {
                "screen_context": "ChatExcel Max product interface with left sidebar",
                "overall_conclusion": "The interface uses non-compliant orange and green accents.",
                "issues": [
                    {
                        "id": "COLOR-001",
                        "category": "Color and gradients",
                        "severity": "warning",
                        "location": "Top right header area",
                        "current_observation": "Orange invite button is not a JM AI color token.",
                        "spec_expectation": "Primary action buttons should use JM AI purple tokens.",
                        "recommendation": "Change the button to #6B36FA.",
                        "confidence": 0.8,
                        "bbox": [10, 20, 30, 40],
                    }
                ],
                "passes": ["Purple title text appears consistent with JM AI primary colors."],
                "checklist": [
                    {
                        "item": "Primary action buttons use AI tokens",
                        "status": "fail",
                        "reason": "Orange button is off-token",
                    }
                ],
                "cannot_verify": [
                    {
                        "item": "Exact font family",
                        "reason": "Screenshot cannot expose CSS font stack",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        allow_missing_arrays=True,
    )

    assert result["screen_context"] == "ChatExcel Max 产品界面，包含左侧导航"
    assert result["overall_conclusion"] == "界面使用了不符合规范的橙色和绿色强调色。"
    assert result["issues"][0]["category"] == "颜色与渐变"
    assert result["issues"][0]["location"] == "右上角头部区域"
    assert result["issues"][0]["current_observation"] == "橙色邀请按钮不是 JM AI 颜色 token。"
    assert result["issues"][0]["spec_expectation"] == "主要操作按钮应使用 JM AI 紫色 token。"
    assert result["issues"][0]["recommendation"] == "将按钮改为 #6B36FA。"
    assert result["passes"] == ["紫色标题文本看起来符合 JM AI 主色。"]
    assert result["checklist"][0]["item"] == "主要操作按钮使用 AI token"
    assert result["checklist"][0]["evidence"] == "橙色按钮偏离 token"
    assert result["cannot_verify"][0]["item"] == "精确字体族"
    assert result["cannot_verify"][0]["reason"] == "截图无法暴露 CSS 字体栈"


def test_parse_audit_json_rejects_empty_chat_audit_payload():
    try:
        parse_audit_json(
            json.dumps(
                {
                    "screen_context": ":",
                    "overall_conclusion": "模型已完成审核。",
                    "issues": [],
                    "major_issues": [],
                    "checklist": [],
                    "passes": [],
                    "cannot_verify": [],
                    "regions": [],
                    "distances": [],
                    "sample_points": [],
                },
                ensure_ascii=False,
            ),
            allow_missing_arrays=True,
        )
    except AuditModelError as exc:
        assert "模型未返回有效审核内容" in str(exc)
    else:
        raise AssertionError("empty chat audit should fail")


def test_parse_audit_json_rejects_non_object_payload():
    try:
        parse_audit_json("[]")
    except AuditModelError as exc:
        assert "对象" in str(exc)
    else:
        raise AssertionError("non-object JSON should fail")


def test_image_data_url_uses_media_type_and_base64(tmp_path):
    path = tmp_path / "screen.jpg"
    Image.new("RGB", (2, 2), color=(107, 54, 250)).save(path)

    url = image_data_url(path)

    assert url.startswith("data:image/jpeg;base64,")
    assert len(url.split(",", 1)[1]) > 0


def test_audit_json_schema_requires_core_fields():
    schema = audit_json_schema()

    assert schema["type"] == "json_schema"
    assert schema["strict"] is True
    assert schema["schema"]["additionalProperties"] is False
    assert set(_valid_payload()).issubset(set(schema["schema"]["required"]))


def test_audit_json_schema_has_strict_nested_objects():
    schema = audit_json_schema()["schema"]["properties"]

    for key in ["regions", "distances", "checklist", "cannot_verify"]:
        item_schema = schema[key]["items"]
        assert item_schema["type"] == "object"
        assert item_schema["additionalProperties"] is False
        assert item_schema["required"] == list(item_schema["properties"])


def test_audit_json_schema_allows_rule_source_metadata_on_issues():
    issue_schema = audit_json_schema()["schema"]["properties"]["issues"]["items"]

    assert "rule_source_type" in issue_schema["properties"]
    assert "rule_source_ref" in issue_schema["properties"]
    assert "rule_source_type" in issue_schema["required"]
    assert "rule_source_ref" in issue_schema["required"]


def test_audit_image_calls_responses_api_with_schema_and_data_url(tmp_path):
    image_path = tmp_path / "screen.png"
    Image.new("RGB", (2, 2), color=(107, 54, 250)).save(image_path)
    payload = _valid_payload()

    class FakeResponses:
        def __init__(self):
            self.kwargs = None

        def create(self, **kwargs):
            self.kwargs = kwargs

            class Response:
                output_text = json.dumps(payload, ensure_ascii=False)

            return Response()

    class FakeClient:
        def __init__(self):
            self.responses = FakeResponses()

    client = FakeClient()

    result = audit_image(client, "test-model", image_path, "SPEC")

    assert {key: result[key] for key in payload} == payload
    assert result["prompt_version"] == PROMPT_VERSION
    assert result["schema_version"] == SCHEMA_VERSION
    assert client.responses.kwargs["model"] == "test-model"
    content = client.responses.kwargs["input"][0]["content"]
    assert content[0]["type"] == "input_text"
    assert "SPEC" in content[0]["text"]
    assert content[1]["type"] == "input_image"
    assert content[1]["image_url"].startswith("data:image/png;base64,")
    assert client.responses.kwargs["text"]["format"]["type"] == "json_schema"
    assert "reasoning" not in client.responses.kwargs


def test_audit_image_uses_b_design_metadata_without_jm_ai_prompt_labels(tmp_path):
    image_path = tmp_path / "screen.png"
    Image.new("RGB", (2, 2), color=(107, 54, 250)).save(image_path)
    payload = _valid_payload()
    spec_text = """# B-design Agent 组件规范

## 通用审核原则
只能依据 B-design PDF 内容。

## 数据收集
数据收集组件必须清晰展示上传和收集状态。

## 任务节点
任务节点组件必须展示一级节点和二级节点。
"""
    applicability = {
        "screen_context": "上传文件页面",
        "applicability": "weak",
        "matched_components": [
            {
                "component_id": "data-collection",
                "component_name": "数据收集",
                "confidence": 0.58,
                "applicability": "weak",
                "evidence": "截图中有上传文件区域。",
            }
        ],
        "reason": "命中数据收集候选组件。",
        "cannot_verify": [],
    }

    class FakeResponses:
        def __init__(self):
            self.calls = []

        def create(self, **kwargs):
            self.calls.append(kwargs)
            output = applicability if len(self.calls) == 1 else payload

            class Response:
                output_text = json.dumps(output, ensure_ascii=False)

            return Response()

    class FakeClient:
        def __init__(self):
            self.responses = FakeResponses()

    client = FakeClient()

    result = audit_image(
        client,
        "test-model",
        image_path,
        spec_text,
        audit_spec_label="京东 B 端设计规范（B-design Agent 组件规范）",
    )

    routing_prompt = client.responses.calls[0]["input"][0]["content"][0]["text"]
    prompt = client.responses.calls[1]["input"][0]["content"][0]["text"]
    assert result["prompt_version"] == B_DESIGN_PROMPT_VERSION
    assert result["schema_version"] == B_DESIGN_SCHEMA_VERSION
    assert result["loaded_spec_sections"] == ["通用审核原则", "数据收集"]
    assert "适用性识别" in routing_prompt
    assert B_DESIGN_PROMPT_VERSION in prompt
    assert "数据收集组件必须清晰展示上传和收集状态" in prompt
    assert "任务节点组件必须展示一级节点和二级节点" not in prompt
    assert PROMPT_VERSION not in prompt
    assert SCHEMA_VERSION not in prompt
    assert "JM AI" not in prompt


def test_audit_image_passes_reasoning_effort_when_configured(tmp_path):
    image_path = tmp_path / "screen.png"
    Image.new("RGB", (2, 2), color=(107, 54, 250)).save(image_path)
    payload = _valid_payload()

    class FakeResponses:
        def __init__(self):
            self.kwargs = None

        def create(self, **kwargs):
            self.kwargs = kwargs

            class Response:
                output_text = json.dumps(payload, ensure_ascii=False)

            return Response()

    class FakeClient:
        def __init__(self):
            self.responses = FakeResponses()

    client = FakeClient()

    audit_image(client, "test-model", image_path, "SPEC", reasoning_effort="xhigh")

    assert client.responses.kwargs["reasoning"] == {"effort": "xhigh"}


def test_audit_image_passes_declared_and_actual_size_to_prompt(tmp_path):
    image_path = tmp_path / "screen.png"
    Image.new("RGB", (32, 18), color=(107, 54, 250)).save(image_path)
    payload = _valid_payload()

    class FakeResponses:
        def __init__(self):
            self.kwargs = None

        def create(self, **kwargs):
            self.kwargs = kwargs

            class Response:
                output_text = json.dumps(payload, ensure_ascii=False)

            return Response()

    class FakeClient:
        def __init__(self):
            self.responses = FakeResponses()

    client = FakeClient()

    audit_image(
        client,
        "test-model",
        image_path,
        "SPEC",
        declared_screen_size=(1440, 900),
    )

    prompt = client.responses.kwargs["input"][0]["content"][0]["text"]
    assert "上传图片实际像素尺寸：32px × 18px" in prompt
    assert "用户声明的稿件基准尺寸：1440px × 900px" in prompt


def test_audit_image_with_chat_calls_chat_completions_with_image(tmp_path):
    image_path = tmp_path / "screen.png"
    Image.new("RGB", (2, 2), color=(107, 54, 250)).save(image_path)
    payload = _valid_payload()

    class FakeCompletions:
        def __init__(self):
            self.kwargs = None

        def create(self, **kwargs):
            self.kwargs = kwargs

            class Message:
                content = json.dumps(payload, ensure_ascii=False)

            class Choice:
                message = Message()

            class Response:
                choices = [Choice()]

            return Response()

    class FakeChat:
        def __init__(self):
            self.completions = FakeCompletions()

    class FakeClient:
        def __init__(self):
            self.chat = FakeChat()

    client = FakeClient()

    result = audit_image_with_chat(client, "jd-model", image_path, "SPEC")

    assert {key: result[key] for key in payload} == payload
    assert result["prompt_version"] == PROMPT_VERSION
    assert result["schema_version"] == SCHEMA_VERSION
    kwargs = client.chat.completions.kwargs
    assert kwargs["model"] == "jd-model"
    assert kwargs["response_format"] == {"type": "json_object"}
    assert "extra_body" not in kwargs
    content = kwargs["messages"][0]["content"]
    assert content[0]["type"] == "text"
    assert "SPEC" in content[0]["text"]
    assert "必须只输出一个 JSON 对象" in content[0]["text"]
    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_audit_image_with_chat_passes_reasoning_effort_when_configured(tmp_path):
    image_path = tmp_path / "screen.png"
    Image.new("RGB", (2, 2), color=(107, 54, 250)).save(image_path)
    payload = _valid_payload()

    class FakeCompletions:
        def __init__(self):
            self.kwargs = None

        def create(self, **kwargs):
            self.kwargs = kwargs

            class Message:
                content = json.dumps(payload, ensure_ascii=False)

            class Choice:
                message = Message()

            class Response:
                choices = [Choice()]

            return Response()

    class FakeChat:
        def __init__(self):
            self.completions = FakeCompletions()

    class FakeClient:
        def __init__(self):
            self.chat = FakeChat()

    client = FakeClient()

    audit_image_with_chat(client, "jd-model", image_path, "SPEC", reasoning_effort="medium")

    assert client.chat.completions.kwargs["reasoning"] == {"effort": "medium"}


def test_audit_image_with_chat_requests_enough_output_tokens(tmp_path):
    image_path = tmp_path / "screen.png"
    Image.new("RGB", (2, 2), color=(107, 54, 250)).save(image_path)
    payload = _valid_payload()

    class FakeCompletions:
        def __init__(self):
            self.kwargs = None

        def create(self, **kwargs):
            self.kwargs = kwargs

            class Message:
                content = json.dumps(payload, ensure_ascii=False)

            class Choice:
                message = Message()

            class Response:
                choices = [Choice()]

            return Response()

    class FakeChat:
        def __init__(self):
            self.completions = FakeCompletions()

    class FakeClient:
        def __init__(self):
            self.chat = FakeChat()

    client = FakeClient()

    audit_image_with_chat(client, "jd-model", image_path, "SPEC")

    assert client.chat.completions.kwargs["max_tokens"] == 32768


def test_audit_image_with_chat_light_uses_compact_prompt_and_output_budget(tmp_path):
    image_path = tmp_path / "screen.png"
    Image.new("RGB", (2, 2), color=(107, 54, 250)).save(image_path)
    payload = _valid_payload()
    full_spec = "VERY LONG SPEC " * 1000

    class FakeCompletions:
        def __init__(self):
            self.kwargs = None

        def create(self, **kwargs):
            self.kwargs = kwargs

            class Message:
                content = json.dumps(payload, ensure_ascii=False)

            class Choice:
                message = Message()

            class Response:
                choices = [Choice()]

            return Response()

    class FakeChat:
        def __init__(self):
            self.completions = FakeCompletions()

    class FakeClient:
        def __init__(self):
            self.chat = FakeChat()

    client = FakeClient()

    result = audit_image_with_chat_light(client, "jd-model", image_path, full_spec)

    assert {key: result[key] for key in payload} == payload
    assert result["prompt_version"] == PROMPT_VERSION
    assert result["schema_version"] == SCHEMA_VERSION
    kwargs = client.chat.completions.kwargs
    prompt = kwargs["messages"][0]["content"][0]["text"]
    assert kwargs["max_tokens"] == 8192
    assert "轻量审核" in prompt
    assert "VERY LONG SPEC" not in prompt
    assert "最多输出 8 个" in prompt


def test_audit_image_with_chat_light_routes_b_design_to_matched_sections(tmp_path):
    image_path = tmp_path / "screen.png"
    Image.new("RGB", (2, 2), color=(107, 54, 250)).save(image_path)
    payload = _valid_payload()
    applicability = {
        "screen_context": "上传文件页面",
        "applicability": "weak",
        "matched_components": [
            {
                "component_id": "data-collection",
                "component_name": "数据收集",
                "confidence": 0.55,
                "applicability": "weak",
                "evidence": "截图中出现上传文件区域。",
            }
        ],
        "reason": "命中数据收集候选组件。",
        "cannot_verify": [],
    }
    spec_text = """# B-design Agent 组件规范

## 通用审核原则
只能依据 B-design PDF 内容。

## 数据收集
数据收集组件必须清晰展示上传、收集进度和停止状态。

## 任务节点
任务节点组件必须展示一级节点和二级节点。
"""

    class FakeCompletions:
        def __init__(self):
            self.calls = []

        def create(self, **kwargs):
            self.calls.append(kwargs)
            output = applicability if len(self.calls) == 1 else payload

            class Message:
                content = json.dumps(output, ensure_ascii=False)

            class Choice:
                message = Message()

            class Response:
                choices = [Choice()]

            return Response()

    class FakeChat:
        def __init__(self):
            self.completions = FakeCompletions()

    class FakeClient:
        def __init__(self):
            self.chat = FakeChat()

    client = FakeClient()

    result = audit_image_with_chat_light(
        client,
        "jd-model",
        image_path,
        spec_text,
        audit_spec_label="京东 B 端设计规范（B-design Agent 组件规范）",
    )

    calls = client.chat.completions.calls
    routing_prompt = calls[0]["messages"][0]["content"][0]["text"]
    audit_prompt = calls[1]["messages"][0]["content"][0]["text"]
    assert calls[0]["max_tokens"] == 4096
    assert calls[1]["max_tokens"] == 8192
    assert "适用性识别" in routing_prompt
    assert "数据收集组件必须清晰展示上传、收集进度和停止状态" in audit_prompt
    assert "任务节点组件必须展示一级节点和二级节点" not in audit_prompt
    assert "不要输出通用 B 端界面风险" in audit_prompt
    assert result["prompt_version"] == B_DESIGN_PROMPT_VERSION
    assert result["schema_version"] == B_DESIGN_SCHEMA_VERSION
    assert result["loaded_spec_sections"] == ["通用审核原则", "数据收集"]
    assert result["b_design_applicability"]["selected_component_ids"] == ["data-collection"]


def test_audit_image_with_chat_light_routes_b_design_extension_rules(tmp_path):
    image_path = tmp_path / "screen.png"
    Image.new("RGB", (2, 2), color=(107, 54, 250)).save(image_path)
    payload = _valid_payload()
    applicability = {
        "screen_context": "质检看板",
        "applicability": "strong",
        "matched_components": [
            {
                "component_id": "quality-dashboard",
                "component_name": "质检/诊断/风险看板",
                "confidence": 0.8,
                "applicability": "strong",
                "evidence": "截图中出现诊断卡片和风险列表。",
            }
        ],
        "reason": "命中 alpha 案例沉淀场景。",
        "cannot_verify": [],
    }
    spec_text = """# B-design Agent 组件规范

## 通用审核原则
只能依据 B-design 规则来源。

## 数据收集
数据收集组件必须清晰展示上传、收集进度和停止状态。

## 扩展审核规则
alpha 案例沉淀规则要求：非 AI 功能不要使用紫色，禁用无依据 emoji。
"""

    class FakeCompletions:
        def __init__(self):
            self.calls = []

        def create(self, **kwargs):
            self.calls.append(kwargs)
            output = applicability if len(self.calls) == 1 else payload

            class Message:
                content = json.dumps(output, ensure_ascii=False)

            class Choice:
                message = Message()

            class Response:
                choices = [Choice()]

            return Response()

    class FakeChat:
        def __init__(self):
            self.completions = FakeCompletions()

    class FakeClient:
        def __init__(self):
            self.chat = FakeChat()

    client = FakeClient()

    result = audit_image_with_chat_light(
        client,
        "jd-model",
        image_path,
        spec_text,
        audit_spec_label="京东 B 端设计规范（B-design Agent 组件规范）",
    )

    audit_prompt = client.chat.completions.calls[1]["messages"][0]["content"][0]["text"]
    assert "alpha 案例沉淀规则要求" in audit_prompt
    assert "数据收集组件必须清晰展示" not in audit_prompt
    assert result["loaded_spec_sections"] == ["通用审核原则", "扩展审核规则"]
    assert result["loaded_spec_components"] == ["质检/诊断/风险看板"]
    assert result["b_design_applicability"]["selected_component_ids"] == ["quality-dashboard"]
    assert result["b_design_applicability"]["matched_components"][0]["source_type"] == "alpha_case"


def test_audit_image_with_chat_light_returns_not_applicable_for_unmatched_b_design(tmp_path):
    image_path = tmp_path / "screen.png"
    Image.new("RGB", (2, 2), color=(107, 54, 250)).save(image_path)
    applicability = {
        "screen_context": "普通表单页面",
        "applicability": "none",
        "matched_components": [],
        "reason": "未出现 B-design 覆盖组件或扩展规则场景。",
        "cannot_verify": [],
    }

    class FakeCompletions:
        def __init__(self):
            self.calls = []

        def create(self, **kwargs):
            self.calls.append(kwargs)

            class Message:
                content = json.dumps(applicability, ensure_ascii=False)

            class Choice:
                message = Message()

            class Response:
                choices = [Choice()]

            return Response()

    class FakeChat:
        def __init__(self):
            self.completions = FakeCompletions()

    class FakeClient:
        def __init__(self):
            self.chat = FakeChat()

    client = FakeClient()

    result = audit_image_with_chat_light(
        client,
        "jd-model",
        image_path,
        "SHOULD NOT BE LOADED",
        audit_spec_label="京东 B 端设计规范（B-design Agent 组件规范）",
    )

    assert len(client.chat.completions.calls) == 1
    assert result["issues"] == []
    assert result["loaded_spec_sections"] == []
    assert result["overall_conclusion"] == "未命中 B-design 规范覆盖范围；本次不输出规范违规问题。"
    assert "通用" not in result["overall_conclusion"]


def test_audit_image_with_kimi_light_uses_kimi_compact_prompt_and_budget(tmp_path):
    image_path = tmp_path / "screen.png"
    Image.new("RGB", (2, 2), color=(107, 54, 250)).save(image_path)
    payload = _valid_payload()

    class FakeCompletions:
        def __init__(self):
            self.kwargs = None

        def create(self, **kwargs):
            self.kwargs = kwargs

            class Message:
                content = json.dumps(payload, ensure_ascii=False)

            class Choice:
                message = Message()

            class Response:
                choices = [Choice()]

            return Response()

    class FakeChat:
        def __init__(self):
            self.completions = FakeCompletions()

    class FakeClient:
        def __init__(self):
            self.chat = FakeChat()

    client = FakeClient()

    result = audit_image_with_kimi_light(client, "Kimi-K2.6", image_path, "VERY LONG SPEC")

    assert {key: result[key] for key in payload} == payload
    kwargs = client.chat.completions.kwargs
    prompt = kwargs["messages"][0]["content"][0]["text"]
    assert kwargs["max_tokens"] == 16384
    assert "禁止输出思考过程" in prompt
    assert "最多输出 5 个" in prompt
    assert "VERY LONG SPEC" not in prompt


def test_audit_image_with_chat_rejects_empty_message_content(tmp_path):
    image_path = tmp_path / "screen.png"
    Image.new("RGB", (2, 2), color=(107, 54, 250)).save(image_path)

    class FakeCompletions:
        def create(self, **kwargs):
            class Message:
                content = None
                reasoning_content = "model spent output budget on reasoning"

            class Choice:
                message = Message()
                finish_reason = "length"

            class Response:
                choices = [Choice()]

            return Response()

    class FakeChat:
        def __init__(self):
            self.completions = FakeCompletions()

    class FakeClient:
        def __init__(self):
            self.chat = FakeChat()

    try:
        audit_image_with_chat(FakeClient(), "jd-model", image_path, "SPEC")
    except AuditModelError as exc:
        message = str(exc)
        assert "没有返回可解析的 JSON 内容" in message
        assert "finish_reason=length" in message
    else:
        raise AssertionError("empty chat content should fail with AuditModelError")


def test_b_design_applicability_failure_includes_finish_reason(tmp_path):
    image_path = tmp_path / "screen.png"
    Image.new("RGB", (2, 2), color=(107, 54, 250)).save(image_path)

    class FakeCompletions:
        def create(self, **kwargs):
            class Message:
                content = None

            class Choice:
                message = Message()
                finish_reason = "length"

            class Response:
                choices = [Choice()]

            return Response()

    class FakeChat:
        def __init__(self):
            self.completions = FakeCompletions()

    class FakeClient:
        def __init__(self):
            self.chat = FakeChat()

    try:
        audit_image_with_chat_light(
            FakeClient(),
            "Kimi-K2.6",
            image_path,
            "SPEC",
            audit_spec_label="京东 B 端设计规范（B-design Agent 组件规范）",
        )
    except AuditModelError as exc:
        message = str(exc)
        assert "B-design 适用性识别没有返回 JSON 内容" in message
        assert "finish_reason=length" in message
    else:
        raise AssertionError("empty applicability content should include finish_reason")
