# JM AI 设计规范审核平台第一轮升级设计

## 1. 背景

当前项目已经具备上传设计稿、调用大模型审核、双模型结果合并、颜色/间距证据生成、截图标注、规范素材匹配和 HTML 报告输出能力。

下一阶段不应继续只堆功能，而应先解决审核系统最关键的三类问题：

1. **稳定性**：同一稿件多次审核，核心问题需要更一致。
2. **可信度**：颜色、间距、bbox 等可测量内容需要更多由规则和证据支撑。
3. **结构化**：问题、模型输出、规则命中、证据和报告需要使用统一结构，为后续入库和看板打基础。

本设计定义第一轮升级范围。该轮升级目标不是一次性完成完整平台化，而是建立后续扩展的主干能力。

## 2. 目标

第一轮升级目标：

- 建立固定评估基线，避免后续优化靠主观感觉判断。
- 建立标准问题类目体系和 issue schema。
- 将 prompt 从大块字符串升级为分层 PromptOps 结构。
- 将 MoE 多专家审核从概念落到模型角色与输出结构。
- 建立 bbox 可信度体系，减少错误截图和偏移截图。
- 将色彩、间距这类可测量问题逐步交给规则引擎主判。
- 让 HTML 报告展示更清楚的质量摘要、问题类型、证据来源和可信度信息。

## 3. 非目标

第一轮不做以下事项：

- 不做完整质量看板。
- 不做 Figma 或设计平台接入。
- 不做 PDF 导出。
- 不做复杂 OCR 体系。
- 不做深度学习组件检测模型。
- 不做自动修复设计稿。
- 不重写现有 Web 框架。
- 不引入外部任务队列，仍保留当前进程内队列模式。

这些能力可以在后续平台化阶段推进。

## 4. 当前系统主链路

当前审核链路：

```text
上传图片
→ 创建任务
→ 后台执行 run_task
→ 调用模型审核
→ 双模型结果合并
→ 颜色采样
→ 区域和间距测量
→ 规则复核
→ 生成问题截图
→ 生成 HTML 报告
```

第一轮升级会保留这条主链路，只在关键边界补充结构化对象、可信度评分、prompt 分层和规则主判能力。

## 5. 设计原则

### 5.1 稳定优先

所有改动都需要提升审核稳定性，而不是只提升一次性输出的“好看程度”。

### 5.2 规则负责可测量事实

颜色、间距、bbox、尺寸等可测量内容应尽量由工具和规则判断。大模型负责识别候选问题、解释上下文和生成可读建议。

### 5.3 Issue 是系统核心对象

模型输出、规则输出、报告展示、截图标注、未来入库，都应围绕标准 issue 对象组织。

### 5.4 HTML 是展示层，不是唯一数据源

报告仍然保留 HTML，但后续应逐步把问题、证据、模型尝试和规则命中结构化，避免报告文件成为唯一资产。

### 5.5 小步演进

不一次性做完整平台化。第一轮只做会显著改善稳定性、可信度和后续扩展能力的核心主干。

## 6. 能力包设计

### 6.1 评估基线

新增固定评估集，用于衡量 prompt、模型、规则和融合逻辑的变化效果。

建议目录：

```text
tests/fixtures/evaluation/
  case-001/
    input.png
    expected.json
  case-002/
    input.png
    expected.json
```

`expected.json` 结构：

```json
{
  "case_id": "case-001",
  "description": "右上角主操作使用非 JM AI 色彩",
  "expected_issues": [
    {
      "category": "color_gradient",
      "subcategory": "off_token_color",
      "target_element": "右上角邀好友按钮",
      "violation_type": "非 JM AI 品牌色",
      "severity": "中",
      "bbox": [1200, 32, 140, 40],
      "must_detect": true
    }
  ],
  "known_false_positive_traps": [
    "第三方内容不应判为 JM AI 品牌色违规"
  ]
}
```

第一轮不要求一次性准备 30 张图。可以先准备 5-10 张真实高价值样本，后续逐步扩充。

