from __future__ import annotations

import json
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
from app.openai_audit import audit_image, audit_image_with_chat, audit_image_with_chat_light
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
from app.storage import ensure_task_dirs, relative_to_data, resolve_data_path


Auditor = Callable[[Path], dict[str, Any]]
SystemAuditor = Callable[[Path, dict[str, Any] | None], dict[str, Any]]
DualAuditor = Callable[[Path, Path, dict[str, Any] | None], dict[str, Any]]
SPEC_PATH = Path(__file__).resolve().parent.parent / "references" / "jm-ai-design-spec.md"


def _default_auditor(
    settings: Settings,
    declared_screen_size: tuple[int, int] | None = None,
) -> SystemAuditor:
    spec_text = SPEC_PATH.read_text(encoding="utf-8")
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
        return audit(
            client,
            settings.audit_model,
            image_path,
            spec_text,
            reasoning_effort=settings.audit_reasoning_effort,
            declared_screen_size=declared_screen_size,
            scale_context=scale_context,
        )

    return run_audit


def _stem(filename: str) -> str:
    return filename.rsplit(".", 1)[0]


def _artifact_image_dirname(sort_order: int) -> str:
    return f"image-{sort_order + 1:03d}"


def _artifact_model_slug(model: str) -> str:
    slug = re.sub(r"[^a-z0-9._-]+", "-", model.lower()).strip("-")
    return slug or "model"


def _jdcloud_chat_audit(settings: Settings) -> Callable[..., dict[str, Any]]:
    if settings.jdcloud_openai_audit_prompt_mode == "light":
        return audit_image_with_chat_light
    return audit_image_with_chat


def _dual_auditor(
    settings: Settings,
    declared_screen_size: tuple[int, int] | None = None,
) -> DualAuditor:
    spec_text = SPEC_PATH.read_text(encoding="utf-8")
    client = OpenAI(
        api_key=settings.audit_api_key,
        base_url=settings.audit_base_url,
        timeout=settings.audit_timeout_seconds,
        max_retries=0,
    )
    chat_audit = _jdcloud_chat_audit(settings)

    def audit(
        image_path: Path,
        artifact_dir: Path,
        scale_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        attempts: list[dict[str, Any]] = []
        image_size = _image_size(image_path)
        for index, model in enumerate(settings.audit_models, start=1):
            try:
                result = chat_audit(
                    client,
                    model,
                    image_path,
                    spec_text,
                    reasoning_effort=settings.audit_reasoning_effort,
                    declared_screen_size=declared_screen_size,
                    scale_context=scale_context,
                )
                write_json(
                    artifact_dir / f"audit-{index:02d}-{_artifact_model_slug(model)}.json",
                    result,
                )
                attempts.append({"model": model, "audit": result, "image_size": image_size})
            except Exception as exc:  # noqa: BLE001 - one model failure should not fail the other.
                attempts.append({"model": model, "error": _short_error(exc)})
        primary_attempt = attempts[0] if attempts else {}
        if isinstance(primary_attempt.get("audit"), dict):
            result = merge_primary_with_candidates(primary_attempt, attempts[1:])
            failures = [
                {"model": str(attempt.get("model") or ""), "error": str(attempt.get("error") or "")}
                for attempt in attempts[1:]
                if attempt.get("error")
            ]
            result["model_comparison"]["model_failures"] = failures
            if failures:
                result["overall_conclusion"] = f"候选模型降级审核：{result['overall_conclusion']}"
            return result
        return merge_audit_attempts(attempts)

    return audit


def _short_error(exc: Exception) -> str:
    return str(exc)[:500] or exc.__class__.__name__


def _image_size(path: Path) -> tuple[int, int]:
    with Image.open(path) as source_image:
        return source_image.size


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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

        clear_task_result(conn, task_id)
        update_task_status(conn, task_id, TASK_RUNNING, error_message=None)
        dirs = ensure_task_dirs(settings, task_id)
        declared_screen_size = (
            (task.screen_width_px, task.screen_height_px)
            if task.screen_width_px and task.screen_height_px
            else None
        )
        dual_auditor = None
        default_auditor: SystemAuditor | None = None
        if auditor is None and settings.audit_mode == "dual":
            dual_auditor = _dual_auditor(settings, declared_screen_size)
        else:
            if auditor is None:
                default_auditor = _default_auditor(settings, declared_screen_size)

        image_results: list[dict[str, Any]] = []
        success_count = 0
        failure_count = 0

        for image in list_task_images(conn, task_id):
            clear_task_image_artifacts(conn, image.id)
            update_task_image_status(conn, image.id, TASK_RUNNING, error_message=None)
            image_path = resolve_data_path(settings, image.original_path)
            image_artifacts = dirs.artifacts / _artifact_image_dirname(image.sort_order)
            image_artifacts.mkdir(parents=True, exist_ok=True)

            try:
                image_size = _image_size(image_path)
                scale_context = (
                    compute_scale(image_size, declared_screen_size)
                    if declared_screen_size
                    else None
                )
                if dual_auditor is not None:
                    audit = dual_auditor(image_path, image_artifacts, scale_context)
                elif default_auditor is not None:
                    audit = default_auditor(image_path, scale_context)
                else:
                    audit = auditor(image_path)
                audit_path = image_artifacts / "audit.json"
                tokens_path = image_artifacts / "tokens.json"
                regions_path = image_artifacts / "regions.json"
                measurements_path = image_artifacts / "measurements.json"
                issues_path = image_artifacts / "issues.json"
                crop_dir = image_artifacts / "region-crops"

                run_color_analysis(image_path, tokens_path, audit.get("sample_points", []))
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
                    relative_to_data(settings, annotated_path) if annotated_path else None
                )
                tokens_rel = relative_to_data(settings, tokens_path)
                measurements_rel = relative_to_data(settings, measurements_path)
                issues_rel = relative_to_data(settings, issues_path)
                audit_rel = relative_to_data(settings, audit_path)

                update_task_image_status(
                    conn,
                    image.id,
                    TASK_SUCCEEDED,
                    annotated_path=annotated_rel,
                    tokens_path=tokens_rel,
                    measurements_path=measurements_rel,
                    issues_path=issues_rel,
                    audit_json_path=audit_rel,
                    error_message=None,
                )
                image_results.append(
                    {
                        "filename": image.filename,
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
            except Exception as exc:  # noqa: BLE001 - image-level isolation is intentional.
                failure_count += 1
                update_task_image_status(
                    conn,
                    image.id,
                    TASK_FAILED,
                    error_message=_short_error(exc),
                )

        if success_count:
            if failure_count:
                summary = f"部分图片审核失败：成功 {success_count} 张，失败 {failure_count} 张"
            else:
                summary = "审核完成"
            html = render_report_html(
                {
                    "title": task.title,
                    "summary": summary,
                    "screen_width_px": task.screen_width_px,
                    "screen_height_px": task.screen_height_px,
                },
                image_results,
                task_id=task_id,
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
