#!/usr/bin/env python3
"""Generate final architecture presentation PPT for JM AI Design Audit Platform."""

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)

BG_DARK      = RGBColor(0x1A, 0x1A, 0x2E)
BG_CARD      = RGBColor(0x22, 0x22, 0x3A)
BG_CODE      = RGBColor(0x15, 0x15, 0x25)
ACCENT       = RGBColor(0x7B, 0x5C, 0xF0)
ACCENT2      = RGBColor(0x00, 0xD2, 0xA0)
WHITE        = RGBColor(0xFF, 0xFF, 0xFF)
LIGHT_GRAY   = RGBColor(0xBB, 0xBB, 0xCC)
MID_GRAY     = RGBColor(0x88, 0x88, 0xAA)
ORANGE       = RGBColor(0xFF, 0x8C, 0x42)
RED_ACCENT   = RGBColor(0xFF, 0x55, 0x55)
PINK         = RGBColor(0xFF, 0x88, 0xCC)
YELLOW       = RGBColor(0xFF, 0xDD, 0x66)
BG_BAR       = RGBColor(0x20, 0x20, 0x38)
BG_DARK2     = RGBColor(0x25, 0x20, 0x40)

def set_bg(slide, color=BG_DARK):
    slide.background.fill.solid(); slide.background.fill.fore_color.rgb = color

def card(slide, l, t, w, h, color=BG_CARD):
    s = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, l, t, w, h)
    s.fill.solid(); s.fill.fore_color.rgb = color; s.line.fill.background(); s.shadow.inherit = False
    return s

def txt(slide, l, t, w, h, text, sz=14, color=WHITE, bold=False, align=PP_ALIGN.LEFT, name="Microsoft YaHei"):
    b = slide.shapes.add_textbox(l, t, w, h); tf = b.text_frame; tf.word_wrap = True
    p = tf.paragraphs[0]; p.text = text; p.font.size = Pt(sz); p.font.color.rgb = color; p.font.bold = bold; p.font.name = name; p.alignment = align
    return b

def bullets(slide, l, t, w, h, items, sz=13, color=LIGHT_GRAY, sp=Pt(6), name="Microsoft YaHei"):
    b = slide.shapes.add_textbox(l, t, w, h); tf = b.text_frame; tf.word_wrap = True
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = item; p.font.size = Pt(sz); p.font.color.rgb = color; p.font.name = name; p.space_after = sp
    return b

def tag(slide, l, t, text, color=ACCENT):
    s = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, l, t, Inches(1.3), Inches(0.3))
    s.fill.solid(); s.fill.fore_color.rgb = color; s.line.fill.background()
    tf = s.text_frame; tf.word_wrap = False; tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]; p.text = text; p.font.size = Pt(10); p.font.color.rgb = WHITE; p.font.bold = True; p.font.name = "Microsoft YaHei"; p.alignment = PP_ALIGN.CENTER

def code_block(slide, l, t, w, h, text, sz=8):
    s = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, l, t, w, h)
    s.fill.solid(); s.fill.fore_color.rgb = BG_CODE; s.line.color.rgb = RGBColor(0x33, 0x33, 0x50); s.line.width = Pt(0.5)
    tf = s.text_frame; tf.word_wrap = True; tf.vertical_anchor = MSO_ANCHOR.TOP
    for i, line in enumerate(text.split("\n")):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = line; p.font.size = Pt(sz); p.font.color.rgb = ACCENT2; p.font.name = "Consolas"; p.space_after = Pt(1)

def info_card(slide, l, t, w, h, title, items, tag_color=ACCENT, tag_text="", title_sz=14, item_sz=11):
    card(slide, l, t, w, h)
    if tag_text: tag(slide, l+Inches(0.15), t+Inches(0.1), tag_text, tag_color); ty = t+Inches(0.5)
    else: ty = t+Inches(0.15)
    txt(slide, l+Inches(0.15), ty, w-Inches(0.3), Inches(0.35), title, sz=title_sz, color=WHITE, bold=True)
    bullets(slide, l+Inches(0.15), ty+Inches(0.35), w-Inches(0.3), h-Inches(0.6), items, sz=item_sz, color=LIGHT_GRAY, sp=Pt(4))

def cover(title, sub="", sub2=""):
    s = prs.slides.add_slide(prs.slide_layouts[6]); set_bg(s)
    bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(3.2), Inches(13.333), Inches(0.06))
    bar.fill.solid(); bar.fill.fore_color.rgb = ACCENT; bar.line.fill.background()
    txt(s, Inches(1), Inches(1.5), Inches(11), Inches(1.5), title, sz=36, color=WHITE, bold=True, align=PP_ALIGN.CENTER)
    if sub: txt(s, Inches(1), Inches(3.5), Inches(11), Inches(0.8), sub, sz=18, color=LIGHT_GRAY, align=PP_ALIGN.CENTER)
    if sub2: txt(s, Inches(1), Inches(4.3), Inches(11), Inches(0.5), sub2, sz=14, color=MID_GRAY, align=PP_ALIGN.CENTER)
    return s

def section(title):
    s = prs.slides.add_slide(prs.slide_layouts[6]); set_bg(s)
    bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(3.3), Inches(13.333), Inches(0.04))
    bar.fill.solid(); bar.fill.fore_color.rgb = ACCENT; bar.line.fill.background()
    txt(s, Inches(1), Inches(2.0), Inches(11), Inches(1.2), title, sz=32, color=WHITE, bold=True, align=PP_ALIGN.CENTER)
    return s

def content(title, sub=""):
    s = prs.slides.add_slide(prs.slide_layouts[6]); set_bg(s)
    bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(13.333), Inches(0.9))
    bar.fill.solid(); bar.fill.fore_color.rgb = BG_BAR; bar.line.fill.background()
    txt(s, Inches(0.6), Inches(0.15), Inches(8), Inches(0.6), title, sz=22, color=WHITE, bold=True)
    if sub: txt(s, Inches(8.5), Inches(0.2), Inches(4.5), Inches(0.5), sub, sz=11, color=MID_GRAY, align=PP_ALIGN.RIGHT)
    return s

# ═══════════════════════════════════════
# S1: COVER
# ═══════════════════════════════════════
cover("JM AI 设计规范审核平台",
       "架构设计与技术方案汇报",
       "LLM + Agent + Skill + MOE + Harness + Data Flywheel")

# ═══════════════════════════════════════
# S2: AGENDA
# ═══════════════════════════════════════
s = content("汇报提纲", "Agenda")
for i, (num, title, desc) in enumerate([
    ("01", "知识库模块", "规范知识工程 + 素材自动化分析管线 + 跨场景扩展架构"),
    ("02", "分析模块 · MOE 系统", "双层 MOE：跨模型集成(GPT+Kimi) + 单模型内多专家路由"),
    ("03", "分析模块 · 工具系统", "Agent 化证据工具链 + 规则引擎 Harness + 安全校验"),
    ("04", "数据沉淀与飞轮", "分层存储 + 全链路追溯 + 数据飞轮：每轮任务反哺精度"),
    ("05", "架构全景与设计模式", "7 层架构 · LLM/Agent/Skill/Harness 概念融合"),
]):
    y = Inches(1.3) + Inches(1.1) * i
    txt(s, Inches(0.8), y, Inches(0.5), Inches(0.5), num, sz=20, color=ACCENT, bold=True)
    txt(s, Inches(1.5), y, Inches(2.8), Inches(0.4), title, sz=16, color=WHITE, bold=True)
    txt(s, Inches(4.5), y+Inches(0.05), Inches(8), Inches(0.4), desc, sz=12, color=LIGHT_GRAY)

