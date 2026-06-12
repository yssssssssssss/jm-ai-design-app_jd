from __future__ import annotations

import json
from pathlib import Path

from app.config import Settings
from app.models import Task, TaskImage
from app.report_renderer import REPORT_RENDERER_VERSION, render_report_html
from app.spec_registry import get_audit_spec, get_audit_specs
from app.storage import UploadValidationError, resolve_data_path


def html_report_with_pdf_link(path: Path, task_id: int) -> str:
    html = path.read_text(encoding="utf-8")
    pdf_href = f"/tasks/{task_id}/report.pdf"
    if pdf_href in html:
        return html

    back_link = '<a class="back-link" href="/tasks">返回</a>'
    if back_link in html:
        return html.replace(
            back_link,
            f'{back_link}\n      <a class="back-link" href="{pdf_href}">下载 PDF</a>',
            1,
        )
    return html


def html_report_is_current(path: Path) -> bool:
    try:
        html = path.read_text(encoding="utf-8")
    except OSError:
        return False
    return f'name="jm-report-renderer" content="{REPORT_RENDERER_VERSION}"' in html


def artifact_rel(path: str | None) -> str | None:
    if not path:
        return None
    normalized = path.replace("\\", "/")
    marker = "/artifacts/"
    if marker in normalized:
        return "artifacts/" + normalized.split(marker, 1)[1]
    if normalized.startswith("artifacts/"):
        return normalized
    return normalized


def existing_artifact_rel(settings: Settings, path: str | None) -> str | None:
    if not path:
        return None
    try:
        if not resolve_data_path(settings, path).exists():
            return None
    except UploadValidationError:
        return None
    return artifact_rel(path)


def load_json_artifact(settings: Settings, relative_path: str | None) -> dict | None:
    if not relative_path:
        return None
    try:
        path = resolve_data_path(settings, relative_path)
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UploadValidationError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def audit_spec_label(specs) -> str:
    return "、".join(spec.label for spec in specs) if specs else get_audit_spec(None).label


def image_artifact_dirname(sort_order: int) -> str:
    return f"image-{sort_order + 1:03d}"


def multi_spec_artifact_path(
    task_id: int,
    sort_order: int,
    spec_id: str,
    filename: str,
) -> str:
    image_dir = image_artifact_dirname(sort_order)
    return f"uploads/{task_id}/artifacts/{image_dir}/{spec_id}/{filename}"


def report_artifact_paths(task: Task, images: list[TaskImage]) -> list[str]:
    audit_specs = get_audit_specs(task.audit_spec_id)
    paths = []
    for image in images:
        if len(audit_specs) == 1:
            if image.audit_json_path:
                paths.append(image.audit_json_path)
            continue
        for spec in audit_specs:
            paths.append(
                multi_spec_artifact_path(task.id, image.sort_order, spec.id, "audit.json")
            )
    return paths


def _report_artifact_is_newer(settings: Settings, relative_path: str, report_mtime: float) -> bool:
    artifact_path = resolve_data_path(settings, relative_path)
    if not artifact_path.exists() or not artifact_path.is_file():
        return True
    if artifact_path.stat().st_mtime > report_mtime:
        return True
    for crop_path in sorted(artifact_path.parent.glob("issue-*.png")):
        if crop_path.is_file() and crop_path.stat().st_mtime > report_mtime:
            return True
    return False


def report_artifacts_are_cached(
    settings: Settings,
    task: Task,
    images: list[TaskImage],
    stored_path: Path,
) -> bool:
    if (
        not stored_path.exists()
        or not stored_path.is_file()
        or not html_report_is_current(stored_path)
    ):
        return False
    artifact_paths = report_artifact_paths(task, images)
    if not artifact_paths:
        return False
    try:
        report_mtime = stored_path.stat().st_mtime
    except OSError:
        return False
    for relative_path in artifact_paths:
        try:
            is_newer = _report_artifact_is_newer(settings, relative_path, report_mtime)
        except UploadValidationError:
            return False
        if is_newer:
            return False
    return True


