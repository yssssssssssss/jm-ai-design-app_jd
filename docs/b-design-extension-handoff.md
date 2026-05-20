# B-design 扩展规范交接说明

## 背景目标

本轮工作的目标是把 `references/alpha/` 中 B-design 审核案例的红字问题沉淀到 B-design 规范里，让后续类似截图能被检出。同时把 `references/B-design/` PDF 中只有示意图、缺少明文描述的规则提炼出来，作为 B-design 扩展规范。

## 规则来源分层

B-design 规范现在分三类来源：

- `pdf_text`：来自 `references/B-design/` PDF 的明文规范。
- `pdf_visual_example`：来自 PDF 示意图归纳的规则。
- `alpha_case`：来自 `references/alpha/` 红字案例沉淀的规则。

这三类来源都属于 B-design 自己的规则体系，不混入 JM AI 规则。

## 当前实现

### `references/specs/b-design.md`

新增 `## 扩展审核规则`，包含：

- 来源类型说明
- PDF 示意图归纳规则
- alpha 案例沉淀规则
- 扩展规则输出要求

### `app/b_design_router.py`

新增扩展识别场景：

- `b-design-visual-patterns`
- `title-optimization-flow`
- `quality-dashboard`
- `legacy-printing-page`
- `form-confirmation-flow`
- `alpha-visual-rules`

这些场景命中后，会加载 `扩展审核规则` 章节。

### `app/prompt_builder.py`

B-design 适用性识别 prompt 从“只识别 PDF Agent 组件”改为识别：

- PDF 明文组件
- PDF 示意图归纳规则
- alpha 案例沉淀规则

同时仍强调：不要输出未被这些来源覆盖的通用 B 端界面问题。

### `app/openai_audit.py`

审核 issue schema 增加：

- `rule_source_type`
- `rule_source_ref`

B-design issue 要求标注来源，例如：

```json
{
  "rule_source_type": "alpha_case",
  "rule_source_ref": "references/alpha/image.png_NDR-SQ 1.png"
}
```

### `app/report_renderer.py`

报告“详细问题清单”的参考素材列只展示规范参考图片，不展示 `alpha_case`、文件名或规则来源文字。`rule_source_type` / `rule_source_ref` 仍保留在原始 JSON 中，供调试和追溯使用。报告顶部的适用性判断也不会直接暴露 `alpha_case`、`pdf_visual_example`、`pdf_text` 这类内部来源标识。

## alpha 已沉淀的问题类型

扩展规则覆盖了这些红字问题：

- 保存/确认/下一步在左，取消在右。
- 保存和下一步同义时只保留一个主动作。
- 底部按钮样式、尺寸、间距、位置参考模板。
- 普通非 AI 功能不要用紫色，应使用 B 端蓝色主按钮。
- AI/智能诊断/勾选等模板明确场景可用紫色。
- 不可点击内容不要用蓝色链接态。
- 非失败/破坏语义不要用红色。
- 完成态不要随意使用绿色勾。
- 选中态不要蓝/紫/绿混用。
- 不要灰卡套白卡套灰卡，容器最多两层。
- 灰框外不要再套无意义白框。
- 卡片留白、边框、层级要清晰。
- 图标尺寸不要过大，首页入口/诊断/AI 卡片图标参考模板。
- 去掉无依据 emoji、星星、装饰性图标。
- 没有下拉语义时去掉下拉箭头。
- 输入框结构参考模板。
- 普通页面元素需要对齐。
- 标题放左侧或模板指定位置。
- 除模板明确要求外，不建议大面积渐变。
- 黄色背景和描边应弱化或去掉。

## 重要边界

当前不是把 B-design 扩成“通用 B 端审核”。逻辑仍然是：

1. 先做 B-design 适用性识别。
2. 只有命中 PDF 组件、PDF 示意图模式或 alpha 扩展场景时，才加载对应规范。
3. 未命中时返回“未命中 B-design 规范覆盖范围”，不输出泛化问题。
4. 每个 B-design 问题必须可追溯到 `pdf_text` / `pdf_visual_example` / `alpha_case`。