# ═══════════════════════════════════════
# MODULE 1: 知识库
# ═══════════════════════════════════════
section("模块一：知识库模块（Knowledge Base）")

# ── 1-1 ──
s = content("知识库模块 · 规范知识工程", "Design Spec Knowledge Engineering")
txt(s, Inches(0.6), Inches(1.1), Inches(12), Inches(0.4),
    "将 JM AI 设计规范从静态文档转化为可被 LLM Agent 和规则引擎消费的结构化知识体系",
    sz=16, color=ACCENT2, bold=True)
info_card(s, Inches(0.4), Inches(1.7), Inches(4), Inches(2.5),
    "① 设计规范文本化",
    ["完整规范 .md：色彩/字体/间距/按钮/标签/图标/Header",
     "19 个 JM AI 色彩 Token 库(#7B5CF0 等紫色系)",
     "间距 Token 体系(4/8/12/16/24/32/48px)",
     "Type Token 体系(字号/字重/行高)"],
    tag_color=ACCENT, tag_text="规范工程")
info_card(s, Inches(4.6), Inches(1.7), Inches(4), Inches(2.5),
    "② 三级 Prompt Skill 体系",
    ["Full Skill: 完整规范注入，无输出限制",
     "Light Skill: 核心规则摘要，最多 8 个 issues",
     "Kimi Compact Skill: 紧凑版(≤60字)，最多 5 个",
     "Prompt + Schema 双版本号追踪"],
    tag_color=ORANGE, tag_text="Skill 体系")
info_card(s, Inches(8.8), Inches(1.7), Inches(4.2), Inches(2.5),
    "③ 标准分类体系",
    ["10 大标准分类：品牌/色彩/字体/间距/组件/图标等",
     "别名表 + token 交集 + 中文关键词三重归一",
     "二级子分类：off_token_color 等细粒度标签"],
    tag_color=ACCENT2, tag_text="Taxonomy")

code_block(s, Inches(0.4), Inches(4.5), Inches(6.2), Inches(2.5),
    "# prompt_builder.py — 三级 Prompt Skill 策略\n\n"
    "def build_audit_prompt(spec_text, ...):      # jm-audit-full\n"
    "    return (\n"
    "        '你是 JM AI 设计规范审核助手。'\n"
    "        '必须覆盖色彩/字体/间距/按钮/标签/图标/Header...'\n"
    "        + spec_text)\n\n"
    "def build_light_audit_prompt(...):           # jm-audit-light\n"
    "    return ('核心规则摘要...最多输出 8 个 issues')\n\n"
    "def build_kimi_light_audit_prompt(...):      # jm-kimi-compact\n"
    "    return ('只输出紧凑 JSON...最多 5 个 issues, ≤60 字')", sz=9)

code_block(s, Inches(6.8), Inches(4.5), Inches(6.2), Inches(2.5),
    "# audit_taxonomy.py — 10 大分类 + 三重归一\n\n"
    "CATEGORY_LABELS = {\n"
    "    'color_gradient': '色彩与渐变',\n"
    "    'typography': '字体与文本',\n"
    "    'spacing_layout': '间距与布局',\n"
    "    'component_spec': '组件规范',\n"
    "    'icon_ai_mark': '图标与 AI 标识',\n"
    "    # ... 共 10 类\n"
    "}\n\n"
    "def normalize_category(value):\n"
    "    if key in CATEGORY_ALIASES:  # 别名直配\n"
    "        return CATEGORY_ALIASES[key]\n"
    "    # 模糊匹配兜底: token 交集 + 中文关键词\n"
    "    if tokens & english_tokens or cjk in raw:\n"
    "        return category\n"
    "    return 'content_hierarchy'", sz=9)

# ── 1-2 素材自动化分析 ──
s = content("知识库模块 · 素材自动化分析管线", "Automated Material Analysis Pipeline")
txt(s, Inches(0.6), Inches(1.1), Inches(12), Inches(0.4),
    "从原始素材到结构化知识库 —— 自动化管线替代人工整理，一键摄入多格式设计资产",
    sz=15, color=ACCENT2, bold=True)

info_card(s, Inches(0.4), Inches(1.7), Inches(3.0), Inches(5.0),
    "① 多格式摄入",
    ["支持格式：",
     "  PDF（设计规范文档）",
     "  PNG/JPG（设计稿截图）",
     "  SVG（图标/组件素材）",
     "  MD/HTML（文本规范）",
     "  Sketch/Figma 导出切片",
     "",
     "输入自动分类器：",
     "  根据 MIME type + 文件名规则路由"],
    tag_color=ACCENT, tag_text="摄入层", item_sz=10)

info_card(s, Inches(3.6), Inches(1.7), Inches(3.2), Inches(5.0),
    "② 智能解析引擎",
    ["PDF 解析：",
     "  PyMuPDF 提取文本层",
     "  PaddleOCR 识别扫描件文字",
     "  表格结构还原",
     "",
     "图片解析：",
     "  自动裁切留白边缘",
     "  组件区域检测",
     "  颜色采样点自动标注",
     "",
     "LLM 辅助提取：",
     "  DocReader → RuleExtractor",
     "  → Validator → Indexer"],
    tag_color=ORANGE, tag_text="解析层", item_sz=10)

info_card(s, Inches(7.0), Inches(1.7), Inches(3.0), Inches(5.0),
    "③ 结构化入库",
    ["知识库 Schema：",
     "  spec_assets 表：素材 ID、",
     "  类型、存储路径、标签",
     "  color_tokens 表：Token 名、",
     "  HEX、RGB、用途分类",
     "  spacing_tokens 表：Token 值、",
     "  适用场景",
     "  typography_tokens 表：字号、",
     "  字重、行高",
     "",
     "JSON 索引自动生成",
     "  (spec-assets.json)"],
    tag_color=ACCENT2, tag_text="存储层", item_sz=10)

info_card(s, Inches(10.2), Inches(1.7), Inches(2.8), Inches(5.0),
    "④ LLM Agent 知识提取",
    ["编排流程：",
     "  1. Doc Reader Agent",
     "     → 文本分段",
     "  2. Rule Extractor Agent",
     "     → 抽取规则",
     "  3. Validator Agent",
     "     → 交叉校验",
     "  4. Indexer Agent",
     "     → 关键词索引",
     "",
     "输出：",
     "  spec-text.md",
     "  spec-assets.json",
     "  color-tokens.json",
     "  spacing-tokens.json"],
    tag_color=RED_ACCENT, tag_text="Agent 编排", item_sz=10)

# ── 1-3 扩展性 ──
s = content("知识库模块 · 跨场景扩展架构", "Extensibility — Build Once, Extend Everywhere")
txt(s, Inches(0.6), Inches(1.1), Inches(12), Inches(0.4),
    "核心不是「一个知识库」，而是一套「自动化处理流程和规范框架」—— 可无缝复制到任意场景",
    sz=15, color=ACCENT2, bold=True)

