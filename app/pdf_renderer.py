from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import unquote

from app.config import PROJECT_ROOT, Settings


class PdfRenderError(Exception):
    pass


PDF_RENDERER_VERSION = "2026-05-14-local-image-paths-v2"
_SRC_ATTR_RE = re.compile(r'(?P<prefix>\s(?:src|href)=["\'])(?P<url>/[^"\']+)(?P<suffix>["\'])')


def render_report_pdf(
    settings: Settings,
    task_id: int,
    html_path: Path,
    pdf_path: Path,
) -> None:
    browser = _find_browser()
    if browser is None:
        raise PdfRenderError("未找到可用的 Chrome/Chromium 浏览器")
    if not html_path.exists() or not html_path.is_file():
        raise PdfRenderError("HTML 报告不存在")

    with tempfile.TemporaryDirectory(prefix="jm-report-pdf-") as tmp:
        printable_html = Path(tmp) / "report.html"
        printable_html.write_text(
            _rewrite_local_urls(settings, task_id, html_path.read_text(encoding="utf-8")),
            encoding="utf-8",
        )
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        command = [
            browser,
            "--headless",
            "--disable-gpu",
            "--allow-file-access-from-files",
            "--no-sandbox",
            f"--print-to-pdf={pdf_path}",
            printable_html.as_uri(),
        ]
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
    if result.returncode != 0:
        pdf_path.unlink(missing_ok=True)
        raise PdfRenderError((result.stderr or result.stdout or "PDF 生成失败").strip())
    if not pdf_path.exists() or pdf_path.stat().st_size == 0:
        raise PdfRenderError("PDF 生成失败")
    _version_path(pdf_path).write_text(PDF_RENDERER_VERSION, encoding="utf-8")


def is_current_report_pdf(pdf_path: Path) -> bool:
    if not pdf_path.exists() or not pdf_path.is_file() or pdf_path.stat().st_size == 0:
        return False
    try:
        return _version_path(pdf_path).read_text(encoding="utf-8") == PDF_RENDERER_VERSION
    except OSError:
        return False


def _find_browser() -> str | None:
    candidates = [
        "chromium",
        "chromium-browser",
        "google-chrome",
        "google-chrome-stable",
        "chrome",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
    ]
    for candidate in candidates:
        if "/" in candidate:
            if Path(candidate).exists():
                return candidate
            continue
        found = shutil.which(candidate)
        if found:
            return found
    return None


def _rewrite_local_urls(settings: Settings, task_id: int, html: str) -> str:
    def replace(match: re.Match[str]) -> str:
        path = unquote(match.group("url").split("?", 1)[0])
        local_path = _local_path_for_url(settings, task_id, path)
        if local_path is None:
            return match.group(0)
        return f'{match.group("prefix")}{local_path.as_uri()}{match.group("suffix")}'

    return _SRC_ATTR_RE.sub(replace, html)


def _local_path_for_url(settings: Settings, task_id: int, url_path: str) -> Path | None:
    artifact_prefix = f"/artifacts/{task_id}/"
    if url_path.startswith(artifact_prefix):
        relative = url_path[len(artifact_prefix) :]
        if relative.startswith("artifacts/"):
            relative = relative[len("artifacts/") :]
        candidate = (settings.uploads_dir / str(task_id) / "artifacts" / relative).resolve()
        root = (settings.uploads_dir / str(task_id) / "artifacts").resolve()
        if root in candidate.parents or candidate == root:
            return candidate
        return None
    if url_path.startswith("/spec-assets/"):
        relative = url_path[len("/spec-assets/") :]
        candidate = (PROJECT_ROOT / "assets" / "spec-images" / relative).resolve()
        root = (PROJECT_ROOT / "assets" / "spec-images").resolve()
        if root in candidate.parents or candidate == root:
            return candidate
    if url_path.startswith("/spec-snippets/"):
        relative = url_path[len("/spec-snippets/") :]
        candidate = (PROJECT_ROOT / "assets" / "spec-snippets" / relative).resolve()
        root = (PROJECT_ROOT / "assets" / "spec-snippets").resolve()
        if root in candidate.parents or candidate == root:
            return candidate
    return None


def _version_path(pdf_path: Path) -> Path:
    return pdf_path.with_name(f"{pdf_path.name}.version")
