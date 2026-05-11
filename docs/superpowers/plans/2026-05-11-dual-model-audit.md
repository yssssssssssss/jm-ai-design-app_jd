# Dual Model Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a JDCloud dual-model audit mode that runs `GPT-5.5` and `Kimi-K2.6`, merges their findings, and shows agreement, single-model findings, conflicts, and model failures in the report.

**Architecture:** Keep single-model audit behavior intact. Add a small `app/audit_merge.py` module for local deterministic merging, extend `Settings` with an explicit `AUDIT_MODE`, and make `task_runner.py` choose between the current single-model path and a new dual-model path. `report_renderer.py` reads optional `model_comparison` data and renders it without changing the existing report contract.

**Tech Stack:** Python 3.12, FastAPI app code, SQLite-backed task metadata, OpenAI-compatible JDCloud chat completions, pytest.

---

## File Structure

- Modify `app/config.py`: add `AUDIT_MODE`, dual model list parsing, and validation.
- Create `app/audit_merge.py`: deterministic merge helpers with no network or filesystem access.
- Modify `app/task_runner.py`: add dual-model auditor construction, artifact naming, failure degradation, and existing screenshot pipeline compatibility.
- Modify `app/report_renderer.py`: render optional model comparison sections.
- Modify `.env`: set `AUDIT_MODE=dual` and `JDCLOUD_OPENAI_AUDIT_MODELS=GPT-5.5,Kimi-K2.6` after tests pass.
- Add `tests/test_audit_merge.py`: focused unit tests for merging.
- Modify `tests/test_config_db.py`: cover config defaults and validation.
- Modify `tests/test_task_runner.py`: cover dual artifacts, single-mode compatibility, and single-model failure degradation.
- Modify `tests/test_report_renderer.py`: cover model comparison HTML.

Use this pytest command in this environment:

```bash
PYTHONPATH=/private/tmp/pytest-no-readline:. .venv/bin/python -m pytest tests/test_config_db.py tests/test_audit_merge.py tests/test_task_runner.py tests/test_report_renderer.py -q
```

Expected final result: all selected tests pass.

---

### Task 1: Add Audit Mode Configuration

**Files:**
- Modify: `app/config.py`
- Modify: `tests/test_config_db.py`

- [ ] **Step 1: Write failing config tests**

Append these tests to `tests/test_config_db.py`:

```python
def test_settings_defaults_to_single_audit_mode(tmp_path, monkeypatch):
    _set_required_env(monkeypatch, tmp_path)

    settings = load_settings()

    assert settings.audit_mode == "single"
    assert settings.jdcloud_openai_audit_models == []


def test_settings_loads_dual_jdcloud_models(tmp_path, monkeypatch):
    _set_required_env(monkeypatch, tmp_path)
    monkeypatch.setenv("AUDIT_MODEL_PROVIDER", "jdcloud")
    monkeypatch.setenv("AUDIT_MODE", "dual")
    monkeypatch.setenv("JDCLOUD_OPENAI_API_KEY", "jd-key")
    monkeypatch.setenv("JDCLOUD_OPENAI_BASE_URL", "https://modelservice.jdcloud.com/v1/")
    monkeypatch.setenv("JDCLOUD_OPENAI_AUDIT_MODEL", "GPT-5.5")
    monkeypatch.setenv("JDCLOUD_OPENAI_AUDIT_MODELS", "GPT-5.5, Kimi-K2.6")

    settings = load_settings()

    assert settings.audit_mode == "dual"
    assert settings.jdcloud_openai_audit_models == ["GPT-5.5", "Kimi-K2.6"]


def test_settings_rejects_dual_mode_for_non_jdcloud_provider(tmp_path, monkeypatch):
    _set_required_env(monkeypatch, tmp_path)
    monkeypatch.setenv("AUDIT_MODE", "dual")
    monkeypatch.setenv("JDCLOUD_OPENAI_AUDIT_MODELS", "GPT-5.5,Kimi-K2.6")

    try:
        load_settings()
    except RuntimeError as exc:
        assert "AUDIT_MODE=dual requires AUDIT_MODEL_PROVIDER=jdcloud" in str(exc)
    else:
        raise AssertionError("dual mode should require jdcloud provider")


def test_settings_rejects_dual_mode_without_exactly_two_models(tmp_path, monkeypatch):
    _set_required_env(monkeypatch, tmp_path)
    monkeypatch.setenv("AUDIT_MODEL_PROVIDER", "jdcloud")
    monkeypatch.setenv("AUDIT_MODE", "dual")
    monkeypatch.setenv("JDCLOUD_OPENAI_API_KEY", "jd-key")
    monkeypatch.setenv("JDCLOUD_OPENAI_BASE_URL", "https://modelservice.jdcloud.com/v1/")
    monkeypatch.setenv("JDCLOUD_OPENAI_AUDIT_MODEL", "GPT-5.5")
    monkeypatch.setenv("JDCLOUD_OPENAI_AUDIT_MODELS", "GPT-5.5")

    try:
        load_settings()
    except RuntimeError as exc:
        assert "JDCLOUD_OPENAI_AUDIT_MODELS" in str(exc)
    else:
        raise AssertionError("dual mode should require exactly two models")
```