info_card(s, Inches(0.4), Inches(1.7), Inches(6.2), Inches(2.5),
    "扩展路径：替换知识层，复用流程层",
    ["当前(JM AI) → 新品牌接入只需替换：",
     "",
     "  input/               ← 新品牌设计规范素材",
     "  color_tokens.json    ← 新品牌色板",
     "  spacing_tokens.json  ← 新品牌间距",
     "  spec_text.md         ← 新品牌规范文本",
     "",
     "流程层完全复用：解析管线 → Prompt Skill → 规则引擎 → 融合逻辑 → 报告模板"],
    tag_color=ACCENT, tag_text="扩展机制")

info_card(s, Inches(6.8), Inches(1.7), Inches(6.2), Inches(2.5),
    "可扩展应用场景",
    ["多品牌设计规范审核：JD React / Taro / NutUI 等任意组件库",
     "跨平台 UI 自动化检测：移动端 App / 小程序 / Web / 后台系统",
     "无障碍合规审核：接入 WCAG 2.1，自动检测对比度",
     "国际化规范适配：替换 Prompt Language + 规范文本语言包"],
    tag_color=ORANGE, tag_text="应用场景")

info_card(s, Inches(0.4), Inches(4.5), Inches(6.2), Inches(2.5),
    "知识库即代码 + Skill 化封装",
    ["所有知识库内容以文件管理，可 Git 版本控制",
     "每次规范更新 → PR 提交 → CI 自动重新生成 Prompt",
     "Skill 化封装：每个专家知识封装为独立 Skill",
     "  jm-color.skill / jm-spacing.skill / jm-typography.skill / jm-components.skill",
     "新品牌 = 新 Skill 集 = 新知识库 + 规则配置"],
    tag_color=ACCENT2, tag_text="GitOps + Skill")

code_block(s, Inches(6.8), Inches(4.5), Inches(6.2), Inches(2.5),
    "# 跨场景复用的能力: 替换知识源即可\n\n"
    "知识库目录结构（可 Git 管理）:\n"
    "  references/\n"
    "  ├── jm-ai-design-spec.md      # 规范文本\n"
    "  ├── spec-assets.json          # 素材索引\n"
    "  ├── color_tokens.json         # 色彩 Token\n"
    "  ├── spacing_tokens.json       # 间距 Token\n"
    "  └── spec-images/              # 规范素材图\n\n"
    "# 切换品牌 = 替换 references/ 目录内容\n"
    "# 零代码修改，全流程复用", sz=9)


# ═══════════════════════════════════════
# MODULE 2: MOE
# ═══════════════════════════════════════
section("模块二：分析模块 · 双层 MOE 系统（Mixture of Agents）")

# ── 2-1 双层架构总览 ──
s = content("MOE 系统 · 双层架构总览", "Two-Level Mixture of Experts / Agents")
txt(s, Inches(0.6), Inches(1.1), Inches(12), Inches(0.4),
    "两个 MOE 层面互为补充：跨模型集成降低漏检率，单模型专家路由提升分析深度",
    sz=15, color=ACCENT2, bold=True)

card(s, Inches(0.4), Inches(1.6), Inches(12.5), Inches(2.7), BG_DARK2)
txt(s, Inches(0.6), Inches(1.7), Inches(12), Inches(0.3),
    "Level 1：跨模型集成 MOE（Cross-Model Ensemble）", sz=16, color=ACCENT, bold=True)
code_block(s, Inches(0.5), Inches(2.1), Inches(12.3), Inches(2.1),
    "┌─────────────────────────────────────────────────────────────────────────┐\n"
    "│                    Task Runner (Orchestration Harness)                  │\n"
    "│  ┌──────────────────────────┐    ┌─────────────────────────────────┐   │\n"
    "│  │   GPT-5.5 Agent          │    │   Kimi-K2.6 Agent               │   │\n"
    "│  │   (Primary Expert)       │    │   (Candidate Expert)            │   │\n"
    "│  │   Skill: full / light    │    │   Skill: kimi-compact           │   │\n"
    "│  └──────────┬───────────────┘    └──────────┬──────────────────────┘   │\n"
    "│             │ issues[]                       │ issues[]                 │\n"
    "│             └──────────────┬─────────────────┘                        │\n"
    "│                            ▼                                           │\n"
    "│                  Fusion Engine (merge_primary_with_candidates)          │\n"
    "│                  ├─ IoU + 文本相似度匹配                               │\n"
    "│                  ├─ 严重度取高 / bbox 取小 / 描述取长                  │\n"
    "│                  └─ agreement: both / gpt_only / kimi_only             │\n"
    "└─────────────────────────────────────────────────────────────────────────┘", sz=8)

card(s, Inches(0.4), Inches(4.5), Inches(12.5), Inches(2.5), BG_DARK2)
txt(s, Inches(0.6), Inches(4.6), Inches(12), Inches(0.3),
    "Level 2：单模型内多专家路由（Intra-Model Expert Routing）", sz=16, color=ACCENT, bold=True)
code_block(s, Inches(0.5), Inches(5.0), Inches(12.3), Inches(1.9),
    "┌────────────────────────────────────────────────────────────────────┐\n"
    "│                       同一个 LLM Instance                          │\n"
    "│                              │                                     │\n"
    "│                   截图 ──→ Router(分类调度器)                       │\n"
    "│                              │                                     │\n"
    "│           ┌──────────────────┼──────────────┬──────────────┐       │\n"
    "│           ▼                  ▼              ▼              ▼       │\n"
    "│   ┌─────────────┐   ┌─────────────┐ ┌────────────┐ ┌────────────┐ │\n"
    "│   │  色彩专家    │   │  布局专家    │ │  组件专家   │ │  图标专家   │ │\n"
    "│   │jm-color     │   │jm-spacing   │ │jm-component│ │jm-icon     │ │\n"
    "│   │.audit.skill │   │.audit.skill │ │.audit.skill│ │.audit.skill│ │\n"
    "│   └──────┬──────┘   └──────┬──────┘ └──────┬─────┘ └──────┬─────┘ │\n"
    "│          │color_issues     │spacing_issues │comp_issues   │icon_is │\n"
    "│          └─────────────────┴───────────────┴──────────────┘        │\n"
    "│                               ▼                                    │\n"
    "│                    Expert Aggregator (汇总去重)                     │\n"
    "└────────────────────────────────────────────────────────────────────┘", sz=8)

# ── 2-2 Level 1 跨模型 MOE ──
s = content("Level 1：跨模型集成 MOE", "Cross-Model Ensemble — GPT-5.5 + Kimi-K2.6")
txt(s, Inches(0.6), Inches(1.1), Inches(12), Inches(0.4),
    "两个独立模型作为不同 Agent，并行审核后通过确定性融合引擎合并结果",
    sz=15, color=ACCENT2, bold=True)

info_card(s, Inches(0.4), Inches(1.7), Inches(6.2), Inches(2.5),
    "Agent 化设计 + Harness 编排",
    ["GPT-5.5 Agent（主审专家）Skill: jm-audit-full/light",
     "Kimi-K2.6 Agent（复审专家）Skill: jm-audit-kimi-compact",
     "每个 Agent 拥有独立 Prompt Skill + Tool 调用权限",
     "",
     "Harness 编排协议（容错降级）：",
     "  1. GPT OK + Kimi OK → 完整融合",
     "  2. GPT OK + Kimi Fail → 降级 GPT 单模型",
     "  3. GPT Fail + Kimi OK → 降级 Kimi 单模型",
     "  4. Both Fail → 任务失败",
     "每次失败记录 error_type + retriable 标记"],
    tag_color=ACCENT, tag_text="Agent + Harness")

