from pathlib import Path

from app.config import Settings
from app.pdf_renderer import PDF_RENDERER_VERSION, is_current_report_pdf, _rewrite_local_urls


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        openai_api_key="test",
        app_secret_key="secret",
        register_invite_code="invite",
        initial_admin_username="admin",
        initial_admin_password="secret123",
        data_dir=tmp_path,
    )


def test_rewrite_local_urls_maps_protected_report_assets(tmp_path):
    settings = _settings(tmp_path)
    artifact = tmp_path / "uploads" / "7" / "artifacts" / "image-001" / "crop.png"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"png")

    html = '<img src="/artifacts/7/image-001/crop.png"><a href="/tasks/7/report.html">report</a>'

    rewritten = _rewrite_local_urls(settings, 7, html)

    assert artifact.as_uri() in rewritten
    assert 'href="/tasks/7/report.html"' in rewritten


def test_rewrite_local_urls_maps_report_assets_with_artifacts_prefix(tmp_path):
    settings = _settings(tmp_path)
    artifact = tmp_path / "uploads" / "7" / "artifacts" / "image-001" / "crop.png"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"png")

    html = '<img src="/artifacts/7/artifacts/image-001/crop.png">'

    assert artifact.as_uri() in _rewrite_local_urls(settings, 7, html)


def test_rewrite_local_urls_maps_spec_snippets(tmp_path):
    html = '<img src="/spec-snippets/button-primary.png">'

    rewritten = _rewrite_local_urls(_settings(tmp_path), 7, html)

    assert "/assets/spec-snippets/button-primary.png" in rewritten


def test_rewrite_local_urls_maps_nested_b_design_spec_snippets(tmp_path):
    html = '<img src="/spec-snippets/b-design/task-planning.png">'

    rewritten = _rewrite_local_urls(_settings(tmp_path), 7, html)

    assert "/assets/spec-snippets/b-design/task-planning.png" in rewritten


def test_rewrite_local_urls_rejects_artifact_traversal(tmp_path):
    settings = _settings(tmp_path)

    html = '<img src="/artifacts/7/../app.db">'

    assert _rewrite_local_urls(settings, 7, html) == html


def test_is_current_report_pdf_requires_matching_version(tmp_path):
    pdf = tmp_path / "report.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")

    assert not is_current_report_pdf(pdf)

    pdf.with_name("report.pdf.version").write_text(PDF_RENDERER_VERSION, encoding="utf-8")

    assert is_current_report_pdf(pdf)
