#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = ROOT / "references" / "B-design"
SPEC_OUT = ROOT / "references" / "specs" / "b-design.md"
SNIPPET_DIR = ROOT / "assets" / "spec-snippets" / "b-design"
INDEX_OUT = ROOT / "references" / "spec-assets-b-design.json"


@dataclass(frozen=True)
class ComponentSource:
    filename: str
    slug: str
    title: str
    aliases: tuple[str, ...]

    @property
    def path(self) -> Path:
        return SOURCE_DIR / self.filename


COMPONENTS = [
    ComponentSource("任务规划.pdf", "task-planning", "任务规划", ("任务计划", "执行计划", "大纲", "浏览类", "节点类")),
    ComponentSource("任务节点.pdf", "task-node", "任务节点", ("一级节点", "二级节点", "生成链", "节点状态")),
    ComponentSource("数据收集.pdf", "data-collection", "数据收集", ("收集", "搜索", "阅读", "资料", "分析资料")),
    ComponentSource("深度思考.pdf", "deep-thinking", "深度思考", ("思考中", "已完成思考", "已停止思考")),
    ComponentSource("状态栏.pdf", "status-bar", "状态栏", ("底部状态栏", "任务进度", "终止按钮", "进度条")),
    ComponentSource("生成中卡片-代码.pdf", "generating-card-code", "生成中卡片-代码", ("代码", "代码运行", "待确认状态")),
    ComponentSource("生成中卡片-商品卡.pdf", "generating-card-product", "生成中卡片-商品卡", ("商品卡", "商卡", "查看全部")),
    ComponentSource("生成中卡片-图片.pdf", "generating-card-image", "生成中卡片-图片", ("图片生成", "生成图片", "查看全部")),
    ComponentSource("生成中卡片-文件.pdf", "generating-card-file", "生成中卡片-文件", ("文件确认", "文件列表", "文件交互")),
    ComponentSource("生成中卡片-表单.pdf", "generating-card-form", "生成中卡片-表单", ("表单", "单选", "多选", "自定义可编辑")),
    ComponentSource("生成中卡片-表格.pdf", "generating-card-table", "生成中卡片-表格", ("表格", "列表", "超过10条")),
]

HEADING_HINTS = (
    "何时使用",
    "组件构成",
    "组件状态",
    "组件交互",
    "待确认状态",
    "已确认状态",
    "收起状态",
    "生成中",
    "已生成",
    "进行中",
    "已完成",
    "已停止",
    "已终止",
    "生成失败",
    "任务终止",
    "纯信息展示",
    "使用场景示意",
    "窄屏适配",
)


