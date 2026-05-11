#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import sys
from typing import Any

from openai import OpenAI

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import Settings, load_settings
from app.db import connect
from app.evidence_tools import run_measurements
from app.openai_audit import audit_image, audit_image_with_chat
from app.repositories import get_task_by_id, list_task_images
from app.size_experiment import DesignSizeError, parse_design_size, run_image_experiment
from app.storage import resolve_data_path


SPEC_PATH = ROOT / "references" / "jm-ai-design-spec.md"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run offline manuscript size experiment.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--task-id", type=int)
    source.add_argument("--image", type=Path)
    parser.add_argument("--design-size", required=True, help="Declared design size, e.g. 1440x900")
    parser.add_argument("--output-root", type=Path, default=ROOT / "data" / "experiments")
    return parser.parse_args(argv)


def _build_auditor(settings: Settings):
    spec_text = SPEC_PATH.read_text(encoding="utf-8")
    client = OpenAI(
        api_key=settings.audit_api_key,
        base_url=settings.audit_base_url,
        timeout=settings.audit_timeout_seconds,
        max_retries=0,
    )
    audit = audit_image_with_chat if settings.audit_model_provider == "jdcloud" else audit_image

    def run(
        *,
        image_path: Path,
        declared_size: tuple[int, int],
        scale: dict[str, Any] | None,
        normalized_preview_path: Path | None,
        variant: str,
    ) -> dict[str, Any]:
        return audit(
            client,
            settings.audit_model,
            image_path,
            spec_text,
            reasoning_effort=settings.audit_reasoning_effort,
            declared_screen_size=declared_size,
            scale_context=scale,
            normalized_preview_path=normalized_preview_path,
            experiment_variant=variant,
        )

    return run


def _task_images(settings: Settings, task_id: int) -> list[Path]:
    conn = connect(settings.db_path)
    try:
        task = get_task_by_id(conn, task_id)
        if task is None:
            raise SystemExit(f"task not found: {task_id}")
        return [resolve_data_path(settings, image.original_path) for image in list_task_images(conn, task_id)]
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        declared_size = parse_design_size(args.design_size)
    except DesignSizeError as exc:
        raise SystemExit(str(exc)) from exc

    settings = load_settings()
    images = _task_images(settings, args.task_id) if args.task_id else [args.image]
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    auditor = _build_auditor(settings)

    for index, image_path in enumerate(images, start=1):
        image_key = f"image-{index:03d}"
        output_dir = args.output_root / run_id / image_key
        comparison = run_image_experiment(
            image_path=image_path,
            declared_size=declared_size,
            output_dir=output_dir,
            auditor=auditor,
            run_measurements_func=run_measurements,
        )
        print(
            f"{image_path} -> {output_dir / 'comparison.html'} "
            f"({len(comparison['variants'])} variants)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
