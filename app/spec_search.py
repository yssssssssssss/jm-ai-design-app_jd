from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from app.spec_registry import AuditSpec, list_audit_specs


MAX_QUERY_LENGTH = 200
MAX_SNIPPET_LENGTH = 260


@dataclass(frozen=True)
class SpecChunk:
    spec_id: str
    spec_label: str
    title: str
    source_ref: str
    text: str
    page: int | None


def search_specs(query: str, limit: int = 2) -> dict[str, Any]:
    clean_query = _clean_query(query)
    if not clean_query:
        raise ValueError("empty query")
    if len(clean_query) > MAX_QUERY_LENGTH:
        raise ValueError("query too long")

    terms = _query_terms(clean_query)
    scored: list[tuple[int, SpecChunk, list[dict[str, Any]]]] = []
    for spec in list_audit_specs():
        assets = _load_assets(spec)
        for chunk in _spec_chunks(spec):
            score = _chunk_score(chunk, terms, assets)
            if score <= 0:
                continue
            scored.append((score, chunk, _related_assets(chunk, terms, assets)))

    scored.sort(key=lambda item: item[0], reverse=True)
    results = [
        _result_payload(chunk, score, assets, terms)
        for score, chunk, assets in scored[: max(1, limit)]
    ]
    return {
        "query": clean_query,
        "summary": _summary(clean_query, results),
        "results": results,
    }


def _clean_query(query: str) -> str:
    return re.sub(r"\s+", " ", str(query or "")).strip()


def _query_terms(query: str) -> list[str]:
    raw_terms = re.findall(r"[a-zA-Z0-9+#._-]+|[\u4e00-\u9fff]{2,}", query.lower())
    terms: list[str] = []
    for term in raw_terms:
        if term not in terms:
            terms.append(term)
    if len(terms) > 1:
        return terms
    compact = re.sub(r"\s+", "", query.lower())
    for size in (4, 3, 2):
        for index in range(0, max(0, len(compact) - size + 1)):
            token = compact[index : index + size]
            if re.search(r"[\u4e00-\u9fff]", token) and token not in terms:
                terms.append(token)
    return terms or [query.lower()]


def _spec_chunks(spec: AuditSpec) -> list[SpecChunk]:
    try:
        text = spec.spec_path.read_text(encoding="utf-8")
    except OSError:
        return []

    chunks: list[SpecChunk] = []
    current_title = spec.label
    current_page: int | None = None
    buffer: list[str] = []

    def flush() -> None:
        content = _normalize_markdown_text("\n".join(buffer))
        if content:
            chunks.append(
                SpecChunk(
                    spec_id=spec.id,
                    spec_label=spec.label,
                    title=current_title,
                    source_ref=_source_ref(spec.label, current_page, current_title),
                    text=content,
                    page=current_page,
                )
            )
        buffer.clear()

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("## "):
            flush()
            current_title = line.lstrip("#").strip()
            current_page = _page_number(current_title)
            continue
        if line.startswith("# "):
            continue
        if line.startswith("### "):
            title = line.lstrip("#").strip()
            if title != "参考素材":
                buffer.append(title)
            continue
        if line.startswith("- ") and "/spec-snippets/" in line:
            continue
        buffer.append(line)
    flush()
    return chunks


def _normalize_markdown_text(text: str) -> str:
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def _page_number(title: str) -> int | None:
    match = re.search(r"第\s*(\d+)\s*页", title)
    return int(match.group(1)) if match else None


def _source_ref(spec_label: str, page: int | None, title: str) -> str:
    parts = [spec_label]
    if page is not None:
        parts.append(f"第 {page} 页")
    elif title and title != spec_label:
        parts.append(title)
    return " / ".join(parts)


def _load_assets(spec: AuditSpec) -> list[dict[str, Any]]:
    try:
        data = json.loads(spec.asset_index_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    assets = data.get("assets") if isinstance(data, dict) else None
    return [asset for asset in assets or [] if isinstance(asset, dict)]


def _chunk_score(chunk: SpecChunk, terms: list[str], assets: list[dict[str, Any]]) -> int:
    label_text = _fold(chunk.spec_label)
    title_text = _fold(chunk.title)
    body_text = _fold(" ".join([chunk.title, chunk.text]))
    score = 0
    body_matches = 0
    for term in terms:
        folded = _fold(term)
        if not folded:
            continue
        if folded in label_text:
            score += 2
        if folded in title_text:
            score += 7
        if folded in body_text:
            body_matches += 1
            score += 5
            score += min(8, body_text.count(folded))
    for asset in assets:
        asset_page = _asset_page(asset)
        if chunk.page is not None:
            if asset_page != chunk.page:
                continue
        elif asset_page is not None:
            continue
        asset_text = _asset_search_text(asset)
        asset_matches = sum(1 for term in terms if _fold(term) in asset_text)
        if asset_matches:
            score += asset_matches * 5
            if asset_matches >= 2:
                score += 10
    score += min(24, body_matches * 6)
    return score


def _related_assets(
    chunk: SpecChunk,
    terms: list[str],
    assets: list[dict[str, Any]],
    limit: int = 4,
) -> list[dict[str, Any]]:
    scored: list[tuple[int, dict[str, Any]]] = []
    for asset in assets:
        score = 0
        if chunk.page is not None and _asset_page(asset) == chunk.page:
            score += 8
        asset_text = _asset_search_text(asset)
        for term in terms:
            if _fold(term) in asset_text:
                score += 4
        if score > 0:
            scored.append((score, asset))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [_asset_payload(asset) for _, asset in scored[:limit]]


def _asset_page(asset: dict[str, Any]) -> int | None:
    match = re.search(r"#page=(\d+)", str(asset.get("source") or ""))
    return int(match.group(1)) if match else None


def _asset_search_text(asset: dict[str, Any]) -> str:
    keywords = asset.get("keywords") if isinstance(asset.get("keywords"), list) else []
    return _fold(" ".join([str(asset.get("label") or ""), str(asset.get("source") or ""), *map(str, keywords)]))


def _asset_payload(asset: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(asset.get("id") or ""),
        "label": str(asset.get("label") or "规范素材"),
        "url": str(asset.get("url") or ""),
        "source": str(asset.get("source") or ""),
    }


def _result_payload(
    chunk: SpecChunk,
    score: int,
    assets: list[dict[str, Any]],
    terms: list[str],
) -> dict[str, Any]:
    return {
        "spec_id": chunk.spec_id,
        "spec_label": chunk.spec_label,
        "title": chunk.title,
        "source_ref": chunk.source_ref,
        "excerpt": _excerpt(chunk.text, terms),
        "score": score,
        "assets": assets,
    }


def _excerpt(text: str, terms: list[str]) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= MAX_SNIPPET_LENGTH:
        return compact
    folded = _fold(compact)
    positions = [
        folded.find(_fold(term))
        for term in terms
        if len(_fold(term)) >= 2 and _fold(term) in folded
    ]
    start = max(0, max(positions) - 110) if positions else 0
    end = min(len(compact), start + MAX_SNIPPET_LENGTH)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(compact) else ""
    return f"{prefix}{compact[start:end].strip()}{suffix}"


def _summary(query: str, results: list[dict[str, Any]]) -> str:
    if not results:
        return f"没有找到与「{query}」明确匹配的规范内容。"
    spec_count = len({result["spec_id"] for result in results})
    asset_count = sum(len(result["assets"]) for result in results)
    return f"找到 {len(results)} 条相关规范内容，覆盖 {spec_count} 个规范，并关联 {asset_count} 张素材。"


def _fold(value: Any) -> str:
    return str(value or "").lower().replace(" ", "")
