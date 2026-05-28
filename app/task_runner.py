from __future__ import annotations

import json
import inspect
import re
from pathlib import Path
from typing import Any, Callable

from openai import OpenAI
from PIL import Image

from app.audit_merge import merge_audit_attempts, merge_primary_with_candidates
from app.config import Settings
from app.db import connect
from app.evidence_tools import (
    build_issues_json_for_image,
    run_annotations,
    run_color_analysis,
    run_measurements,
    write_json,
    write_regions_json,
)
from app.models import TASK_FAILED, TASK_RUNNING, TASK_SUCCEEDED
from app.model_errors import model_failure
from app.openai_audit import (
    audit_image,
    audit_image_with_chat,
    audit_image_with_chat_light,
    audit_image_with_kimi_light,
)
from app.report_renderer import render_report_html
from app.repositories import (
    clear_task_image_artifacts,
    clear_task_result,
    get_task_by_id,
    list_task_images,
    update_task_image_status,
    update_task_status,
)
from app.rule_engine import apply_rule_review
from app.size_context import compute_scale
from app.spec_registry import get_audit_specs
from app.storage import ensure_task_dirs, relative_to_data, resolve_data_path


Auditor = Callable[[Path], dict[str, Any]]
SystemAuditor = Callable[[Path, dict[str, Any] | None], dict[str, Any]]
DualAuditor = Callable[[Path, Path, dict[str, Any] | None], dict[str, Any]]
SPEC_PATH = Path(__file__).resolve().parent.parent / "references" / "jm-ai-design-spec.md"


