#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE_DIR = ROOT / "assets" / "spec-images"
DEFAULT_OUTPUT_DIR = ROOT / "assets" / "spec-snippets"
DEFAULT_INDEX_PATH = ROOT / "references" / "spec-assets.json"


@dataclass(frozen=True)
class Snippet:
    id: str
    source: str
    bbox: tuple[int, int, int, int]
    label: str
    keywords: tuple[str, ...]

    @property
    def filename(self) -> str:
        return f"{self.id}.png"

    @property
    def url(self) -> str:
        return f"/spec-snippets/{self.filename}"


SNIPPETS = [
    Snippet(
        id="button-primary",
        source="buttons.png",
        bbox=(105, 875, 940, 1198),
        label="主要按钮填充",
        keywords=("主要按钮", "主按钮", "primary button", "填充按钮", "ai 按钮"),
    ),
    Snippet(
        id="button-secondary",
        source="buttons.png",
        bbox=(1040, 875, 1845, 1198),
        label="次要按钮填充",
        keywords=("次要按钮", "secondary button", "浅色按钮", "ghost", "次级填充"),
    ),
    Snippet(
        id="button-outline",
        source="buttons.png",
        bbox=(1978, 875, 2795, 1198),
        label="主要线性按钮",
        keywords=("线性按钮", "描边按钮", "边框按钮", "outline button"),
    ),
    Snippet(
        id="button-sparkle",
        source="buttons.png",
        bbox=(105, 875, 940, 1198),
        label="AI 按钮 Sparkle 标识",
        keywords=("sparkle", "ai sparkle", "ai 图标", "ai标识", "生成类 ai", "智能生成"),
    ),
    Snippet(
        id="tag-ai-capsule",
        source="tags.png",
        bbox=(130, 640, 1180, 900),
        label="AI 标签样式",
        keywords=("ai 标签", "标签", "胶囊", "tag", "角标", "badge"),
    ),
]

MANUAL_SNIPPET_METADATA = {
    "color-ai-main-color": {
        "label": "AI 主纯色",
        "keywords": ("ai/ai-normal", "#6b36fa", "主纯色", "主色", "紫色", "ai 主色"),
    },
    "color-ai-light-color": {
        "label": "AI light 纯色",
        "keywords": ("ai/ai-light-normal", "#f3f0ff", "light 纯色", "浅色", "浅紫", "浅色按钮"),
    },
    "color-ai-main-gradient": {
        "label": "AI 主渐变色",
        "keywords": ("gradient/ai/ai-normal", "主渐变", "ai 渐变", "渐变色", "主渐变色"),
    },
    "color-ai-light-gradient": {
        "label": "AI light 渐变色",
        "keywords": ("gradient/ai/ai-light-normal", "light 渐变", "浅色渐变", "浅紫渐变"),
    },
    "color-ai-brand-color": {
        "label": "AI 品牌色板",
        "keywords": ("品牌色", "色板", "ai 色彩体系", "品牌色板", "ai 品牌色"),
    },
}


def generate_spec_snippets(
    source_dir: Path = DEFAULT_SOURCE_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    index_path: Path = DEFAULT_INDEX_PATH,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    assets_by_id: dict[str, dict[str, Any]] = {}
    for snippet in SNIPPETS:
        source_path = source_dir / snippet.source
        if not source_path.exists():
            continue
        with Image.open(source_path) as image:
            crop = image.crop(snippet.bbox)
            crop.save(output_dir / snippet.filename)
        assets_by_id[snippet.id] = _snippet_asset(snippet)

    for path in sorted(output_dir.glob("*.png")):
        snippet_id = path.stem
        if snippet_id in assets_by_id:
            continue
        assets_by_id[snippet_id] = _manual_asset(path)

    index = {"version": 1, "assets": list(assets_by_id.values())}
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return index


def _snippet_asset(snippet: Snippet) -> dict[str, Any]:
    return {
        "id": snippet.id,
        "label": snippet.label,
        "url": snippet.url,
        "source": snippet.source,
        "bbox": list(snippet.bbox),
        "keywords": list(snippet.keywords),
    }


def _manual_asset(path: Path) -> dict[str, Any]:
    snippet_id = path.stem
    metadata = MANUAL_SNIPPET_METADATA.get(snippet_id, {})
    label = str(metadata.get("label") or _label_from_id(snippet_id))
    keywords = list(metadata.get("keywords") or ())
    keywords.extend(_keywords_from_id(snippet_id))
    return {
        "id": snippet_id,
        "label": label,
        "url": f"/spec-snippets/{path.name}",
        "source": "manual",
        "keywords": _unique(keywords),
    }


def _label_from_id(snippet_id: str) -> str:
    return snippet_id.replace("-", " ")


def _keywords_from_id(snippet_id: str) -> list[str]:
    parts = [part for part in snippet_id.replace("_", "-").split("-") if part]
    keywords = [snippet_id, " ".join(parts)]
    if "button" in parts:
        keywords.append("按钮")
    if "tag" in parts:
        keywords.extend(["标签", "tag"])
    if "gradient" in parts:
        keywords.append("渐变")
    if "light" in parts:
        keywords.extend(["浅色", "light"])
    if "main" in parts:
        keywords.extend(["主色", "main"])
    if "brand" in parts:
        keywords.extend(["品牌色", "brand"])
    return keywords


def _unique(values: list[str]) -> list[str]:
    output = []
    seen = set()
    for value in values:
        text = str(value).strip()
        key = text.lower()
        if text and key not in seen:
            seen.add(key)
            output.append(text)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate cropped JM AI spec snippets and index.")
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX_PATH)
    args = parser.parse_args()
    index = generate_spec_snippets(args.source_dir, args.output_dir, args.index)
    print(f"generated {len(index['assets'])} spec snippets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