code_block(s, Inches(6.8), Inches(1.7), Inches(6.2), Inches(5.2),
    "# task_runner.py — Harness 编排核心代码\n\n"
    "def _dual_auditor(settings, declared_screen_size=None):\n"
    "    spec_text = SPEC_PATH.read_text(encoding='utf-8')\n"
    "    client = OpenAI(api_key=settings.audit_api_key,\n"
    "                    base_url=settings.audit_base_url)\n\n"
    "    def audit(image_path, artifact_dir, scale_context=None):\n"
    "        attempts: list[dict[str, Any]] = []\n\n"
    "        # 遍历两个 Agent: GPT-5.5, Kimi-K2.6\n"
    "        for index, model in enumerate(\n"
    "                settings.audit_models, start=1):\n"
    "            try:\n"
    "                # 选取对应 Skill\n"
    "                chat_audit = _jdcloud_model_audit(\n"
    "                    settings, model)\n"
    "                # Agent 执行\n"
    "                result = chat_audit(\n"
    "                    client, model, image_path, spec_text,\n"
    "                    reasoning_effort=settings\n"
    "                        .audit_reasoning_effort)\n"
    "                # 写入原始输出(可追溯)\n"
    "                write_json(\n"
    "                    artifact_dir\n"
    "                    f'/audit-{index:02d}-{model_slug}.json',\n"
    "                    result)\n"
    "                attempts.append(\n"
    "                    {'model': model, 'audit': result})\n"
    "            except Exception as exc:\n"
    "                # 独立容错: 一个失败不影响另一个\n"
    "                failure = model_failure(model, exc)\n"
    "                write_json(\n"
    "                    artifact_dir\n"
    "                    f'/audit-{index:02d}'\n"
    "                    f'-{model_slug}-failure.json',\n"
    "                    failure)\n"
    "                attempts.append(failure)\n\n"
    "        # Fusion Engine 执行融合\n"
    "        primary = attempts[0]\n"
    "        if isinstance(primary.get('audit'), dict):\n"
    "            return merge_primary_with_candidates(\n"
    "                primary, attempts[1:])\n"
    "        # 降级路径\n"
    "        return merge_audit_attempts(attempts)\n\n"
    "    return audit", sz=8)

# ── 2-3 融合引擎 ──
s = content("Level 1 · 融合引擎核心算法", "Fusion Engine — Deterministic Rule-Based Merging")
txt(s, Inches(0.6), Inches(1.1), Inches(12), Inches(0.4),
    "不依赖第三方仲裁模型，所有融合在本地通过 IoU + 文本相似度完成",
    sz=15, color=ACCENT2, bold=True)

info_card(s, Inches(0.4), Inches(1.7), Inches(6.2), Inches(2.5),
    "问题匹配算法（_issue_match_score）",
    ["步骤 1 — 冲突阻断：",
     "  位置冲突(「左上」vs「右下」) → 得分 0",
     "  分类冲突(颜色 vs 间距) → 得分 0",
     "",
     "步骤 2 — bbox 相关匹配：",
     "  计算 IoU(Intersection over Union)",
     "  IoU ≥ 0.2 → 继续匹配",
     "  得分 = 0.75 + 对象相似度(≤0.2) + 语义相似度(≤0.05)",
     "",
     "步骤 3 — 无 bbox 文本匹配：",
     "  最长公共子串 ≥ 4 字符 → 锚点分",
     "  文本相似度 ≥ 0.18 → 语义分",
     "  综合 ≥ 0.65 → 视为同一问题"],
    tag_color=ACCENT, tag_text="匹配算法")

info_card(s, Inches(6.8), Inches(1.7), Inches(6.2), Inches(2.5),
    "问题融合策略（_merge_issue_into）",
    ["▸ 严重度取高：GPT 判「中」+ Kimi 判「高」→「高」",
     "  确保高风险问题不被低估",
     "",
     "▸ Bbox 取面积小：100x50 vs 60x30 → 选 60x30",
     "  定位越精准越好",
     "",
     "▸ 文本描述取长：「颜色偏差」(4字)",
     "  vs「顶部主按钮使用了明显偏离主色的蓝色」(24字)",
     "  → 选 24 字版本",
     "",
     "▸ Agreement 标签体系：",
     "  both / gpt_only / kimi_only / promoted_candidate"],
    tag_color=ORANGE, tag_text="融合策略")

code_block(s, Inches(0.4), Inches(4.4), Inches(6.2), Inches(2.6),
    "# audit_merge.py — 问题匹配核心实现\n\n"
    "def _issue_match_score(left, right):\n"
    "    # 冲突阻断\n"
    "    if _side_conflict(left, right):\n"
    "        return 0.0   # 左上 vs 右下\n"
    "    if _issue_kind_conflict(left, right):\n"
    "        return 0.0   # 颜色 vs 间距\n\n"
    "    left_bbox = _bbox(left.get('bbox'))\n"
    "    right_bbox = _bbox(right.get('bbox'))\n\n"
    "    # 有 bbox → IoU 匹配\n"
    "    if left_bbox and right_bbox:\n"
    "        if not _bbox_related(left_bbox, right_bbox):\n"
    "            return 0.0   # IoU < 0.2\n"
    "        score = (0.75\n"
    "            + min(object_score, 0.2)\n"
    "            + min(semantic_score, 0.05))\n"
    "        return score\n\n"
    "    # 无 bbox → 文本语义匹配\n"
    "    if anchor_score >= 0.6 and object_score >= 0.18:\n"
    "        return 0.8 + min(object_score, 0.15)\n"
    "    if object_score >= 0.3 and (category_match\n"
    "            or semantic_score >= 0.12):\n"
    "        return 0.72 + min(semantic_score, 0.08)\n"
    "    return 0.0", sz=8)

code_block(s, Inches(6.8), Inches(4.4), Inches(6.2), Inches(2.6),
    "# audit_merge.py — 融合策略实现\n\n"
    "def _merge_issue_into(target, source):\n"
    "    # 严重度取高\n"
    "    target['severity'] = _higher_severity(\n"
    "        target.get('severity'),\n"
    "        source.get('severity'))\n\n"
    "    # bbox 取面积小\n"
    "    target['bbox'] = _choose_bbox(\n"
    "        target.get('bbox'),\n"
    "        source.get('bbox'))\n\n"
    "    # 文本字段取长\n"
    "    FIELDS = ['current_observation',\n"
    "              'spec_expectation',\n"
    "              'recommendation',\n"
    "              'location']\n"
    "    for field in FIELDS:\n"
    "        target[field] = _longer_text(\n"
    "            target.get(field),\n"
    "            source.get(field))\n\n"
    "    # 补充 target 缺失的字段\n"
    "    for key, value in source.items():\n"
    "        if key not in target and key != '_source_models':\n"
    "            target[key] = value", sz=8)