验收标准：

- 能读取评估集。
- 能输出每个 case 的问题命中、漏检、重复问题和 bbox 状态。
- 后续 prompt 或规则改动可以复跑评估集。

### 6.2 标准 Taxonomy

新增标准问题类目体系。

一级类目：

```text
brand_identity       品牌一致性
color_gradient       色彩与渐变
typography           字体与文本
spacing_layout       间距与布局
component_spec       组件规范
icon_ai_mark         图标与 AI 标识
header_navigation    头部与导航
interaction_state    交互与状态
accessibility        可访问性
content_hierarchy    文案与信息层级
```

二级类目示例：

```text
color_gradient.off_token_color
color_gradient.wrong_gradient_direction
color_gradient.non_ai_primary_action
color_gradient.low_contrast
spacing_layout.off_spacing_token
spacing_layout.alignment_mismatch
component_spec.button_wrong_style
component_spec.tag_wrong_shape
icon_ai_mark.missing_sparkle
header_navigation.weak_hierarchy
```

实现建议：

- 新增 `app/audit_taxonomy.py` 或等价模块。
- 提供 category/subcategory 归一化函数。
- 模型输出和旧数据都通过归一化函数进入标准类目。

验收标准：

- 报告中问题类目稳定。
- 规则引擎可以基于类目挂载规则。
- 双模型融合可以使用标准类目辅助判断。

### 6.3 标准 Issue Schema

建立平台内部统一 issue 对象。

建议字段：

```json
{
  "id": "问题-001",
  "issue_key": "color_gradient.off_token_color:top-right-invite-button",
  "category": "color_gradient",
  "subcategory": "off_token_color",
  "target_element": "右上角邀好友按钮",
  "violation_type": "非 JM AI 品牌色",
  "severity": "中",
  "location": "顶部右上角",
  "current_observation": "按钮使用橙色强调色。",
  "spec_expectation": "JM AI 主操作应使用 AI 紫色 token 或 AI 渐变。",
  "recommendation": "替换为 ai/ai-normal 或 JM AI 主渐变。",
  "confidence": 0.86,
  "evidence_type": "model_with_rule",
  "bbox": [1200, 32, 140, 40],
  "bbox_status": "trusted",
  "bbox_confidence": 0.86,
  "bbox_reason": "bbox 位于右上区域，符合问题位置描述。",
  "source_models": ["GPT-5.5", "Kimi-K2.6"],
  "agreement": "both",
  "rule_sources": ["color.primary_action.off_token"]
}
```

字段说明：

- `issue_key`：用于去重、复跑对比和入库。
- `target_element`：目标 UI 元素。
- `violation_type`：违规类型。
- `evidence_type`：区分模型推断、规则实测、模型+规则等。
- `bbox_status`：`trusted`、`suspicious`、`dropped`。
- `bbox_confidence`：bbox 可信度评分。
- `rule_sources`：命中的规则 ID。

实现建议：

- 新增 issue normalization 层，不要求模型一次性完美输出所有字段。
- 对缺失字段进行推断或置空。
- 保留旧字段兼容报告和测试。

验收标准：

- 模型 issue、规则 issue、合并 issue 都统一成该结构。
- 报告从该结构读取字段。
- 旧模型输出仍可兼容。

### 6.4 PromptOps 初版

将现有大 prompt 拆成分层结构。

建议结构：

```text
system_prompt
spec_context
task_mode_prompt
image_context
output_schema_prompt
bbox_rules_prompt
tool_request_rules_prompt
self_check_prompt
```

各层职责：

| Prompt 层 | 职责 |
|---|---|
| system_prompt | 角色、语言、禁止编造、证据优先 |
| spec_context | JM AI 规范内容，可按类目动态注入 |
| task_mode_prompt | 快速、标准、严格、复核等模式 |
| image_context | 图片尺寸、声明尺寸、缩放上下文 |
| output_schema_prompt | JSON 字段和 issue schema |
| bbox_rules_prompt | bbox 坐标、越界、无法定位规则 |
| tool_request_rules_prompt | 何时请求颜色采样、区域测量、OCR |
| self_check_prompt | 输出前检查中文、重复、字段完整、证据不足 |

