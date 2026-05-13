from app.model_errors import classify_model_error, model_failure


def test_classify_model_error_detects_capacity():
    result = classify_model_error("Selected model is at capacity. Please try a different model.")

    assert result["error_type"] == "capacity"
    assert result["retriable"] is True


def test_classify_model_error_detects_invalid_json():
    result = classify_model_error("模型返回的 JSON 无法解析")

    assert result["error_type"] == "invalid_json"
    assert result["retriable"] is False


def test_classify_model_error_detects_image_unsupported():
    result = classify_model_error("该模型不支持图片 JSON 输出")

    assert result["error_type"] == "image_unsupported"
    assert result["retriable"] is False


def test_model_failure_includes_degradation_metadata():
    result = model_failure("Kimi-K2.6", TimeoutError("timeout"))

    assert result == {
        "model": "Kimi-K2.6",
        "error": "timeout",
        "error_type": "timeout",
        "retriable": True,
        "degraded": True,
    }