# ── 2-4 端到端案例 ──
s = content("Level 1 · 端到端融合案例", "End-to-End Example — Button Color Violation")
card(s, Inches(0.4), Inches(1.1), Inches(12.5), Inches(2.6))
bullets(s, Inches(0.6), Inches(1.2), Inches(12), Inches(2.4), [
    "场景：审核「邀好友赚套餐」营销按钮颜色是否偏离 JM AI 规范",
    "",
    "GPT-5.5 发现：该按钮使用橙色到红色的醒目渐变 → 严重度: 中，bbox: [2586, 20, 216, 56]",
    "Kimi-K2.6 发现1：「邀好友赚套餐」按钮使用橙色填充背景 → 严重度: 高，bbox: [2623, 29, 220, 50]",
    "Kimi-K2.6 发现2：品牌徽标未使用 JM AI 紫色 → 严重度: 中（GPT 未发现此问题）",
    "",
    "融合结果：",
    "  ✅ 问题1（双方一致确认）→ severity: 高(取Kimi)，bbox: [2623,29,220,50](面积更小)",
    "     描述保留 GPT 原文(更详细)，source_models: [GPT-5.5, Kimi-K2.6]，agreement: promoted_candidate",
    "  📋 问题2（待人工复核）→ 品牌区问题 → review_candidates，source_model: Kimi-K2.6",
], sz=11, sp=Pt(3))

code_block(s, Inches(0.4), Inches(3.9), Inches(6.2), Inches(3.0),
    "# 融合后的 issue JSON 结构\n\n"
    "{\n"
    "  'id': '问题-001',\n"
    "  'category': '色彩与渐变',\n"
    "  'severity': '高',  # 从 Kimi(更严格)\n"
    "  'current_observation': '该按钮使用'\n"
    "      '橙色到红色的醒目渐变...',  # 从 GPT(更长)\n"
    "  'bbox': [2623, 29, 220, 50],  # 面积更小\n"
    "  'agreement': 'promoted_candidate',\n"
    "  'source_models': ['GPT-5.5', 'Kimi-K2.6'],\n"
    "  'rule_sources': ['model', 'color_sample'],\n"
    "  # 规则引擎也验证了这个颜色偏离\n"
    "}", sz=9)

code_block(s, Inches(6.8), Inches(3.9), Inches(6.2), Inches(3.0),
    "# test_audit_merge.py — 融合测试验证\n\n"
    "def test_merge_primary_with_candidates():\n"
    "    primary = _audit('GPT-5.5', [\n"
    "        severity:'中', bbox:[2586,20,216,56]])\n"
    "    candidate = _audit('Kimi-K2.6', [\n"
    "        severity:'高', bbox:[2623,29,220,50],\n"
    "        severity:'中'  # 不匹配 → review\n"
    "    ])\n\n"
    "    result = merge_primary_with_candidates(\n"
    "        primary, candidate)\n\n"
    "    assert len(result['issues']) == 1\n"
    "    assert result['issues'][0]['severity'] == '高'\n"
    "    assert result['issues'][0]['agreement'] \\\n"
    "        == 'promoted_candidate'\n"
    "    assert len(result['model_comparison']\n"
    "        ['review_candidates']) == 1", sz=9)

# ── 2-5 Level 2 多专家路由 ──
s = content("Level 2：单模型内多专家路由", "Intra-Model Expert Routing — Mixture of Skills")
txt(s, Inches(0.6), Inches(1.1), Inches(12), Inches(0.4),
    "同一个模型内按技能领域路由到不同 Expert Skill —— 每个专家专注于一个维度的深度分析",
    sz=15, color=ACCENT2, bold=True)

experts = [
    ("色彩专家", ACCENT, ["Skill: jm-color-audit",
     "专注：品牌色/渐变方向/色彩 Token 合规/对比度",
     "输出：color_issues + sample_points 采样点坐标"]),
    ("布局/间距专家", ORANGE, ["Skill: jm-spacing-audit",
     "专注：间距 Token/组件对齐/内边距/布局密度",
     "输出：spacing_issues + regions + distances"]),
    ("组件专家", ACCENT2, ["Skill: jm-component-audit",
     "专注：按钮/标签/表单/卡片/Dialog",
     "输出：component_issues + 二级子分类"]),
    ("图标专家", RED_ACCENT, ["Skill: jm-icon-audit",
     "专注：AI 闪光标/图标语义/品牌徽标/状态标记",
     "输出：icon_issues + bbox 定位每个图标"]),
    ("字体专家", PINK, ["Skill: jm-typography-audit",
     "专注：字号 Token/字重/行高/文本层级",
     "输出：type_issues + 文本区域"]),
    ("总体专家", YELLOW, ["Skill: jm-overall-audit",
     "全局视角：页面整体感知/Header 层级/商业入口",
     "输出：overall_conclusion + 全局问题"]),
]
for i, (name, c, items) in enumerate(experts):
    col, row = i % 3, i // 3
    info_card(s, Inches(0.4)+Inches(4.3)*col, Inches(1.7)+Inches(2.5)*row, Inches(4.0), Inches(2.2),
        name, items, tag_color=c, tag_text="Expert", item_sz=10)

# ── 2-6 Expert Skill 案例 ──
s = content("Level 2 · Expert Skill Prompt 案例", "Expert Skill Prompt Templates")
code_block(s, Inches(0.4), Inches(1.1), Inches(6.2), Inches(3.0),
    "# jm-color-audit.skill — 色彩专家 Prompt\n\n"
    "def build_color_expert_prompt(...):\n"
    "    return '''你是一位 JM AI 色彩规范专家。\n"
    "专注检查以下内容：\n"
    "1. 主按钮/选中态是否使用了 JM AI\n"
    "   紫色(#7B5CF0)系\n"
    "2. 营销入口是否使用了非规范强调色\n"
    "   (橙色/红色/绿色等)\n"
    "3. 渐变方向是否符合 AI 渐变规范\n"
    "4. 图标/标签/徽章颜色是否偏离\n\n"
    "输出要求：\n"
    "  category = 'color_gradient'\n"
    "  severity = '高'/'中'/'低'\n"
    "  bbox = [x, y, w, h]\n"
    "  sample_points = [{'label':'SP-001',\n"
    "    'x':100, 'y':200}]  # 颜色分析请求\n"
    "'''", sz=8)

code_block(s, Inches(6.8), Inches(1.1), Inches(6.2), Inches(3.0),
    "# jm-spacing-audit.skill — 布局专家 Prompt\n\n"
    "def build_spacing_expert_prompt(...):\n"
    "    return '''你是一位 JM AI 间距/布局专家。\n"
    "专注检查以下内容：\n"
    "1. 卡片内边距是否符合间距 Token\n"
    "   (4/8/12/16/24/32/48px)\n"
    "2. 组件之间的间距是否一致\n"
    "3. 表单/列表的布局密度是否合理\n\n"
    "输出要求：\n"
    "  category = 'spacing_layout'\n"
    "  regions = [{'label':'主按钮区域',\n"
    "    'bbox':[x,y,w,h]}]  # 测量区域请求\n"
    "  distances = [{'from':'标题','to':'按钮',\n"
    "    'expected':24}]  # 间距测量请求\n"
    "'''", sz=8)

code_block(s, Inches(0.4), Inches(4.3), Inches(6.2), Inches(2.7),
    "# jm-component-audit.skill — 组件专家 Prompt\n\n"
    "def build_component_expert_prompt(...):\n"
    "    return '''你是一位 JM AI 组件规范专家。\n"
    "专注检查以下内容：\n"
    "1. 按钮样式：形状/圆角/填充色/悬停态/禁用态\n"
    "2. 标签形态：胶囊型/圆角矩形/文字标签\n"
    "3. 表单元素：输入框/选择器/开关/滑块\n"
    "4. Dialog/Toast/BottomSheet 等临时组件\n\n"
    "输出要求：\n"
    "  category = 'component_spec'\n"
    "  subcategory 精确到二级分类\n"
    "  (如 button_wrong_style)\n"
    "'''", sz=8)