Also add `"AUDIT_MODE"` and `"JDCLOUD_OPENAI_AUDIT_MODELS"` to `OPTIONAL_ENV`.

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
PYTHONPATH=/private/tmp/pytest-no-readline:. .venv/bin/python -m pytest tests/test_config_db.py -q
```

Expected: fail because `Settings.audit_mode` and `Settings.jdcloud_openai_audit_models` do not exist.

- [ ] **Step 3: Implement config fields and parsing**

In `app/config.py`, add constants near the existing provider constants:

```python
AUDIT_MODES = {"single", "dual"}
```

Add fields to `Settings`:

```python
    audit_mode: str = "single"
    jdcloud_openai_audit_models: list[str] | None = None
```

Add a property:

```python
    @property
    def audit_models(self) -> list[str]:
        if self.audit_mode == "dual":
            return list(self.jdcloud_openai_audit_models or [])
        return [self.audit_model]
```

Add helpers near `_load_audit_model_provider`:

```python
def _load_audit_mode() -> str:
    mode = (os.getenv("AUDIT_MODE") or "single").strip().lower()
    if mode not in AUDIT_MODES:
        raise RuntimeError("Invalid AUDIT_MODE value. Expected single or dual")
    return mode


def _load_jdcloud_audit_models(provider: str, mode: str) -> list[str]:
    raw = (os.getenv("JDCLOUD_OPENAI_AUDIT_MODELS") or "").strip()
    models = [item.strip() for item in raw.split(",") if item.strip()]
    if mode == "single":
        return models
    if provider != "jdcloud":
        raise RuntimeError("AUDIT_MODE=dual requires AUDIT_MODEL_PROVIDER=jdcloud")
    if len(models) != 2:
        raise RuntimeError(
            "Invalid JDCLOUD_OPENAI_AUDIT_MODELS value. "
            "AUDIT_MODE=dual requires exactly two comma-separated models"
        )
    return models
```

In `load_settings()`, after loading `audit_model_provider`, load `audit_mode` and `jdcloud_audit_models`, then pass them into `Settings`:

```python
    audit_model_provider = _load_audit_model_provider()
    audit_mode = _load_audit_mode()
    jdcloud_values = _load_jdcloud_required_values(audit_model_provider)
    jdcloud_audit_models = _load_jdcloud_audit_models(
        audit_model_provider,
        audit_mode,
    )
```

Add constructor arguments:

```python
        audit_mode=audit_mode,
        jdcloud_openai_audit_models=jdcloud_audit_models,
```

- [ ] **Step 4: Run config tests**

Run:

```bash
PYTHONPATH=/private/tmp/pytest-no-readline:. .venv/bin/python -m pytest tests/test_config_db.py -q
```

Expected: pass.

---

### Task 2: Add Deterministic Audit Merge Module

**Files:**
- Create: `app/audit_merge.py`
- Create: `tests/test_audit_merge.py`

- [ ] **Step 1: Write failing merge tests**

Create `tests/test_audit_merge.py`:

```python
from app.audit_merge import merge_audits, merge_audit_attempts


def _audit(issue):
    return {
        "screen_context": "页面",
        "overall_conclusion": "存在问题",
        "major_issues": ["颜色问题"],
        "passes": ["标题层级清晰"],
        "issues": [issue] if issue else [],
        "sample_points": [],
        "regions": [],
        "distances": [],
        "checklist": [{"item": "AI 主色", "status": "不通过", "evidence": "偏色"}],
        "cannot_verify": [],
    }


def _issue(issue_id, category, location, bbox, severity="中"):
    return {
        "id": issue_id,
        "category": category,
        "severity": severity,
        "location": location,
        "current_observation": f"{location} 使用非 JM AI 色彩",
        "spec_expectation": "应使用 JM AI 紫色 token",
        "recommendation": "改为 #6B36FA",
        "confidence": 0.8,
        "bbox": bbox,
    }


