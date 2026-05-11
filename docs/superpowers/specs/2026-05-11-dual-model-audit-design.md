# 双模型审核融合设计

日期：2026-05-11

## 目标

在当前 JM AI 设计稿审核项目中同时使用 JDCloud 的 `GPT-5.5` 和 `Kimi-K2.6` 对同一张图片进行审核，并将两份结论融合成一份最终报告。

第一版目标不是让模型互相“投票替代人工判断”，而是降低漏检概率，并把模型之间的一致、单方发现和分歧显式展示出来，提升报告的可追溯性。

## 范围

第一版只支持 JDCloud provider 下的双模型：

- `GPT-5.5`
- `Kimi-K2.6`

不扩展 OpenAI provider，不引入第三个 LLM 做仲裁，不改登录、任务列表、上传流程和数据库结构。

## 非目标

- 不做复杂语义向量匹配。
- 不做多模型权重学习。
- 不做自动真伪裁决。
- 不改变当前单模型审核链路的默认能力。
- 不把融合逻辑塞进模型 prompt。

## 配置设计

新增一个显式开关，避免隐式改变当前行为：

```env
AUDIT_MODE=single
JDCLOUD_OPENAI_AUDIT_MODEL=GPT-5.5
JDCLOUD_OPENAI_AUDIT_MODELS=GPT-5.5,Kimi-K2.6
```

规则：

- `AUDIT_MODE=single` 时沿用当前 `JDCLOUD_OPENAI_AUDIT_MODEL`。
- `AUDIT_MODE=dual` 时读取 `JDCLOUD_OPENAI_AUDIT_MODELS`。
- 第一版要求 dual 模式下刚好两个模型，且都走 JDCloud chat 图片审核接口。
- 配置错误应在应用启动或任务开始时给出明确错误，不允许静默回退。

## 模块边界

现有模块职责保持清晰：

- `app/openai_audit.py`：继续负责单模型图片审核、JSON 解析和归一化。
- `app/task_runner.py`：负责任务编排、产物写入、状态更新和报告生成。
- `app/report_renderer.py`：负责 HTML 展示。

新增一个小模块：

- `app/audit_merge.py`：只负责融合两个已归一化的 audit JSON。

`audit_merge.py` 不调用网络，不读写数据库，不生成截图，只接收结构化 JSON 并返回结构化 JSON。

## 数据流

单张图片在 dual 模式下的处理流程：

1. 用 `GPT-5.5` 调用现有 `audit_image_with_chat`。
2. 写入 `audit-gpt-5.5.json`。
3. 用 `Kimi-K2.6` 调用现有 `audit_image_with_chat`。
4. 写入 `audit-kimi-k2.6.json`。
5. 调用 `audit_merge.merge_audits()` 生成融合结果。
6. 写入兼容旧报告入口的 `audit.json`。
7. 用融合后的 `issues` 生成 `issues.json`、`annotated.png` 和问题截图。
8. HTML 报告读取融合后的 `audit.json`，并展示模型对比信息。

## 融合输出结构

融合后的 `audit.json` 保留当前顶层字段，确保旧渲染逻辑基本可用：

- `screen_context`
- `overall_conclusion`
- `major_issues`
- `passes`
- `issues`
- `sample_points`
- `regions`
- `distances`
- `checklist`
- `cannot_verify`

额外增加：

```json
{
  "model_comparison": {
    "models": ["GPT-5.5", "Kimi-K2.6"],
    "agreed_issues": [],
    "gpt_only_issues": [],
    "kimi_only_issues": [],
    "conflicts": [],
    "model_failures": []
  }
}
```

`issues` 是最终用于截图和详细问题清单的融合列表。每个 issue 增加来源信息：

```json
{
  "id": "问题-001",
  "source_models": ["GPT-5.5", "Kimi-K2.6"],
  "agreement": "both"
}
```

`agreement` 取值：

- `both`
- `gpt_only`
- `kimi_only`

## 合并规则

第一版使用本地规则，不做复杂算法。

两个 issue 视为同一问题的条件满足任一即可：

- bbox 有重叠，IoU 达到阈值。
- `category` 相近且 `location` 文本相近。
- 当前表现、位置、建议中命中相同核心关键词。

合并同一问题时：

- `severity` 取更高等级。
- `source_models` 合并去重。
- `current_observation` 优先使用更具体、更长且中文完整的一方。
- `spec_expectation` 和 `recommendation` 取信息更完整的一方。
- `bbox` 优先使用非空且面积更合理的一方；明显过大或越界的 bbox 降级。
- `confidence` 取较高值；无法比较时保留原值。

单模型独有问题不丢弃，进入最终 `issues`，但 `agreement` 标记为 `gpt_only` 或 `kimi_only`。

## 分歧处理

第一版只处理明确、可解释的分歧：

- 一个模型判定合规，另一个模型判定不合规。
- 两个模型对同一位置给出相反结论。
- 一个模型明确写入 `cannot_verify`，另一个模型给出确定问题。

分歧写入 `model_comparison.conflicts`，并在报告中进入“需人工复核”区域。

## 失败策略

- 两个模型都成功：任务成功，输出完整双模型融合报告。
- 一个模型成功、一个模型失败：任务成功，报告显示“单模型降级”，并在 `model_failures` 记录失败模型和错误摘要。
- 两个模型都失败：任务失败，沿用当前“全部图片审核失败”路径。

单模型失败不能导致已成功模型的结果被丢弃。

## 报告展示

HTML 报告保持当前结构，新增一个“模型对比”区域：

- 双方一致的问题
- 仅 GPT-5.5 发现的问题
- 仅 Kimi-K2.6 发现的问题
- 需人工复核的分歧
- 模型失败信息

“核心结论”使用融合后的本地模板生成，避免第三次 LLM 仲裁造成新幻觉。

问题截图继续使用融合后的 `issues`。截图文件名仍由现有标注流程生成，避免新命名体系带来兼容成本。

## 测试计划

新增单元测试覆盖 `audit_merge.py`：

- 两个模型发现同一 bbox 问题时合并为一个 issue。
- 两个模型发现不同问题时都保留。
- GPT-only 和 Kimi-only 能正确标记。
- 严重程度取更高等级。
- bbox 为空时选用另一方非空 bbox。
- 一个模型失败时生成降级结果。
- 两个模型失败时返回明确失败状态。

新增任务级测试：

- dual 模式写入 `audit-gpt-5.5.json`、`audit-kimi-k2.6.json`、`audit.json`。
- 融合后的 `issues.json` 可用于生成标注截图。
- single 模式行为保持不变。

## 风险

- 成本和耗时约增加一倍。第一版先串行执行，稳定后再考虑并行。
- 双模型可能同时漏检同一问题。融合不能替代规范和规则校验。
- 单模型独有问题可能包含误报。因此报告必须分层展示，不能把单方发现伪装成双方共识。
- bbox 仍可能来自模型误判。现有 bbox 归一化和截图修正逻辑必须继续保留。

## 验收标准

- 开启 dual 模式后，同一张图片会生成两份原始模型 JSON 和一份融合 JSON。
- 报告中能明确看到双方一致、GPT-only、Kimi-only、分歧和失败降级信息。
- 如果其中一个模型失败，任务仍能在另一个模型成功时产出报告。
- 融合后的问题列表能生成正确的 `issues.json`、`annotated.png` 和问题截图。
- 关闭 dual 模式后，当前单模型审核行为不变。