def _default_auditor(
    settings: Settings,
    declared_screen_size: tuple[int, int] | None = None,
    spec_path: Path | None = None,
    audit_spec_label: str = "JM AI 设计规范",
) -> SystemAuditor:
    spec_text = (spec_path or SPEC_PATH).read_text(encoding="utf-8")
    client = OpenAI(
        api_key=settings.audit_api_key,
        base_url=settings.audit_base_url,
        timeout=settings.audit_timeout_seconds,
        max_retries=0,
    )
    if settings.audit_model_provider == "jdcloud":
        audit = _jdcloud_chat_audit(settings)
    else:
        audit = audit_image

    def run_audit(
        image_path: Path,
        scale_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return _call_audit_model(
            audit,
            client,
            settings.audit_model,
            image_path,
            spec_text,
            audit_spec_label=audit_spec_label,
            reasoning_effort=settings.audit_reasoning_effort,
            declared_screen_size=declared_screen_size,
            scale_context=scale_context,
        )

    return run_audit


def _stem(filename: str) -> str:
    return filename.rsplit(".", 1)[0]


def _artifact_image_dirname(sort_order: int) -> str:
    return f"image-{sort_order + 1:03d}"


def _artifact_dir_for_spec(
    artifacts_root: Path,
    sort_order: int,
    spec_count: int,
    spec_id: str,
) -> Path:
    image_dir = artifacts_root / _artifact_image_dirname(sort_order)
    return image_dir if spec_count == 1 else image_dir / spec_id


def _artifact_model_slug(model: str) -> str:
    slug = re.sub(r"[^a-z0-9._-]+", "-", model.lower()).strip("-")
    return slug or "model"


def _jdcloud_chat_audit(settings: Settings) -> Callable[..., dict[str, Any]]:
    if settings.jdcloud_openai_audit_prompt_mode == "light":
        return audit_image_with_chat_light
    return audit_image_with_chat


def _jdcloud_model_audit(settings: Settings, model: str) -> Callable[..., dict[str, Any]]:
    if settings.jdcloud_openai_audit_prompt_mode == "light" and _is_kimi_model(model):
        return audit_image_with_kimi_light
    return _jdcloud_chat_audit(settings)


def _is_kimi_model(model: str) -> bool:
    return "kimi" in model.lower()


def _dual_auditor(
    settings: Settings,
    declared_screen_size: tuple[int, int] | None = None,
    spec_path: Path | None = None,
    audit_spec_label: str = "JM AI 设计规范",
) -> DualAuditor:
    spec_text = (spec_path or SPEC_PATH).read_text(encoding="utf-8")
    client = OpenAI(
        api_key=settings.audit_api_key,
        base_url=settings.audit_base_url,
        timeout=settings.audit_timeout_seconds,
        max_retries=0,
    )
    def audit(
        image_path: Path,
        artifact_dir: Path,
        scale_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        attempts: list[dict[str, Any]] = []
        image_size = _image_size(image_path)
        for index, model in enumerate(settings.audit_models, start=1):
            model_slug = _artifact_model_slug(model)
            try:
                chat_audit = _jdcloud_model_audit(settings, model)
                result = _call_audit_model(
                    chat_audit,
                    client,
                    model,
                    image_path,
                    spec_text,
                    audit_spec_label=audit_spec_label,
                    reasoning_effort=settings.audit_reasoning_effort,
                    declared_screen_size=declared_screen_size,
                    scale_context=scale_context,
                )
                write_json(
                    artifact_dir / f"audit-{index:02d}-{model_slug}.json",
                    result,
                )
                attempts.append({"model": model, "audit": result, "image_size": image_size})
            except Exception as exc:  # noqa: BLE001 - one model failure should not fail the other.
                failure = model_failure(model, exc)
                write_json(
                    artifact_dir / f"audit-{index:02d}-{model_slug}-failure.json",
                    failure,
                )
                attempts.append(failure)
        primary_attempt = attempts[0] if attempts else {}
        if isinstance(primary_attempt.get("audit"), dict):
            result = merge_primary_with_candidates(
                primary_attempt,
                attempts[1:],
                audit_spec_label=audit_spec_label,
            )
            failures = [
                {
                    "model": str(attempt.get("model") or ""),
                    "error": str(attempt.get("error") or ""),
                    "error_type": str(attempt.get("error_type") or "unknown"),
                    "retriable": bool(attempt.get("retriable")),
                    "degraded": bool(attempt.get("degraded")),
                }
                for attempt in attempts[1:]
                if attempt.get("error")
            ]
            result["model_comparison"]["model_failures"] = failures
            if failures:
                result["overall_conclusion"] = f"候选模型降级审核：{result['overall_conclusion']}"
            return result
        return merge_audit_attempts(attempts, audit_spec_label=audit_spec_label)

    return audit


def _short_error(exc: Exception) -> str:
    return str(exc)[:500] or exc.__class__.__name__


def _call_audit_model(audit: Callable[..., dict[str, Any]], *args: Any, **kwargs: Any) -> dict[str, Any]:
    signature = inspect.signature(audit)
    if "audit_spec_label" not in signature.parameters and not any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD
        for parameter in signature.parameters.values()
    ):
        kwargs.pop("audit_spec_label", None)
    return audit(*args, **kwargs)


def _image_size(path: Path) -> tuple[int, int]:
    with Image.open(path) as source_image:
        return source_image.size


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _audit_spec_label(audit_specs: list[Any]) -> str:
    return "、".join(spec.label for spec in audit_specs)


def _uses_jm_ai_rules(audit_spec_label: str) -> bool:
    return (audit_spec_label or "").strip() == "JM AI 设计规范"


def _write_empty_token_evidence(
    path: Path,
    image_path: Path,
    image_size: tuple[int, int],
    audit_spec_label: str,
) -> None:
    write_json(
        path,
        {
            "image": str(image_path),
            "image_size_px": {"width": image_size[0], "height": image_size[1]},
            "samples": [],
            "dominant_accent_colors": [],
            "notes": [f"{audit_spec_label} 未启用色彩 token 自动判定。"],
        },
    )


def run_task(
    settings: Settings,
    task_id: int,
    auditor: Auditor | None = None,
) -> None:
    conn = connect(settings.db_path)
    try:
        task = get_task_by_id(conn, task_id)
        if task is None:
            return
        audit_specs = get_audit_specs(task.audit_spec_id)

        clear_task_result(conn, task_id)
        update_task_status(conn, task_id, TASK_RUNNING, error_message=None)
        dirs = ensure_task_dirs(settings, task_id)
        declared_screen_size = (
            (task.screen_width_px, task.screen_height_px)
            if task.screen_width_px and task.screen_height_px
            else None
        )
        dual_auditors: dict[str, DualAuditor] = {}
        default_auditors: dict[str, SystemAuditor] = {}
        if auditor is None:
            for audit_spec in audit_specs:
                if settings.audit_mode == "dual":
                    dual_auditors[audit_spec.id] = _dual_auditor(
                        settings,
                        declared_screen_size,
                        spec_path=audit_spec.spec_path,
                        audit_spec_label=audit_spec.label,
                    )
                    continue
                default_auditors[audit_spec.id] = _default_auditor(
                    settings,
                    declared_screen_size,
                    spec_path=audit_spec.spec_path,
                    audit_spec_label=audit_spec.label,
                )

        image_results: list[dict[str, Any]] = []
        success_count = 0
        failure_count = 0

        for image in list_task_images(conn, task_id):
            clear_task_image_artifacts(conn, image.id)
            update_task_image_status(conn, image.id, TASK_RUNNING, error_message=None)
            image_path = resolve_data_path(settings, image.original_path)
            image_errors: list[str] = []
            first_success_artifacts: dict[str, str | None] | None = None

            try:
                image_size = _image_size(image_path)
                scale_context = (
                    compute_scale(image_size, declared_screen_size)
                    if declared_screen_size
                    else None
                )
            except Exception as exc:  # noqa: BLE001 - corrupt source image fails all specs.
                failure_count += len(audit_specs)
                update_task_image_status(
                    conn,
                    image.id,
                    TASK_FAILED,
                    error_message=_short_error(exc),
                )
                continue

            for audit_spec in audit_specs:
                image_artifacts = _artifact_dir_for_spec(
                    dirs.artifacts,
                    image.sort_order,
                    len(audit_specs),
                    audit_spec.id,
                )
                image_artifacts.mkdir(parents=True, exist_ok=True)

                try:
                    if audit_spec.id in dual_auditors:
                        audit = dual_auditors[audit_spec.id](
                            image_path,
                            image_artifacts,
                            scale_context,
                        )
                    elif audit_spec.id in default_auditors:
                        audit = default_auditors[audit_spec.id](
                            image_path,
                            scale_context,
                        )
                    else:
                        if auditor is None:
                            raise RuntimeError("auditor not configured")
                        audit = auditor(image_path)
                    audit_path = image_artifacts / "audit.json"
                    tokens_path = image_artifacts / "tokens.json"
                    regions_path = image_artifacts / "regions.json"
                    measurements_path = image_artifacts / "measurements.json"
                    issues_path = image_artifacts / "issues.json"
                    crop_dir = image_artifacts / "region-crops"

                    if _uses_jm_ai_rules(audit_spec.label):
                        run_color_analysis(
                            image_path,
                            tokens_path,
                            audit.get("sample_points", []),
                        )
                    else:
                        _write_empty_token_evidence(
                            tokens_path,
                            image_path,
                            image_size,
                            audit_spec.label,
                        )
                    write_regions_json(
                        regions_path,
                        audit.get("regions", []),
                        audit.get("distances", []),
                    )
                    run_measurements(
                        image_path,
                        regions_path,
                        measurements_path,
                        crop_dir,
                        design_size=declared_screen_size,
                    )
                    audit = apply_rule_review(
                        audit,
                        tokens=_read_json(tokens_path),
                        measurements=_read_json(measurements_path),
                        image_size=image_size,
                        audit_spec_label=audit_spec.label,
                    )
                    write_json(audit_path, audit)
                    issues_for_screenshots = build_issues_json_for_image(
                        audit.get("issues", []),
                        image_size=image_size,
                    )
                    write_json(issues_path, issues_for_screenshots)
                    annotated_path = None
                    issue_crop_paths: list[str] = []
                    if issues_for_screenshots:
                        run_annotations(image_path, issues_path, image_artifacts)
                        annotated_path = image_artifacts / "annotated.png"
                        issue_crop_paths = [
                            relative_to_data(settings, path)
                            for path in sorted(image_artifacts.glob("issue-*.png"))
                        ]

                    annotated_rel = (
                        relative_to_data(settings, annotated_path)
                        if annotated_path
                        else None
                    )
                    tokens_rel = relative_to_data(settings, tokens_path)
                    measurements_rel = relative_to_data(settings, measurements_path)
                    issues_rel = relative_to_data(settings, issues_path)
                    audit_rel = relative_to_data(settings, audit_path)

                    if first_success_artifacts is None:
                        first_success_artifacts = {
                            "annotated": annotated_rel,
                            "tokens": tokens_rel,
                            "measurements": measurements_rel,
                            "issues": issues_rel,
                            "audit_json": audit_rel,
                        }
                    image_results.append(
                        {
                            "filename": image.filename,
                            "audit_spec_label": audit_spec.label,
                            "spec_asset_index_path": audit_spec.asset_index_path,
                            "audit": audit,
                            "artifacts": {
                                "annotated": annotated_rel,
                                "issue_crops": issue_crop_paths,
                                "tokens": tokens_rel,
                                "measurements": measurements_rel,
                                "issues": issues_rel,
                                "audit_json": audit_rel,
                            },
                        }
                    )
                    success_count += 1
                except Exception as exc:  # noqa: BLE001 - spec-level isolation is intentional.
                    failure_count += 1
                    error = _short_error(exc)
                    if len(audit_specs) > 1:
                        error = f"{audit_spec.label}: {error}"
                    image_errors.append(error)

            if first_success_artifacts:
                update_task_image_status(
                    conn,
                    image.id,
                    TASK_SUCCEEDED,
                    annotated_path=first_success_artifacts["annotated"],
                    tokens_path=first_success_artifacts["tokens"],
                    measurements_path=first_success_artifacts["measurements"],
                    issues_path=first_success_artifacts["issues"],
                    audit_json_path=first_success_artifacts["audit_json"],
                    error_message="；".join(image_errors) if image_errors else None,
                )
            else:
                update_task_image_status(
                    conn,
                    image.id,
                    TASK_FAILED,
                    error_message="；".join(image_errors) or "审核失败",
                )

        if success_count:
            if failure_count:
                if len(audit_specs) == 1:
                    summary = (
                        f"部分图片审核失败：成功 {success_count} 张，"
                        f"失败 {failure_count} 张"
                    )
                else:
                    summary = (
                        f"部分规范审核失败：成功 {success_count} 项，"
                        f"失败 {failure_count} 项"
                    )
            else:
                summary = "审核完成"
            html = render_report_html(
                {
                    "title": task.title,
                    "summary": summary,
                    "audit_spec_label": _audit_spec_label(audit_specs),
                    "screen_width_px": task.screen_width_px,
                    "screen_height_px": task.screen_height_px,
                },
                image_results,
                task_id=task_id,
                spec_asset_index_path=(
                    audit_specs[0].asset_index_path if len(audit_specs) == 1 else None
                ),
            )
            dirs.report.write_text(html, encoding="utf-8")
            update_task_status(
                conn,
                task_id,
                TASK_SUCCEEDED,
                summary=summary,
                report_path=relative_to_data(settings, dirs.report),
                error_message=None,
            )
            return

        update_task_status(
            conn,
            task_id,
            TASK_FAILED,
            summary=None,
            report_path=None,
            error_message="全部图片审核失败",
        )
    finally:
        conn.close()