def test_merge_audits_combines_overlapping_issues_as_agreement():
    gpt = _audit(_issue("g1", "色彩", "邀好友赚套餐", [100, 10, 120, 40], "中"))
    kimi = _audit(_issue("k1", "颜色", "邀好友赚套餐按钮", [110, 12, 118, 38], "高"))

    merged = merge_audits(
        [{"model": "GPT-5.5", "audit": gpt}, {"model": "Kimi-K2.6", "audit": kimi}]
    )

    assert len(merged["issues"]) == 1
    assert merged["issues"][0]["agreement"] == "both"
    assert merged["issues"][0]["source_models"] == ["GPT-5.5", "Kimi-K2.6"]
    assert merged["issues"][0]["severity"] == "高"
    assert len(merged["model_comparison"]["agreed_issues"]) == 1


def test_merge_audits_keeps_single_model_findings():
    gpt = _audit(_issue("g1", "色彩", "邀好友赚套餐", [100, 10, 120, 40]))
    kimi = _audit(_issue("k1", "图标", "右下角彩色图标", [500, 400, 40, 40]))

    merged = merge_audits(
        [{"model": "GPT-5.5", "audit": gpt}, {"model": "Kimi-K2.6", "audit": kimi}]
    )

    assert [issue["agreement"] for issue in merged["issues"]] == ["gpt_only", "kimi_only"]
    assert len(merged["model_comparison"]["gpt_only_issues"]) == 1
    assert len(merged["model_comparison"]["kimi_only_issues"]) == 1


def test_merge_audits_uses_non_null_bbox_when_only_one_model_has_bbox():
    gpt = _audit(_issue("g1", "色彩", "续费套餐", None))
    kimi = _audit(_issue("k1", "色彩", "续费套餐", [200, 20, 80, 32]))

    merged = merge_audits(
        [{"model": "GPT-5.5", "audit": gpt}, {"model": "Kimi-K2.6", "audit": kimi}]
    )

    assert merged["issues"][0]["bbox"] == [200, 20, 80, 32]
    assert merged["issues"][0]["agreement"] == "both"


def test_merge_audit_attempts_degrades_when_one_model_fails():
    gpt = _audit(_issue("g1", "色彩", "邀好友赚套餐", [100, 10, 120, 40]))

    merged = merge_audit_attempts(
        [
            {"model": "GPT-5.5", "audit": gpt, "error": None},
            {"model": "Kimi-K2.6", "audit": None, "error": "timeout"},
        ]
    )

    assert merged["issues"][0]["agreement"] == "gpt_only"
    assert merged["model_comparison"]["model_failures"] == [
        {"model": "Kimi-K2.6", "error": "timeout"}
    ]
    assert "单模型降级" in merged["overall_conclusion"]


def test_merge_audit_attempts_fails_when_all_models_fail():
    try:
        merge_audit_attempts(
            [
                {"model": "GPT-5.5", "audit": None, "error": "bad request"},
                {"model": "Kimi-K2.6", "audit": None, "error": "timeout"},
            ]
        )
    except RuntimeError as exc:
        assert "全部模型审核失败" in str(exc)
    else:
        raise AssertionError("all model failures should raise")
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
PYTHONPATH=/private/tmp/pytest-no-readline:. .venv/bin/python -m pytest tests/test_audit_merge.py -q
```

Expected: fail because `app.audit_merge` does not exist.

- [ ] **Step 3: Implement `app/audit_merge.py`**

Create `app/audit_merge.py`:

```python
from __future__ import annotations

import re
from copy import deepcopy
from typing import Any


REQUIRED_ARRAY_KEYS = [
    "major_issues",
    "passes",
    "issues",
    "sample_points",
    "regions",
    "distances",
    "checklist",
    "cannot_verify",
]
SEVERITY_RANK = {"低": 1, "中": 2, "高": 3}


def merge_audit_attempts(attempts: list[dict[str, Any]]) -> dict[str, Any]:
    successes = [
        {"model": item["model"], "audit": item["audit"]}
        for item in attempts
        if item.get("audit") is not None
    ]
    failures = [
        {"model": item["model"], "error": str(item.get("error") or "")[:500]}
        for item in attempts
        if item.get("audit") is None
    ]
    if not successes:
        raise RuntimeError("全部模型审核失败")

    merged = merge_audits(successes)
    comparison = merged.setdefault("model_comparison", _empty_comparison([]))
    comparison["model_failures"] = failures
    if failures:
        merged["overall_conclusion"] = "单模型降级审核：" + str(
            merged.get("overall_conclusion") or "已完成审核"
        )
    return merged