## 后续补充细节规范的方法

新增规则不要直接写成“风格不对”或“需要更美观”。每条规则都要能被截图审核稳定观察到，推荐按这个顺序补：

1. 收集失败样例：保留原图、红框、红字问题，以及本次漏检的审核 JSON。
2. 拆成单一视觉问题：一条规则只管一个可观察缺陷，例如“完成态误用绿色勾”，不要混入按钮顺序、容器层级等多个问题。
3. 写清触发条件：截图里必须出现什么页面、控件、状态、颜色、布局结构时才启用。
4. 写清错误判定：什么表现算错，最好包含反例图或 alpha 文件名。
5. 写清正确表现：应该改成哪类 B-design 模板表现，不能只写“优化”。
6. 标注来源：`pdf_text` / `pdf_visual_example` / `alpha_case` 三选一；视觉图规则必须绑定来源图片或 PDF 页面的组件/状态名。
7. 补路由关键词：如果这是新页面或新子场景，需要同步补 `app/b_design_router.py`，否则第一阶段可能不会加载这条规范。
8. 补参考图片索引：如果报告里要展示对应规范图片，需要同步补 `references/spec-assets-b-design.json` 或相关素材，避免落到通用色彩图。
9. 补回归测试：至少验证路由命中、prompt 包含规则、schema 保留来源字段、报告只展示图片。
10. 用真机样例重跑：确认同一类问题能检出，同时无关页面不会被误报。

一条可落地规则的最小模板：

```text
规则 ID：
来源类型：
来源文件/页码：
适用页面/状态：
可观察触发条件：
错误判定：
正确表现：
不适用边界：
建议输出文案：
```

## 验证状态

已通过目标测试：

```bash
PYTHONPATH=. /tmp/jm-checktool-py311/bin/python -m pytest tests/test_b_design_router.py tests/test_prompt_builder.py tests/test_openai_audit.py tests/test_report_renderer.py -q
```

结果：

```text
75 passed
```

也通过：

- `py_compile`
- `git diff --check`
- B-design 扩展规范未检出 JM AI / jm-ai / jm-audit / ai/ 混入

## 真机验证信号

上传 `references/alpha/` 里的典型案例图，审核规范只勾选 `京东 B 端设计规范（B-design Agent 组件规范）`。

推荐先测：

- `references/alpha/image.png_NDR-SQ 1.png`
  - 预期能检出：灰卡/白卡/灰卡三层嵌套、选中态颜色、预览确认/取消按钮顺序。
- `references/alpha/image.png_l_Vf4O 1.png`
  - 预期能检出：无下拉语义时去掉下拉箭头。
- `references/alpha/image.png_MZxI2s 1.png`
  - 预期能检出：去掉 emoji。
- `references/alpha/image.png_FaeyIY 1.png` 或 `references/alpha/image.png_bmRvcc 1.png`
  - 预期能检出：普通非 AI 功能不要用紫色，应用 B 端蓝色按钮。

报告中应出现：

- “适用性判断”命中扩展场景。
- “已加载规范章节”包含 `通用审核原则、扩展审核规则`。
- “详细问题清单”的参考素材列只显示规范参考图片，不显示 `alpha_case` 或文件名文字。

原始 JSON 中应能看到：

```json
{
  "loaded_spec_sections": ["通用审核原则", "扩展审核规则"],
  "rule_source_type": "alpha_case",
  "rule_source_ref": "references/alpha/..."
}
```

如果真机报告仍显示“未命中 B-design 规范覆盖范围”，优先看模型 JSON 里的 `b_design_applicability`，这通常说明第一阶段适用性识别没有命中扩展场景，而不是规范没有加载。

## 服务状态

当前服务运行在 `http://127.0.0.1:8010/`，监听进程为 Python `PID 19317`。

服务是从 tmux session 启动的：

```bash
tmux new-session -d -s jm-ai-design-8010 -c /Users/heyunshen/work/PROJECT/jdc/jm-checktool/web/jm-ai-design-app_jd /tmp/jm-ai-design-app-jd-py311/bin/python -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8010 --workers 1 --log-level info
```
