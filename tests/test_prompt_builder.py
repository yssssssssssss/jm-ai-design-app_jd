from app.prompt_builder import (
    PROMPT_VERSION,
    SCHEMA_VERSION,
    build_audit_prompt,
    build_light_audit_prompt,
    prompt_metadata,
)


def test_prompt_metadata_exposes_prompt_and_schema_versions():
    assert prompt_metadata() == {
        "prompt_version": PROMPT_VERSION,
        "schema_version": SCHEMA_VERSION,
    }


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