def legacy_artifact_bundle(settings: Settings, image: TaskImage) -> dict:
    return {
        "annotated": artifact_rel(image.annotated_path),
        "issue_crops": issue_crop_paths(settings, image.audit_json_path),
        "tokens": artifact_rel(image.tokens_path),
        "measurements": artifact_rel(image.measurements_path),
        "issues": artifact_rel(image.issues_path),
        "audit_json": artifact_rel(image.audit_json_path),
    }


def multi_spec_artifact_bundle(
    settings: Settings,
    task_id: int,
    sort_order: int,
    spec_id: str,
) -> dict:
    return {
        "annotated": existing_artifact_rel(
            settings,
            multi_spec_artifact_path(task_id, sort_order, spec_id, "annotated.png"),
        ),
        "issue_crops": issue_crop_paths(
            settings,
            multi_spec_artifact_path(task_id, sort_order, spec_id, "audit.json"),
        ),
        "tokens": artifact_rel(
            multi_spec_artifact_path(task_id, sort_order, spec_id, "tokens.json")
        ),
        "measurements": artifact_rel(
            multi_spec_artifact_path(task_id, sort_order, spec_id, "measurements.json")
        ),
        "issues": artifact_rel(
            multi_spec_artifact_path(task_id, sort_order, spec_id, "issues.json")
        ),
        "audit_json": artifact_rel(
            multi_spec_artifact_path(task_id, sort_order, spec_id, "audit.json")
        ),
    }


def build_report_image_results(
    settings: Settings,
    task: Task,
    images: list[TaskImage],
) -> list[dict]:
    audit_specs = get_audit_specs(task.audit_spec_id)
    image_results = []
    for image in images:
        if len(audit_specs) == 1:
            audit = load_json_artifact(settings, image.audit_json_path)
            if not audit:
                continue
            image_results.append(
                {
                    "filename": image.filename,
                    "audit_spec_label": audit_specs[0].label,
                    "spec_asset_index_path": audit_specs[0].asset_index_path,
                    "audit": audit,
                    "artifacts": legacy_artifact_bundle(settings, image),
                }
            )
            continue
        for spec in audit_specs:
            audit_path = multi_spec_artifact_path(
                task.id, image.sort_order, spec.id, "audit.json"
            )
            audit = load_json_artifact(settings, audit_path)
            if not audit:
                continue
            image_results.append(
                {
                    "filename": image.filename,
                    "audit_spec_label": spec.label,
                    "spec_asset_index_path": spec.asset_index_path,
                    "audit": audit,
                    "artifacts": multi_spec_artifact_bundle(
                        settings,
                        task.id,
                        image.sort_order,
                        spec.id,
                    ),
                }
            )
    return image_results


def current_report_html(
    settings: Settings,
    task: Task,
    images: list[TaskImage],
    stored_path: Path,
) -> str:
    if report_artifacts_are_cached(settings, task, images, stored_path):
        return html_report_with_pdf_link(stored_path, task.id)

    audit_specs = get_audit_specs(task.audit_spec_id)
    image_results = build_report_image_results(settings, task, images)

    if not image_results:
        return html_report_with_pdf_link(stored_path, task.id)

    html = render_report_html(
        {
            "title": task.title,
            "summary": task.summary,
            "audit_spec_label": audit_spec_label(audit_specs),
            "screen_width_px": task.screen_width_px,
            "screen_height_px": task.screen_height_px,
        },
        image_results,
        task_id=task.id,
    )
    if stored_path.read_text(encoding="utf-8") != html:
        stored_path.write_text(html, encoding="utf-8")
    return html


def issue_crop_paths(settings: Settings, anchor_path: str | None) -> list[str]:
    if not anchor_path:
        return []
    try:
        path = resolve_data_path(settings, anchor_path).parent
    except UploadValidationError:
        return []
    if not path.exists() or not path.is_dir():
        return []
    root = settings.data_dir.resolve()
    paths = []
    for candidate in sorted(path.glob("issue-*.png")):
        if not candidate.is_file():
            continue
        resolved = candidate.resolve()
        if root not in resolved.parents and resolved != root:
            continue
        paths.append(resolved.relative_to(root).as_posix())
    return paths