新增字段：

```text
prompt_version
schema_version
spec_version
```

实现建议：

- 初期可以仍在 `app/openai_audit.py` 内实现分层 builder。
- 等结构稳定后再拆到独立模块。

验收标准：

- prompt 输出仍符合现有审核 JSON。
- prompt 版本可在报告或模型 JSON 中追踪。
- 同一评估样本多次运行，字段缺失和英文输出减少。

### 6.5 MoE 专家角色化

将“双模型审核”升级为可描述、可扩展的 MoE 多专家审核机制。

第一轮专家角色：

```text
structure_expert   页面结构专家
compliance_expert  规范合规专家
evidence_expert    证据定位专家
```

第一轮不要求每个专家都调用独立模型。可以先通过 prompt 角色和输出字段表达专家职责。

建议输出：

```json
{
  "expert_role": "compliance_expert",
  "model": "GPT-5.5",
  "issues": []
}
```

融合层需要保留：

- `source_models`
- `source_experts`
- `agreement`
- `review_candidates`

验收标准：

- 报告能说明哪些问题来自双方一致，哪些是单专家补充。
- 单模型失败时任务可以降级完成。
- 后续可扩展更多专家而不重写整条链路。

### 6.6 BBox 可信度体系

新增 bbox 评分和状态机制。

输入：

- issue bbox
- 图片尺寸
- 问题描述文本
- location 文本
- category/subcategory

输出：

```json
{
  "bbox_status": "trusted",
  "bbox_confidence": 0.86,
  "bbox_reason": "位于右上区域，符合 location 描述。"
}
```

评分规则第一版：

- bbox 是否越界
- bbox 宽高是否为正
- bbox 面积是否过大或过小
- bbox 中心点是否匹配“左上/右上/左下/右下/顶部/底部”等位置词
- 多模型 bbox 是否有重叠
- bbox 是否覆盖过大页面区域

行为：

- `trusted`：可生成截图。
- `suspicious`：报告可展示，但截图生成需谨慎。
- `dropped`：不生成问题裁剪图。

验收标准：

- 明显方向错误 bbox 被降级或丢弃。
- 越界 bbox 不再生成错误截图。
- 报告能解释某些问题为何没有截图。

### 6.7 规则引擎主判初版

将规则引擎从“复核模型结论”升级为“可测量项主判”。

第一轮只做两类：

1. 色彩规则
2. 间距规则

规则输出：

```json
{
  "rule_id": "color.primary_action.off_token",
  "category": "color_gradient",
  "subcategory": "off_token_color",
  "result": "failed",
  "measured_value": "#FF7A00",
  "expected_value": "ai/ai-normal #6B36FA",
  "delta": 82.4,
  "confidence": 0.91,
  "evidence_type": "sampled_color"
}
```

色彩规则：

- 使用采样点或区域主色。
- 计算最近 JM AI token。
- 超过阈值且目标元素属于主操作、品牌强调、状态强调时判定违规。

间距规则：

- 使用模型请求的 regions/distances。
- 计算设计尺寸折算后的 gap。
- 判断是否命中 spacing token。

验收标准：

- 色彩问题能展示采样值、最近 token 和色差。
- 间距问题能展示测量值、目标 token 和偏差。
- 规则问题能和模型问题合并，而不是重复输出。

### 6.8 报告升级

HTML 报告第一轮升级为更清晰的质量验收单。

新增摘要：

```text
合规状态
问题总数
高/中/低风险数量
MoE 一致问题数量
规则命中问题数量
有截图证据的问题数量
待确认问题数量
```

问题表增加：

- 问题类型
- 目标元素
- 证据类型
- bbox 置信度
- 来源模型
- 规则来源

验收标准：