def main() -> int:
    _require_tool("pdfinfo")
    _require_tool("pdftotext")
    _require_tool("pdfimages")
    SPEC_OUT.parent.mkdir(parents=True, exist_ok=True)
    SNIPPET_DIR.mkdir(parents=True, exist_ok=True)
    _clean_generated_snippets()

    all_assets: list[dict[str, object]] = []
    component_sections: list[str] = []
    for component in COMPONENTS:
        if not component.path.exists():
            raise FileNotFoundError(component.path)
        page_count = _page_count(component.path)
        pages = [_page_text(component.path, page) for page in range(1, page_count + 1)]
        assets = _extract_assets(component, pages)
        all_assets.extend(assets)
        component_sections.append(_component_markdown(component, pages, assets))

    SPEC_OUT.write_text(_spec_markdown(component_sections), encoding="utf-8")
    INDEX_OUT.write_text(
        json.dumps({"version": 1, "spec_id": "b-design", "assets": all_assets}, ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote {SPEC_OUT.relative_to(ROOT)}")
    print(f"wrote {INDEX_OUT.relative_to(ROOT)}")
    print(f"wrote {len(all_assets)} snippets under {SNIPPET_DIR.relative_to(ROOT)}")
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
    with tempfile.TemporaryDirectory(prefix="bdesign-text-") as tmp:
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
    value = re.sub(r"(?<=\d)\s+p\s*x", "px", value, flags=re.IGNORECASE)
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def _extract_assets(component: ComponentSource, pages: list[str]) -> list[dict[str, object]]:
    rows = _image_rows(component.path)
    page_sequence: dict[int, int] = defaultdict(int)
    assets: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="bdesign-images-") as tmp:
        prefix = Path(tmp) / "image"
        subprocess.run(["pdfimages", "-png", str(component.path), str(prefix)], check=True)
        extracted = sorted(Path(tmp).glob("image-*.png"))
        for index, source in enumerate(extracted):
            row = rows[index] if index < len(rows) else {}
            page = int(row.get("page") or 1)
            page_sequence[page] += 1
            asset_id = f"b-design-{component.slug}-p{page:02d}-{page_sequence[page]:02d}"
            filename = f"{asset_id}.png"
            target = SNIPPET_DIR / filename
            shutil.copyfile(source, target)
            with Image.open(target) as image:
                width, height = image.size
            page_title = _page_title(component, pages[page - 1] if page <= len(pages) else "")
            assets.append(
                {
                    "id": asset_id,
                    "label": f"{component.title} · {page_title}",
                    "url": f"/spec-snippets/b-design/{filename}",
                    "source": f"{component.filename}#page={page}",
                    "width": width,
                    "height": height,
                    "keywords": _keywords(component, page_title, pages[page - 1] if page <= len(pages) else ""),
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


def _page_title(component: ComponentSource, text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for hint in HEADING_HINTS:
        if hint in lines:
            return hint
    for line in lines:
        if line == component.title:
            continue
        if len(line) <= 18 and not re.match(r"^\d+[、.]", line):
            return line
    return "规范示意图"


def _keywords(component: ComponentSource, page_title: str, page_text: str) -> list[str]:
    values = [
        "B-design",
        "Agent 组件规范",
        component.title,
        *component.aliases,
        page_title,
    ]
    for hint in HEADING_HINTS:
        if hint in page_text:
            values.append(hint)
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


def _component_markdown(
    component: ComponentSource,
    pages: list[str],
    assets: list[dict[str, object]],
) -> str:
    text = "\n\n".join(page for page in pages if page)
    links = "\n".join(
        f"- {asset['label']}：{asset['url']}"
        for asset in assets
    )
    return f"""## {component.title}

### 审核方式
- 仅当被审核图片中出现「{component.title}」或其同类 Agent 组件时适用。
- 优先检查规范文本中的「必有」项、状态文案、展开/收起交互、主次操作和容器高度。
- 规范写明「可选」的元素不能因为缺失直接判定违规；只有业务场景需要但设计缺失时才作为问题。
- 标题加示意图的页面代表该状态或结构的标准视觉参考。没有明确尺寸标注时，不要把示意图中的像素值当作硬性尺寸。

### 规范文本
{text}

### 参考素材
{links or "- 暂无"}
"""


def _spec_markdown(component_sections: list[str]) -> str:
    sections = "\n\n".join(component_sections)
    return f"""# B-design Agent 组件规范

本规范由 `references/B-design/` 中的 PDF 入库生成，适用于 Agent 任务执行、生成中卡片、状态栏、任务规划、任务节点、数据收集和深度思考等组件的设计审核。

## 通用审核原则

- 审核时必须依据本文件中的规范文本，不要套用 JM AI 色彩、按钮、标签等无关规范。
- 标题、内文描述是强规则来源；浅灰底或页面内嵌 UI 图片是规范示意图和案例素材。
- 对只有标题和示意图的页面，按标题识别组件状态，把示意图作为该状态的视觉参考；不要凭视觉图臆造未标注的精确尺寸。
- 对「必有」项，若被审核图片中对应组件缺失该元素，应输出问题和修改建议。
- 对「可选」项，除非业务上下文明确需要，否则不要因为缺失直接判定违规。
- 对状态类组件，重点检查状态文案、状态图标、展开/收起、停止/失败/已完成等状态是否与当前任务阶段一致。
- 对生成中卡片，重点检查卡片标题、补充文案、生成内容、主按钮、次按钮、延展操作区和最大高度。
- 输出修改建议时，应指向具体组件和状态，并优先引用本规范里的组件名称，例如「任务规划」「数据收集」「生成中卡片-表格」。

{sections}
"""


if __name__ == "__main__":
    raise SystemExit(main())