code_block(s, Inches(6.8), Inches(4.3), Inches(6.2), Inches(2.7),
    "# jm-icon-audit.skill — 图标专家 Prompt\n\n"
    "def build_icon_expert_prompt(...):\n"
    "    return '''你是一位 JM AI 图标/AI 标识专家。\n"
    "专注检查以下内容：\n"
    "1. AI 闪光标的样式/位置/颜色\n"
    "2. 功能图标是否使用规范线框风格\n"
    "3. 品牌徽标大小/位置/颜色\n"
    "4. 状态标记(勾选/警告等)颜色是否偏离\n\n"
    "输出要求：\n"
    "  category = 'icon_ai_mark'\n"
    "  使用 bbox 精确定位每个图标的位置\n"
    "'''", sz=8)

# ═══════════════════════════════════════
# MODULE 2b: 工具系统
# ═══════════════════════════════════════
section("模块二：分析模块 · Agent 工具系统（Tool System）")

s = content("工具系统 · Agent Tool 体系", "Agent Tools + Rule Engine Harness + Bbox Validator")
txt(s, Inches(0.6), Inches(1.1), Inches(12), Inches(0.4),
    "LLM 做发现 → Agent Tool 做验证 → Rule Engine Harness 做兜底：本地确定性校验补足 AI 不可靠",
    sz=15, color=ACCENT2, bold=True)

info_card(s, Inches(0.4), Inches(1.7), Inches(4), Inches(2.5),
    "① 颜色分析 Tool",
    ["Tool 名称: color_sampler",
     "脚本: analyze_image_tokens.py",
     "调用: subprocess(独立进程/独立内存)",
     "▸ 提取采样点精确 HEX 色值",
     "▸ 匹配 19 个 JM AI 色彩 Token",
     "▸ 计算 Delta E 色差距离",
     "▸ 输出: tokens.json"],
    tag_color=ACCENT, tag_text="Tool")

info_card(s, Inches(4.6), Inches(1.7), Inches(4), Inches(2.5),
    "② 区域测量 Tool",
    ["Tool 名称: region_measurer",
     "脚本: measure_regions.py",
     "调用: subprocess(独立进程/独立内存)",
     "▸ 测量 UI 元素间距/内边距",
     "▸ 匹配间距 Token 体系",
     "▸ 1px 容差容忍判断",
     "▸ 输出: measurements.json"],
    tag_color=ORANGE, tag_text="Tool")

info_card(s, Inches(8.8), Inches(1.7), Inches(4.2), Inches(2.5),
    "③ 问题标注 Tool",
    ["Tool 名称: issue_annotator",
     "脚本: annotate_issues.py",
     "调用: subprocess(独立进程/独立内存)",
     "▸ 在原图上绘制问题 bbox 边框",
     "▸ 生成焦点蒙层突出问题区域",
     "▸ 裁剪单个问题的局部截图",
     "▸ 输出: annotated.png + issue-*.png"],
    tag_color=ACCENT2, tag_text="Tool")

info_card(s, Inches(0.4), Inches(4.4), Inches(6.2), Inches(2.6),
    "④ 规则引擎 Harness + Bbox 校验器",
    ["规则引擎(rule_engine.py) — 确定性校验兜底：",
     "  颜色规则: tokens.json 中 off_token → rule_hit",
     "  间距规则: measurements 未命中 token → rule_hit",
     "  Upsert 融合: AI 已发现则增强，未发现→warnings",
     "",
     "Bbox 校验器(bbox_validator.py) — 三层状态机：",
     "  bbox → TRUSTED / SUSPICIOUS / DROPPED",
     "  越界检测: 坐标超出图片边界 → DROPPED",
     "  位置冲突检测: 说「右下」坐标在左半边 → SUSPICIOUS",
     "  只有 TRUSTED 的 bbox 进入标注截图"],
    tag_color=RED_ACCENT, tag_text="Harness")

code_block(s, Inches(6.8), Inches(4.4), Inches(6.2), Inches(2.6),
    "# evidence_tools.py — Agent Tool 子进程调用\n\n"
    "def run_color_analysis(image_path, output_path,\n"
    "                       sample_points):\n"
    "    args = [\n"
    "        sys.executable,  # 复用当前解释器\n"
    "        str(SCRIPTS_DIR / 'analyze_image_tokens.py'),\n"
    "        str(image_path), '--output', str(output_path),\n"
    "    ]\n"
    "    for point in sample_points:\n"
    "        args.extend([\n"
    "            '--sample', f'{label}:{x}:{y}'])\n"
    "    _run(args)  # 子进程隔离执行\n\n\n"
    "# rrule_engine.py — Upsert 融合策略\n\n"
    "def _upsert_rule_finding(issues, warnings,\n"
    "                         rule_issue):\n"
    "    match = _find_matching_issue(issues, rule_issue)\n"
    "    if match is None:\n"
    "        warnings.append(rule_issue)  # 人工复核\n"
    "        return\n"
    "    # AI 已发现 → 增强\n"
    "    match['severity'] = _higher_severity(...)\n"
    "    match['current_observation']\n"
    "        = _join_sentences(...)", sz=8)

# ═══════════════════════════════════════
# MODULE 3: 数据飞轮
# ═══════════════════════════════════════
section("模块三：数据沉淀与飞轮（Data Flywheel）")

s = content("数据飞轮 · 核心概念", "Data Flywheel — Every Audit Makes the System Smarter")
txt(s, Inches(0.6), Inches(1.1), Inches(12), Inches(0.4),
    "每轮审核的产出不是终点，而是下一轮迭代的养料 —— 形成持续进化的数据飞轮",
    sz=16, color=ACCENT2, bold=True)

card(s, Inches(0.4), Inches(1.7), Inches(12.5), Inches(5.0))
stages_data = [
    ("任务执行", ACCENT, ["用户上传设计稿截图", "AI Agent 并行审核",
     "Tool 执行离线验证", "Rule Engine 规则复核", "生成完整报告"]),
    ("结果沉淀", ORANGE, ["制品完整保留(JSON/PNG/HTML)",
     "model_comparison 记录", "rule_hits 记录规则命中率",
     "每模型表现指标追踪"]),
    ("人工反馈", ACCENT2, ["review_candidates→人工确认",
     "纠正误报/补充漏报", "修正数据→ground truth",
     "反馈写入 feedback 表"]),
    ("飞轮反哺", RED_ACCENT, ["Prompt 自动优化: 分析误报模式",
     "规则引擎调参: 校准阈值",
     "Token 库进化: 新色值入库",
     "模型评估: 持续跟踪 precision/recall"]),
]
for i, (title, c, items) in enumerate(stages_data):
    x = Inches(0.6) + Inches(3.1) * i
    info_card(s, x, Inches(1.9), Inches(2.9), Inches(4.5), title, items, tag_color=c, tag_text=f"Step {i+1}", item_sz=10)
for i in range(3):
    txt(s, Inches(3.3)+Inches(3.1)*i, Inches(3.8), Inches(0.5), Inches(0.4), "→", sz=24, color=ACCENT, bold=True)

s = content("数据飞轮 · 四个反哺维度", "4 Feedback Loops — Continuous Improvement")
info_card(s, Inches(0.4), Inches(1.2), Inches(6.2), Inches(2.5),
    "维度一：Prompt 自动优化",
    ["收集每个任务的误报/漏报模式",
     "分析 GPT-only 和 Kimi-only 问题的分布规律",
     "某类别漏报率 > 阈值 → 强化 Prompt 对应维度描述",
     "Prompt 版本化管理，支持 A/B 对比实验"],
    tag_color=ACCENT, tag_text="反哺 1")