- 第一屏能快速看懂本次审核质量状态。
- 问题清单能说明“模型说的”还是“规则测的”。
- 证据不足的问题不会伪装成确定结论。

## 7. 数据库策略

第一轮可以选择两种策略：

### 方案 A：暂不改数据库

只在 artifact JSON 和报告里落标准 issue。

优点：

- 改动小。
- 风险低。
- 适合先验证 schema 和规则。

缺点：

- 后续统计和看板仍不方便。

### 方案 B：新增最小结构化表

新增：

```text
audit_runs
audit_issues
model_attempts
```

优点：

- 为看板和历史查询打基础。
- 能追踪模型和 prompt 表现。

缺点：

- 涉及 DB migration。
- 需要更多测试。

第一轮推荐：

> 先采用方案 A 完成 schema、prompt、bbox、规则稳定化；如果评估集验证通过，再进入方案 B 的数据库升级。

原因：当前最大风险是问题结构和规则边界还没完全稳定，过早入库会增加迁移成本。

## 8. 测试策略

需要新增或增强测试：

- taxonomy 归一化测试
- issue schema normalization 测试
- issue_key 生成测试
- prompt builder 测试
- bbox validator 测试
- rule hit 输出测试
- 色彩规则主判测试
- 间距规则主判测试
- 双模型融合兼容新字段测试
- 报告展示新字段测试
- 旧 audit JSON 兼容测试

评估脚本不代替单元测试。  
单元测试保证结构和规则正确，评估集用于观察真实审核效果。

## 9. 验收标准

第一轮升级完成后，需要满足：

- 同一评估样本多次审核，核心问题更稳定。
- 双模型发现同一问题时，重复输出明显减少。
- 明显错误 bbox 不再生成错误截图。
- 色彩类问题至少包含采样值、最近 token、色差或规则来源。
- 间距类问题至少包含测量值、目标 token、偏差或规则来源。
- 报告能展示问题类型、证据类型、bbox 可信度和规则来源。
- 旧任务和旧格式 audit JSON 不应因为新 schema 崩溃。

## 10. 推荐实施顺序

1. 建立 taxonomy 和 issue schema。
2. 增加 issue normalization。
3. 增加 bbox validator。
4. 改造融合逻辑使用标准 issue 字段。
5. 改造 prompt builder 为分层结构。
6. 增加 prompt version/schema version。
7. 升级色彩和间距规则输出。
8. 改造报告摘要和问题表。
9. 建立初版评估集。
10. 跑评估集并记录基线。

这个顺序的理由：

- 先统一问题结构，再改 prompt 和融合，避免输出字段继续发散。
- 先做 bbox validator，再扩大截图能力，避免错误证据伤害信任。
- 先验证 artifact JSON 和报告，再决定数据库迁移，避免过早固化不稳定模型。

## 11. 风险与控制

### 风险 1：Issue schema 过重

控制：

- 字段允许缺省。
- normalization 层补齐默认值。
- 报告只展示高价值字段。

### 风险 2：规则主判误报

控制：

- 第一轮只做色彩和间距。
- 规则必须输出 measured/expected/delta。
- 规则命中先与模型问题合并，不盲目新增大量问题。

### 风险 3：Prompt 改造导致模型输出退化

控制：

- 保留旧 prompt 作为 fallback。
- 使用评估集对比。
- prompt version 入 artifact。

### 风险 4：bbox 评分误杀有效截图

控制：

- 第一版 suspicious 不直接丢弃。
- dropped 只用于越界、方向明显错误、面积明显异常的 bbox。
- 报告保留无截图问题，不因 bbox 被丢弃而丢失问题文本。

## 12. 后续阶段

第一轮完成后，进入第二轮：

- 最小数据库升级：`audit_runs`、`model_attempts`、`audit_issues`。
- OCR Reader 初版。
- Component Detector 启发式初版。
- Reference Matcher 标签增强。
- report_versions。

第三轮：

- 质量看板。
- 规范盲区清单。
- 人工复核状态。
- 修复前后对比。
- 批量审核。