def merge_audits(model_audits: list[dict[str, Any]]) -> dict[str, Any]:
    models = [str(item["model"]) for item in model_audits]
    base = _base_payload(model_audits)
    merged_issues: list[dict[str, Any]] = []

    for item in model_audits:
        model = str(item["model"])
        for issue in item["audit"].get("issues") or []:
            candidate = deepcopy(issue)
            existing = _find_matching_issue(merged_issues, candidate)
            if existing is None:
                candidate["source_models"] = [model]
                candidate["agreement"] = _agreement_for_models([model], models)
                merged_issues.append(candidate)
            else:
                _merge_issue(existing, candidate, model, models)

    for index, issue in enumerate(merged_issues, start=1):
        issue["id"] = f"问题-{index:03d}"
        issue["agreement"] = _agreement_for_models(issue["source_models"], models)

    comparison = _build_comparison(models, merged_issues)
    base["issues"] = merged_issues
    base["major_issues"] = [
        issue.get("current_observation") or issue.get("location") or issue["id"]
        for issue in merged_issues
    ]
    base["overall_conclusion"] = _merged_conclusion(merged_issues, comparison)
    base["model_comparison"] = comparison
    return base


def _base_payload(model_audits: list[dict[str, Any]]) -> dict[str, Any]:
    first = deepcopy(model_audits[0]["audit"])
    for key in REQUIRED_ARRAY_KEYS:
        first[key] = list(first.get(key) or [])
    first["screen_context"] = first.get("screen_context") or "模型未返回页面识别"
    first["overall_conclusion"] = first.get("overall_conclusion") or "已完成审核"
    return first


def _empty_comparison(models: list[str]) -> dict[str, Any]:
    return {
        "models": models,
        "agreed_issues": [],
        "gpt_only_issues": [],
        "kimi_only_issues": [],
        "conflicts": [],
        "model_failures": [],
    }


def _build_comparison(models: list[str], issues: list[dict[str, Any]]) -> dict[str, Any]:
    comparison = _empty_comparison(models)
    for issue in issues:
        bucket = {
            "both": "agreed_issues",
            "gpt_only": "gpt_only_issues",
            "kimi_only": "kimi_only_issues",
        }.get(issue.get("agreement"))
        if bucket:
            comparison[bucket].append(issue)
    return comparison


def _merged_conclusion(
    issues: list[dict[str, Any]],
    comparison: dict[str, Any],
) -> str:
    if not issues:
        return "双模型审核未发现明确 JM AI 设计规范问题。"
    return (
        "双模型审核发现 "
        f"{len(issues)} 个问题，其中双方一致 {len(comparison['agreed_issues'])} 个，"
        f"仅 GPT-5.5 发现 {len(comparison['gpt_only_issues'])} 个，"
        f"仅 Kimi-K2.6 发现 {len(comparison['kimi_only_issues'])} 个。"
    )


def _find_matching_issue(
    existing_issues: list[dict[str, Any]],
    candidate: dict[str, Any],
) -> dict[str, Any] | None:
    for issue in existing_issues:
        if _bbox_iou(issue.get("bbox"), candidate.get("bbox")) >= 0.2:
            return issue
        if _text_similarity(issue.get("location"), candidate.get("location")) >= 0.5:
            return issue
    return None


def _merge_issue(
    target: dict[str, Any],
    candidate: dict[str, Any],
    model: str,
    models: list[str],
) -> None:
    if model not in target["source_models"]:
        target["source_models"].append(model)
    target["source_models"].sort(key=models.index)
    if _severity_rank(candidate.get("severity")) > _severity_rank(target.get("severity")):
        target["severity"] = candidate.get("severity")
    for key in ["current_observation", "spec_expectation", "recommendation", "location"]:
        target[key] = _better_text(target.get(key), candidate.get(key))
    target["bbox"] = _better_bbox(target.get("bbox"), candidate.get("bbox"))
    if _confidence(candidate.get("confidence")) > _confidence(target.get("confidence")):
        target["confidence"] = candidate.get("confidence")


def _agreement_for_models(source_models: list[str], models: list[str]) -> str:
    if len(set(source_models)) >= 2:
        return "both"
    source = source_models[0] if source_models else ""
    if source == models[0]:
        return "gpt_only"
    return "kimi_only"


def _severity_rank(value: Any) -> int:
    return SEVERITY_RANK.get(str(value or ""), 0)


def _better_text(left: Any, right: Any) -> str:
    left_text = str(left or "")
    right_text = str(right or "")
    if len(right_text) > len(left_text):
        return right_text
    return left_text