info_card(s, Inches(6.8), Inches(1.2), Inches(6.2), Inches(2.5),
    "维度二：规则引擎参数校准",
    ["根据人工复核结果调整色差阈值",
     "1px 容差是否需根据设计稿倍率动态调整？",
     "分类冲突规则：哪些分类允许跨类匹配？",
     "误报多 → 收紧阈值；漏报多 → 放宽阈值"],
    tag_color=ORANGE, tag_text="反哺 2")
info_card(s, Inches(0.4), Inches(4.0), Inches(6.2), Inches(2.5),
    "维度三：Token 库持续进化",
    ["审核中发现的新色值 → 自动入库候选列表",
     "人工确认后补充到 color_tokens 库",
     "新间距/字体模式 → 研究是否纳入规范",
     "反哺设计规范本身 —— 帮设计师发现规范盲区"],
    tag_color=ACCENT2, tag_text="反哺 3")
info_card(s, Inches(6.8), Inches(4.0), Inches(6.2), Inches(2.5),
    "维度四：模型评估与选型",
    ["持续追踪两模型的 precision / recall / F1",
     "按分类维度分别统计(颜色/间距/组件/图标)",
     "发现 GPT 在颜色上更好，Kimi 在间距上更好",
     "→ 未来可动态调整 Expert 权重"],
    tag_color=RED_ACCENT, tag_text="反哺 4")

s = content("数据沉淀 · 全链路制品追溯", "Traceability — SQLite + Filesystem Two-Tier Storage")
txt(s, Inches(0.6), Inches(1.1), Inches(12), Inches(0.4),
    "控制面(SQLite) + 数据面(文件系统)分离 —— 查询轻量、备份简单、全链路可追溯",
    sz=15, color=ACCENT2, bold=True)

info_card(s, Inches(0.4), Inches(1.7), Inches(6.2), Inches(2.5),
    "SQLite 控制面（元数据）",
    ["tasks 表: id/title/status(created/running/succeeded/failed)",
     "task_images 表: 每张图片独立状态 + 制品路径",
     "users 表: 认证 + 角色(admin/user)",
     "只存几十行记录，查询永远轻量",
     "Schema 版本号控制(SCHEMA_VERSION=3)，增量迁移"],
    tag_color=ACCENT, tag_text="SQLite")

info_card(s, Inches(6.8), Inches(1.7), Inches(6.2), Inches(2.5),
    "文件系统数据面（制品仓库）",
    ["data/uploads/{task_id}/",
     "  ├─ originals/ ← 原始截图(不可变)",
     "  └─ artifacts/image-{n}/",
     "      ├─ audit-01-gpt-5-5.json  ← AI Stage 1",
     "      ├─ audit-02-kimi-k2-6.json ← AI Stage 2",
     "      ├─ audit.json             ← 融合报告",
     "      ├─ tokens.json            ← Tool 颜色分析",
     "      ├─ measurements.json      ← Tool 间距测量",
     "      ├─ issues.json            ← 标注用 issues",
     "      ├─ annotated.png          ← 标注截图",
     "      ├─ issue-*.png            ← 局部裁剪",
     "      └─ region-crops/          ← 区域裁剪"],
    tag_color=ORANGE, tag_text="文件系统")

info_card(s, Inches(0.4), Inches(4.4), Inches(6.2), Inches(2.5),
    "可对比 · 模型 PK 报告",
    ["每个 issue 携带完整溯源信息：",
     "  agreement: both / gpt_only / kimi_only",
     "  source_models: [GPT-5.5, Kimi-K2.6]",
     "  rule_sources: [model, color_sample]",
     "",
     "model_comparison 结构：",
     "  agreed_issues → 双方一致同意",
     "  gpt_only_issues → 仅 GPT 发现",
     "  kimi_only_issues → 仅 Kimi 发现",
     "  review_candidates → 待人工确认",
     "  model_failures → 模型失败记录"],
    tag_color=ACCENT2, tag_text="可对比")

info_card(s, Inches(6.8), Inches(4.4), Inches(6.2), Inches(2.5),
    "闭环追踪指标",
    ["持续追踪的飞轮指标：",
     "  ▸ 召回率(Recall)：模型发现的真实问题占比",
     "  ▸ 精确率(Precision)：正确问题占比",
     "  ▸ 模型一致率：both / (both + model_only)",
     "  ▸ 规则命中率：rule_hits / total_issues",
     "  ▸ 人工复核率：review / total_issues",
     "  ▸ 降级率：degraded_tasks / total_tasks",
     "",
     "这些指标随数据飞轮运转持续提升"],
    tag_color=RED_ACCENT, tag_text="指标")

code_block(s, Inches(0.4), Inches(6.8), Inches(6.2), Inches(0.5),
    "结论自动汇总(降级时自动加前缀):\n"
    "「双模型本地合并完成：共发现 N 个问题，双方共同确认 M 个，单模型补充 K 个。」", sz=8)

code_block(s, Inches(6.8), Inches(6.8), Inches(6.2), Inches(0.5),
    "「候选模型降级审核：共发现 N 个问题...」/ 「单模型降级审核：共发现 N 个问题...」", sz=8)


# ═══════════════════════════════════════
# MODULE 4: 架构全景
# ═══════════════════════════════════════
section("模块四：架构全景与设计模式")

s = content("7 层架构总览 · LLM/Agent/Skill/Harness 融合", "Full Architecture Stack")
txt(s, Inches(0.6), Inches(1.1), Inches(12), Inches(0.4),
    "Web → Queue → Orchestration Harness → Agent/Skill → Tool/Rule Engine → Data → Report",
    sz=15, color=ACCENT2, bold=True)

layers = [
    ("WEB 层", "FastAPI + Jinja2", "极薄路由，仅 HTTP 适配，不含业务逻辑", ACCENT),
    ("队列层", "threading Queue", "双检锁单 Worker，daemon 自动终止，永不崩溃", ORANGE),
    ("编排 Harness", "6-Stage Pipeline", "Agent 生命周期管理、容错降级调度、图片级隔离", PINK),
    ("Agent/Skill", "GPT-5.5 + Kimi-K2.6", "4 种审核 Agent、3 级 Prompt Skill、双模型 MOE 融合", ACCENT),
    ("Tool 层", "3 子进程 Tool", "颜色采样/区域测量/标注截图，独立内存隔离运行", ACCENT2),
    ("Rule Harness", "规则引擎", "颜色/间距确定性校验、Upsert 融合、Bbox 三层校验", ORANGE),
    ("报告层", "HTML + PDF", "规范素材联动、JS 缩放平移、无头 Chrome 导出", PINK),
]
for i, (name, tech, desc, c) in enumerate(layers):
    y = Inches(1.6) + Inches(0.7) * i
    sh = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.4), y, Inches(1.5), Inches(0.55))
    sh.fill.solid(); sh.fill.fore_color.rgb = c; sh.line.fill.background()
    tf = sh.text_frame; tf.word_wrap = False; tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]; p.text = name; p.font.size = Pt(12); p.font.color.rgb = WHITE; p.font.bold = True; p.font.name = "Microsoft YaHei"; p.alignment = PP_ALIGN.CENTER
    txt(s, Inches(2.1), y+Inches(0.05), Inches(1.8), Inches(0.45), tech, sz=12, color=WHITE, bold=True)
    txt(s, Inches(4.0), y+Inches(0.05), Inches(9), Inches(0.45), desc, sz=11, color=LIGHT_GRAY)

