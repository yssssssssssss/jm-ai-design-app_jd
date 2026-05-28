#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parent.parent
SOURCE_PDF = ROOT / "references" / "bottom-nav" / "导航类-底部导航栏.pdf"
SPEC_OUT = ROOT / "references" / "specs" / "bottom-nav.md"
SNIPPET_DIR = ROOT / "assets" / "spec-snippets" / "bottom-nav"
INDEX_OUT = ROOT / "references" / "spec-assets-bottom-nav.json"

HEADING_HINTS = (
    "组件定义",
    "行为准则",
    "设计属性",
    "常规底导布局属性",
    "Agent+底导布局属性",
    "交互状态标注",
    "招手形态标注",
    "Joy Agent",
    "灵动岛运营资源位",
    "颜色应用",
    "材质应用",
    "多端适配",
    "底导换肤规则",
    "底导元素换肤要求",
    "图标交互状态",
    "底导换肤材质规则",
    "错误用法",
)


def main() -> int:
    _require_tool("pdfinfo")
    _require_tool("pdftotext")
    _require_tool("pdfimages")
    if not SOURCE_PDF.exists():
        raise FileNotFoundError(SOURCE_PDF)

    SPEC_OUT.parent.mkdir(parents=True, exist_ok=True)
    SNIPPET_DIR.mkdir(parents=True, exist_ok=True)
    _clean_generated_snippets()

    page_count = _page_count(SOURCE_PDF)
    pages = [_page_text(SOURCE_PDF, page) for page in range(1, page_count + 1)]
    assets = _extract_assets(pages)

    SPEC_OUT.write_text(_spec_markdown(pages, assets), encoding="utf-8")
    INDEX_OUT.write_text(
        json.dumps({"version": 1, "spec_id": "bottom-nav", "assets": assets}, ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote {SPEC_OUT.relative_to(ROOT)}")
    print(f"wrote {INDEX_OUT.relative_to(ROOT)}")
    print(f"wrote {len(assets)} snippets under {SNIPPET_DIR.relative_to(ROOT)}")
    return 0


def _require_tool(name: str) -> None:
    if shutil.which(name) is None:
        raise RuntimeError(f"missing required tool: {name}")


def _clean_generated_snippets() -> None:
    for path in SNIPPET_DIR.glob("*.png"):
        path.unlink()


def _page_count(path: Path) -> int:
    result = subprocess.run(["pdfinfo", str(path)], check=True, capture_output=True, text=True)
    match = re.search(r"^Pages:\s+(\d+)$", result.stdout, flags=re.MULTILINE)
    if not match:
        raise RuntimeError(f"cannot read page count for {path}")
    return int(match.group(1))


def _page_text(path: Path, page: int) -> str:
    with tempfile.TemporaryDirectory(prefix="bottom-nav-text-") as tmp:
        out = Path(tmp) / "page.txt"
        subprocess.run(
            ["pdftotext", "-layout", "-f", str(page), "-l", str(page), str(path), str(out)],
            check=True,
            capture_output=True,
            text=True,
        )
        return _normalize_text(out.read_text(encoding="utf-8", errors="ignore"))


def _normalize_text(value: str) -> str:
    value = value.replace("\x0c", "\n")
    value = re.sub(r"(?<=\d)\s*D\s*P", "DP", value, flags=re.IGNORECASE)
    value = re.sub(r"(?<=\d)\s*P\s*X", "PX", value, flags=re.IGNORECASE)
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def _extract_assets(pages: list[str]) -> list[dict[str, object]]:
    rows = _image_rows(SOURCE_PDF)
    page_sequence: dict[int, int] = defaultdict(int)
    assets: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="bottom-nav-images-") as tmp:
        prefix = Path(tmp) / "image"
        subprocess.run(["pdfimages", "-png", str(SOURCE_PDF), str(prefix)], check=True)
        extracted = sorted(Path(tmp).glob("image-*.png"))
        for index, source in enumerate(extracted):
            row = rows[index] if index < len(rows) else {}
            page = int(row.get("page") or 1)
            page_sequence[page] += 1
            page_title = _page_title(pages[page - 1] if page <= len(pages) else "")
            asset_id = f"bottom-nav-p{page:02d}-{page_sequence[page]:02d}"
            filename = f"{asset_id}.png"
            target = SNIPPET_DIR / filename
            shutil.copyfile(source, target)
            with Image.open(target) as image:
                width, height = image.size
            assets.append(
                {
                    "id": asset_id,
                    "label": f"底部导航栏 · {page_title}",
                    "url": f"/spec-snippets/bottom-nav/{filename}",
                    "source": f"{SOURCE_PDF.name}#page={page}",
                    "width": width,
                    "height": height,
                    "keywords": _keywords(page_title, pages[page - 1] if page <= len(pages) else ""),
                }
            )
    return assets


def _image_rows(path: Path) -> list[dict[str, int]]:
    result = subprocess.run(["pdfimages", "-list", str(path)], check=True, capture_output=True, text=True)
    rows: list[dict[str, int]] = []
    for line in result.stdout.splitlines():
        parts = line.split()
        if not parts or not parts[0].isdigit():
            continue
        rows.append(
            {
                "page": int(parts[0]),
                "width": int(parts[3]),
                "height": int(parts[4]),
            }
        )
    return rows


def _page_title(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    joined = "\n".join(lines)
    for hint in HEADING_HINTS:
        if hint in joined:
            return hint
    for line in lines:
        if line == "导航类-底部导航栏":
            continue
        if len(line) <= 24 and not re.match(r"^[a-z][.、]", line, flags=re.IGNORECASE):
            return line
    return "规范示意图"


def _keywords(page_title: str, page_text: str) -> list[str]:
    values = [
        "导航类",
        "底部导航栏",
        "底导",
        "Tabbar",
        "底部导航",
        page_title,
    ]
    for hint in HEADING_HINTS:
        if hint in page_text:
            values.append(hint)
    for token in ("Agent", "Joy Agent", "灵动岛", "招手", "红点", "数字型", "文字型", "换肤", "Plus", "大促", "iOS26", "Android"):
        if token.lower() in page_text.lower():
            values.append(token)
    return _unique(values)


def _unique(values: list[str] | tuple[str, ...]) -> list[str]:
    output: list[str] = []
    seen = set()
    for value in values:
        text = str(value).strip()
        key = text.lower().replace(" ", "")
        if text and key not in seen:
            seen.add(key)
            output.append(text)
    return output


def _spec_markdown(pages: list[str], assets: list[dict[str, object]]) -> str:
    body = "\n\n".join(_page_section(index, text, assets) for index, text in enumerate(pages, start=1))
    return f"""# 导航类-底部导航栏规范

本规范由 `references/bottom-nav/导航类-底部导航栏.pdf` 入库生成，适用于移动端底部导航栏、Tabbar、Joy Agent 入口、灵动岛运营资源位、底导换肤和多端材质适配的设计审核。

## 通用审核原则

- 仅当被审核图片中出现底部导航栏、Tabbar、底导换肤、Joy Agent 入口、招手引导或灵动岛运营资源位时适用。
- 审核时只依据本文件中的底部导航栏规范，不要套用 JM AI 或 B-design 的色彩、按钮、Agent 任务组件规则。
- 优先检查底导总高、安全区、坑位数量、坑位均分、图标尺寸、文本字数、选中态、营销态、招手位置、灵动岛尺寸和禁放区域。
- DP/PX 尺寸来自规范文本；截图无法确认精确尺寸时写入 `cannot_verify`，不要编造测量值。
- 若问题来自规范文本，`rule_source_type` 填 `pdf_text`；若来自页面示意图归纳，填 `pdf_visual_example`；`rule_source_ref` 标明 PDF 页码或图号。
- 输出建议必须指向具体模块，例如「常规底导」「Agent+底导」「Joy Agent」「灵动岛运营资源位」「底导换肤」。

{body}
"""


def _page_section(page: int, text: str, assets: list[dict[str, object]]) -> str:
    page_assets = [asset for asset in assets if str(asset.get("source") or "").endswith(f"#page={page}")]
    links = "\n".join(f"- {asset['label']}：{asset['url']}" for asset in page_assets)
    title = _page_title(text)
    return f"""## 第 {page} 页：{title}

### 规范文本
{text or "（本页未提取到可用文本，主要依据参考素材判断。）"}

### 参考素材
{links or "- 暂无"}
"""


if __name__ == "__main__":
    raise SystemExit(main())