def _confidence(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _better_bbox(left: Any, right: Any) -> Any:
    if _valid_bbox(left) and not _valid_bbox(right):
        return left
    if _valid_bbox(right) and not _valid_bbox(left):
        return right
    if _valid_bbox(left) and _valid_bbox(right):
        left_area = float(left[2]) * float(left[3])
        right_area = float(right[2]) * float(right[3])
        return left if left_area <= right_area else right
    return None


def _valid_bbox(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 4
        and all(isinstance(item, int | float) for item in value)
        and value[2] > 0
        and value[3] > 0
    )


def _bbox_iou(left: Any, right: Any) -> float:
    if not _valid_bbox(left) or not _valid_bbox(right):
        return 0.0
    lx1, ly1, lw, lh = [float(item) for item in left]
    rx1, ry1, rw, rh = [float(item) for item in right]
    lx2, ly2 = lx1 + lw, ly1 + lh
    rx2, ry2 = rx1 + rw, ry1 + rh
    ix1, iy1 = max(lx1, rx1), max(ly1, ry1)
    ix2, iy2 = min(lx2, rx2), min(ly2, ry2)
    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0
    intersection = (ix2 - ix1) * (iy2 - iy1)
    union = lw * lh + rw * rh - intersection
    return intersection / union if union > 0 else 0.0


def _text_similarity(left: Any, right: Any) -> float:
    left_tokens = _tokens(left)
    right_tokens = _tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    overlap = left_tokens & right_tokens
    return len(overlap) / max(len(left_tokens), len(right_tokens))


def _tokens(value: Any) -> set[str]:
    text = str(value or "").lower()
    return {token for token in re.split(r"[\s,，。；;：:/|()（）]+", text) if token}
```

- [ ] **Step 4: Run merge tests**

Run:

```bash
PYTHONPATH=/private/tmp/pytest-no-readline:. .venv/bin/python -m pytest tests/test_audit_merge.py -q
```

Expected: pass.

---

### Task 3: Add Dual-Mode Task Runner Path

**Files:**
- Modify: `app/task_runner.py`
- Modify: `tests/test_task_runner.py`

- [ ] **Step 1: Write failing task runner tests**

Append to `tests/test_task_runner.py`:

```python
def test_run_task_dual_mode_writes_model_artifacts_and_merged_audit(monkeypatch, tmp_path):
    settings = Settings(
        openai_api_key="key",
        app_secret_key="secret",
        register_invite_code="invite",
        initial_admin_username="admin",
        initial_admin_password="password123",
        data_dir=tmp_path,
        audit_model_provider="jdcloud",
        audit_mode="dual",
        jdcloud_openai_api_key="jd-key",
        jdcloud_openai_base_url="https://modelservice.jdcloud.com/v1/",
        jdcloud_openai_audit_model="GPT-5.5",
        jdcloud_openai_audit_models=["GPT-5.5", "Kimi-K2.6"],
    )
    conn = connect(settings.db_path)
    init_db(conn)
    user = create_user(conn, "alice", hash_password("secret123"), "user")
    task = create_task(conn, user.id, "Dual Audit", 1)
    dirs = ensure_task_dirs(settings, task.id)
    image_path = dirs.originals / "image-001.png"
    Image.new("RGB", (20, 20), color=(107, 54, 250)).save(image_path)
    add_task_image(conn, task.id, "image-001.png", relative_to_data(settings, image_path), 0)

    def fake_audit(client, model, image_path, spec_text, reasoning_effort=None, declared_screen_size=None):
        return {
            "screen_context": "测试页",
            "overall_conclusion": "存在问题",
            "major_issues": [],
            "passes": [],
            "issues": [
                {
                    "id": model,
                    "category": "色彩",
                    "severity": "中",
                    "location": "邀好友赚套餐",
                    "current_observation": f"{model} 发现橙色按钮",
                    "spec_expectation": "应使用 JM AI 紫色",
                    "recommendation": "改为 #6B36FA",
                    "confidence": 0.9,
                    "bbox": [2, 2, 10, 8],
                }
            ],
            "sample_points": [],
            "regions": [],
            "distances": [],
            "checklist": [],
            "cannot_verify": [],
        }

    class FakeClient:
        def __init__(self, **kwargs):
            pass

    spec_path = tmp_path / "spec.md"
    spec_path.write_text("spec", encoding="utf-8")
    monkeypatch.setattr(task_runner, "SPEC_PATH", spec_path)
    monkeypatch.setattr(task_runner, "OpenAI", FakeClient)
    monkeypatch.setattr(task_runner, "audit_image_with_chat", fake_audit)

    run_task(settings, task.id)

    artifact_dir = tmp_path / "uploads" / str(task.id) / "artifacts" / "image-001"
    assert (artifact_dir / "audit-gpt-5.5.json").exists()
    assert (artifact_dir / "audit-kimi-k2.6.json").exists()
    assert (artifact_dir / "audit.json").exists()
    assert (artifact_dir / "annotated.png").exists()
    merged = json.loads((artifact_dir / "audit.json").read_text(encoding="utf-8"))
    assert merged["issues"][0]["agreement"] == "both"
    assert merged["model_comparison"]["models"] == ["GPT-5.5", "Kimi-K2.6"]


def test_run_task_dual_mode_succeeds_when_one_model_fails(monkeypatch, tmp_path):
    settings = Settings(
        openai_api_key="key",
        app_secret_key="secret",
        register_invite_code="invite",
        initial_admin_username="admin",
        initial_admin_password="password123",
        data_dir=tmp_path,
        audit_model_provider="jdcloud",
        audit_mode="dual",
        jdcloud_openai_api_key="jd-key",
        jdcloud_openai_base_url="https://modelservice.jdcloud.com/v1/",
        jdcloud_openai_audit_model="GPT-5.5",
        jdcloud_openai_audit_models=["GPT-5.5", "Kimi-K2.6"],
    )
    conn = connect(settings.db_path)
    init_db(conn)
    user = create_user(conn, "alice", hash_password("secret123"), "user")
    task = create_task(conn, user.id, "Dual Audit", 1)
    dirs = ensure_task_dirs(settings, task.id)
    image_path = dirs.originals / "image-001.png"
    Image.new("RGB", (20, 20), color=(107, 54, 250)).save(image_path)
    add_task_image(conn, task.id, "image-001.png", relative_to_data(settings, image_path), 0)

    def fake_audit(client, model, image_path, spec_text, reasoning_effort=None, declared_screen_size=None):
        if model == "Kimi-K2.6":
            raise RuntimeError("timeout")
        return {
            "screen_context": "测试页",
            "overall_conclusion": "存在问题",
            "major_issues": [],
            "passes": [],
            "issues": [
                {
                    "id": "gpt",
                    "category": "色彩",
                    "severity": "中",
                    "location": "邀好友赚套餐",
                    "current_observation": "橙色按钮",
                    "spec_expectation": "应使用 JM AI 紫色",
                    "recommendation": "改为 #6B36FA",
                    "confidence": 0.9,
                    "bbox": [2, 2, 10, 8],
                }
            ],
            "sample_points": [],
            "regions": [],
            "distances": [],
            "checklist": [],
            "cannot_verify": [],
        }

    class FakeClient:
        def __init__(self, **kwargs):
            pass

    spec_path = tmp_path / "spec.md"
    spec_path.write_text("spec", encoding="utf-8")
    monkeypatch.setattr(task_runner, "SPEC_PATH", spec_path)
    monkeypatch.setattr(task_runner, "OpenAI", FakeClient)
    monkeypatch.setattr(task_runner, "audit_image_with_chat", fake_audit)

    run_task(settings, task.id)

    refreshed = get_task_by_id(conn, task.id)
    artifact_dir = tmp_path / "uploads" / str(task.id) / "artifacts" / "image-001"
    merged = json.loads((artifact_dir / "audit.json").read_text(encoding="utf-8"))
    assert refreshed.status == "succeeded"
    assert merged["issues"][0]["agreement"] == "gpt_only"
    assert merged["model_comparison"]["model_failures"] == [
        {"model": "Kimi-K2.6", "error": "timeout"}
    ]
```

Add `import json` at the top of `tests/test_task_runner.py`.

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
PYTHONPATH=/private/tmp/pytest-no-readline:. .venv/bin/python -m pytest tests/test_task_runner.py -q
```

Expected: fail because dual mode is not implemented in `task_runner.py`.

- [ ] **Step 3: Implement dual auditor construction**

In `app/task_runner.py`, add import:

```python
from app.audit_merge import merge_audit_attempts
```

Add helper below `_default_auditor`:

```python
def _dual_auditor(
    settings: Settings,
    declared_screen_size: tuple[int, int] | None = None,
) -> Callable[[Path, Path], dict[str, Any]]:
    spec_text = SPEC_PATH.read_text(encoding="utf-8")
    client = OpenAI(
        api_key=settings.audit_api_key,
        base_url=settings.audit_base_url,
        timeout=settings.audit_timeout_seconds,
        max_retries=0,
    )

    def audit(image_path: Path, artifact_dir: Path) -> dict[str, Any]:
        attempts: list[dict[str, Any]] = []
        for model in settings.audit_models:
            artifact_name = f"audit-{_artifact_model_slug(model)}.json"
            try:
                result = audit_image_with_chat(
                    client,
                    model,
                    image_path,
                    spec_text,
                    reasoning_effort=settings.audit_reasoning_effort,
                    declared_screen_size=declared_screen_size,
                )
                write_json(artifact_dir / artifact_name, result)
                attempts.append({"model": model, "audit": result, "error": None})
            except Exception as exc:  # noqa: BLE001 - one model may fail while the other succeeds.
                attempts.append({"model": model, "audit": None, "error": _short_error(exc)})
        return merge_audit_attempts(attempts)

    return audit
```

Add slug helper near `_stem`:

```python
def _artifact_model_slug(model: str) -> str:
    return (
        model.strip()
        .lower()
        .replace("/", "-")
        .replace("\\", "-")
        .replace(" ", "-")
    )
```

- [ ] **Step 4: Route `run_task` to dual mode**

In `run_task`, replace:

```python
        auditor = auditor or _default_auditor(settings, declared_screen_size)
```

with:

```python
        dual_auditor = None
        if auditor is None and settings.audit_mode == "dual":
            dual_auditor = _dual_auditor(settings, declared_screen_size)
        else:
            auditor = auditor or _default_auditor(settings, declared_screen_size)
```

Inside the image loop, replace:

```python
                audit = auditor(image_path)
```

with:

```python
                if dual_auditor is not None:
                    audit = dual_auditor(image_path, image_artifacts)
                else:
                    audit = auditor(image_path)
```

Keep the later `write_json(audit_path, audit)` unchanged so `audit.json` remains the merged or single-model result.

- [ ] **Step 5: Run task runner tests**

Run:

```bash
PYTHONPATH=/private/tmp/pytest-no-readline:. .venv/bin/python -m pytest tests/test_task_runner.py -q
```

Expected: pass.

---

### Task 4: Render Model Comparison in HTML

**Files:**
- Modify: `app/report_renderer.py`
- Modify: `tests/test_report_renderer.py`

- [ ] **Step 1: Write failing renderer test**

Append to `tests/test_report_renderer.py`:

```python
def test_render_report_html_includes_model_comparison_when_present():
    audit = _audit_payload()
    audit["model_comparison"] = {
        "models": ["GPT-5.5", "Kimi-K2.6"],
        "agreed_issues": [
            {"id": "问题-001", "location": "邀好友赚套餐", "current_observation": "橙色按钮"}
        ],
        "gpt_only_issues": [
            {"id": "问题-002", "location": "生成PPT", "current_observation": "橙色图标"}
        ],
        "kimi_only_issues": [
            {"id": "问题-003", "location": "续费套餐", "current_observation": "绿色标签"}
        ],
        "conflicts": [
            {"location": "头像徽章", "summary": "一个模型认为违规，另一个模型未提及"}
        ],
        "model_failures": [{"model": "Kimi-K2.6", "error": "timeout"}],
    }

    html = render_report_html(
        task={"title": "审核", "summary": "完成"},
        image_results=[{"filename": "image-001.png", "audit": audit, "artifacts": {}}],
    )

    assert "模型对比" in html
    assert "双方一致的问题" in html
    assert "仅 GPT-5.5 发现的问题" in html
    assert "仅 Kimi-K2.6 发现的问题" in html
    assert "需人工复核" in html
    assert "模型失败信息" in html
    assert "timeout" in html
```

- [ ] **Step 2: Run renderer tests to verify failure**

Run:

```bash
PYTHONPATH=/private/tmp/pytest-no-readline:. .venv/bin/python -m pytest tests/test_report_renderer.py -q
```

Expected: fail because model comparison is not rendered.

- [ ] **Step 3: Add comparison renderer**

In `app/report_renderer.py`, add helpers after `_issues_table`:

```python
def _comparison_issue_list(items: list[dict[str, Any]]) -> str:
    if not items:
        return '<p class="meta">无</p>'
    rows = []
    for item in items:
        label = item.get("id") or item.get("location") or "问题"
        detail = item.get("current_observation") or item.get("summary") or item.get("recommendation") or ""
        rows.append(f"<li>{_text(label)}：{_text(detail)}</li>")
    return "<ul>" + "".join(rows) + "</ul>"


def _model_failures(items: list[dict[str, Any]]) -> str:
    if not items:
        return '<p class="meta">无</p>'
    return "<ul>" + "".join(
        f"<li>{_text(item.get('model'))}：{_text(item.get('error'))}</li>"
        for item in items
    ) + "</ul>"


def _model_comparison(comparison: dict[str, Any] | None) -> str:
    if not comparison:
        return ""
    models = "、".join(str(model) for model in comparison.get("models") or [])
    return f"""
      <h3>模型对比</h3>
      <p class="meta">参与模型：{_text(models)}</p>
      <h4>双方一致的问题</h4>
      {_comparison_issue_list(comparison.get("agreed_issues") or [])}
      <h4>仅 GPT-5.5 发现的问题</h4>
      {_comparison_issue_list(comparison.get("gpt_only_issues") or [])}
      <h4>仅 Kimi-K2.6 发现的问题</h4>
      {_comparison_issue_list(comparison.get("kimi_only_issues") or [])}
      <h4>需人工复核</h4>
      {_comparison_issue_list(comparison.get("conflicts") or [])}
      <h4>模型失败信息</h4>
      {_model_failures(comparison.get("model_failures") or [])}
    """
```

In `_image_section`, insert after the core conclusion block:

```python
      {_model_comparison(audit.get("model_comparison"))}
```

Add compact CSS for `h4` near existing heading styles:

```python
    h4 { margin: 16px 0 6px; font-size: 14px; line-height: 22px; font-weight: 600; }
```

- [ ] **Step 4: Run renderer tests**

Run:

```bash
PYTHONPATH=/private/tmp/pytest-no-readline:. .venv/bin/python -m pytest tests/test_report_renderer.py -q
```

Expected: pass.

---

### Task 5: Update Runtime Env for Dual Mode

**Files:**
- Modify: `.env`

- [ ] **Step 1: Update `.env`**

Edit `.env` so it contains:

```env
AUDIT_MODEL_PROVIDER=jdcloud
AUDIT_MODE=dual
JDCLOUD_OPENAI_AUDIT_MODEL=GPT-5.5
JDCLOUD_OPENAI_AUDIT_MODELS=GPT-5.5,Kimi-K2.6
```

Keep existing keys and URLs unchanged. Do not expose or rewrite secrets.

- [ ] **Step 2: Verify loaded settings**

Run:

```bash
.venv/bin/python -c "from app.config import load_settings; s=load_settings(); print(s.audit_model_provider, s.audit_mode, s.audit_models)"
```

Expected output contains:

```text
jdcloud dual ['GPT-5.5', 'Kimi-K2.6']
```

---

### Task 6: Full Verification

**Files:**
- No code changes expected.

- [ ] **Step 1: Run focused test suite**

Run:

```bash
PYTHONPATH=/private/tmp/pytest-no-readline:. .venv/bin/python -m pytest tests/test_config_db.py tests/test_audit_merge.py tests/test_task_runner.py tests/test_report_renderer.py -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run existing audit-related tests**

Run:

```bash
PYTHONPATH=/private/tmp/pytest-no-readline:. .venv/bin/python -m pytest tests/test_openai_audit.py tests/test_evidence_tools.py tests/test_task_runner.py tests/test_report_renderer.py -q
```

Expected: all selected tests pass.

- [ ] **Step 3: Optional real dual-model smoke test**

Only run this if network access and JDCloud quota are acceptable. Reuse one existing uploaded real image to create a new task and run `run_task()` with loaded settings.

Expected artifacts under `data/uploads/<new_task_id>/artifacts/image-001/`:

```text
audit-gpt-5.5.json
audit-kimi-k2.6.json
audit.json
issues.json
annotated.png
```

Expected report behavior:

- HTML report includes “模型对比”.
- `audit.json` contains `model_comparison`.
- If one model fails, report still succeeds with `model_failures`.

---

## Self-Review

Spec coverage:

- JDCloud-only dual mode: Task 1 and Task 5.
- Two raw model JSON files and merged JSON: Task 3.
- Deterministic merge with agreement and single-model buckets: Task 2.
- Failure degradation: Task 2 and Task 3.
- Report comparison sections: Task 4.
- Single-mode compatibility: Task 1, Task 3, and focused regression tests.

Placeholder scan:

- No placeholder or deferred-detail steps are present.

Type consistency:

- `Settings.audit_mode`, `Settings.jdcloud_openai_audit_models`, and `Settings.audit_models` are introduced in Task 1 and used in Task 3.
- `merge_audits()` and `merge_audit_attempts()` are introduced in Task 2 and used in Task 3.
- `model_comparison` shape matches the design spec and renderer tests.