s = content("LLM / Agent / Skill / Harness 概念融合", "Concept Integration Map")
txt(s, Inches(0.6), Inches(1.1), Inches(12), Inches(0.4),
    "项目中实践的 AI 工程化概念及其协作关系",
    sz=15, color=ACCENT2, bold=True)

concepts = [
    ("LLM", ACCENT, ["大语言模型(GPT-5.5 / Kimi-K2.6)",
     "作为审核 Agent 的「大脑」",
     "",
     "角色：",
     "  理解设计规范文本",
     "  分析截图中的视觉元素",
     "  生成结构化审核结果",
     "",
     "Provider 无关抽象：",
     "  config.py 统一适配 OpenAI/JDCloud",
     "  任何兼容 API 的模型都可接入"]),
    ("Agent", ORANGE, ["具有角色和工具的 AI 实体",
     "",
     "项目 Agent 清单：",
     "  GPT-5.5 Agent（主审专家）",
     "  Kimi-K2.6 Agent（复审专家）",
     "  Color Expert（色彩专家）",
     "  Layout Expert（布局专家）",
     "  Component Expert（组件专家）",
     "  Icon Expert（图标专家）",
     "",
     "公式：Agent = LLM + Skill + Tool"]),
    ("Skill", ACCENT2, ["封装领域知识的 Prompt 模板",
     "",
     "项目 Skill 清单：",
     "  jm-audit-full.skill",
     "  jm-audit-light.skill",
     "  jm-audit-kimi-compact.skill",
     "  jm-color-audit.skill",
     "  jm-spacing-audit.skill",
     "  jm-component-audit.skill",
     "  jm-icon-audit.skill",
     "",
     "Skill = 版本号 + Prompt + Schema"]),
    ("Harness", RED_ACCENT, ["编排 Agent 生命周期的基设施",
     "",
     "项目 Harness 实现：",
     "  Task Runner Harness",
     "  Dual Auditor Harness",
     "  Tool Harness",
     "  Rule Engine Harness",
     "  Bbox Validator Sub-Harness",
     "",
     "Harness 职责：",
     "  调度 + 容错 + 结果聚合"]),
]
for i, (name, c, items) in enumerate(concepts):
    info_card(s, Inches(0.4)+Inches(3.25)*i, Inches(1.6), Inches(3.0), Inches(5.3),
        name, items, tag_color=c, tag_text="概念", title_sz=16, item_sz=10)

s = content("关键设计模式总结", "7 Architecture Design Patterns")
txt(s, Inches(0.6), Inches(1.1), Inches(12), Inches(0.3),
    "7 种关键设计模式支撑系统的可扩展性、容错性和可维护性", sz=14, color=LIGHT_GRAY)

patterns = [
    ("收缩式编排", "所有流水线阶段同线程完成，数据流清晰、失败回滚简单", ACCENT),
    ("Agent + Skill 分离", "Agent 调度和工具调用，Skill 封装领域知识，各自独立迭代", ORANGE),
    ("双检锁单 Worker", "线程安全启动、daemon 自动终止、永不崩溃的 worker loop", ACCENT2),
    ("子进程 Tool 隔离", "证据工具独立进程运行，独立管理内存，避免主进程 OOM", RED_ACCENT),
    ("三级容错降级", "模型级(错误分类) + 融合级(单模型降级) + 图片级(独立 try/except)", PINK),
    ("三级证据链", "Level 1 AI 发现 → Level 2 规则验证 → Level 3 人工复核", YELLOW),
    ("控制/数据面分离", "SQLite 控制面(几十行)+ 文件系统数据面(制品仓库)", ACCENT2),
]
for i, (name, desc, c) in enumerate(patterns):
    y = Inches(1.5) + Inches(0.75) * i
    sh = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.4), y, Inches(2.0), Inches(0.55))
    sh.fill.solid(); sh.fill.fore_color.rgb = c; sh.line.fill.background()
    tf = sh.text_frame; tf.word_wrap = False; tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]; p.text = name; p.font.size = Pt(12); p.font.color.rgb = WHITE; p.font.bold = True; p.font.name = "Microsoft YaHei"; p.alignment = PP_ALIGN.CENTER
    txt(s, Inches(2.6), y+Inches(0.05), Inches(10.3), Inches(0.45), desc, sz=12, color=LIGHT_GRAY)

# ═══════════════════════════════════════
# FINAL: 总结
# ═══════════════════════════════════════
s = content("总结 · 核心设计理念", "Design Philosophy")
txt(s, Inches(0.6), Inches(1.1), Inches(12), Inches(0.6),
    "「AI 做发现、Tool 做验证、Rule 做兜底、数据飞轮做进化」",
    sz=22, color=ACCENT2, bold=True, align=PP_ALIGN.CENTER)

info_card(s, Inches(0.4), Inches(1.9), Inches(6.2), Inches(2.3),
    "知识库 → 自动化 + 可扩展",
    ["素材自动化分析管线：PDF/图片/文档智能摄入→结构化库",
     "知识库即代码：Git 版本控制，CI 自动同步",
     "跨场景扩展：一次建设，多品牌/多平台复用",
     "Skill 化封装：每个领域知识封装为独立 Skill"],
    tag_color=ACCENT, tag_text="模块一")
info_card(s, Inches(6.8), Inches(1.9), Inches(6.2), Inches(2.3),
    "MOE → 双层专家系统",
    ["Level 1：GPT+Kimi 跨模型集成，互补漏检",
     "Level 2：颜色/布局/组件/图标多 Expert 路由，提升深度",
     "双层互补：广度 + 深度 = 全面覆盖",
     "Agent + Skill + Harness 成熟模式支撑"],
    tag_color=ORANGE, tag_text="模块二")
info_card(s, Inches(0.4), Inches(4.4), Inches(6.2), Inches(2.3),
    "工具 → Agent Tool 体系",
    ["颜色采样/区域测量/标注截图三件套，子进程隔离",
     "规则引擎 Harness 兜底，确定性校验",
     "Bbox 三层状态机把关标注数据质量"],
    tag_color=ACCENT2, tag_text="模块二")
info_card(s, Inches(6.8), Inches(4.4), Inches(6.2), Inches(2.3),
    "数据 → 飞轮持续进化",
    ["控制面/数据面分离，全链路可追溯",
     "每轮审核反哺 Prompt/规则/Token/模型评估",
     "4 个反哺维度：precision/recall 持续追踪"],
    tag_color=RED_ACCENT, tag_text="模块三")

txt(s, Inches(0.6), Inches(7.0), Inches(12), Inches(0.4),
    "总代码量 ~8000 行 Python · 22 个测试文件 · 4 种模型变体 · 7 层架构 · 7 种设计模式",
    sz=13, color=MID_GRAY, align=PP_ALIGN.CENTER)

# ── Save ──
out = "/Users/heyunshen/work/PROJECT/jdc/jm-checktool/web/jm-ai-design-app_jd/JM_AI_架构设计方案汇报_完整版.pptx"
prs.save(out)
print(f"PPT saved to: {out}")
print(f"Total slides: {len(prs.slides)}")
