---
name: closeout-learning
description: 用于需求结项和知识沉淀，适用于汇总 intake、requirements、plan、progress、cr-comments、verification，生成 closeout.md，并将稳定知识候选沉淀到 docs/wiki 或 docs/codemap。
---

# 结项沉淀 Skill

## 目标

完成需求结项，总结过程经验，并筛选可复用知识，输出：

```text
.agent/memory/active/<需求ID>/closeout.md
```

必要时更新：

```text
docs/wiki/
docs/codemap/
```

## 必读材料

- `.agent/memory/active/<需求ID>/intake.md`
- `.agent/memory/active/<需求ID>/requirements.md`
- `.agent/memory/active/<需求ID>/plan.md`
- `.agent/memory/active/<需求ID>/progress.md`
- `.agent/memory/active/<需求ID>/cr-comments.md`
- `.agent/memory/active/<需求ID>/verification.md`
- `.agent/templates/closeout.template.md`

## 工作步骤

1. 汇总需求目标、最终交付和验证结果。
2. 区分三类材料：
   - 稳定知识：可进入 `docs/wiki/` 或 `docs/codemap/`。
   - 流程改进：可改进 skill、模板、检查规则。
   - 仅归档记录：临时调试、一次性上下文和中间状态。
3. 生成 `closeout.md`。
4. 对稳定知识候选，按需更新 `docs/wiki/` 或 `docs/codemap/`。
5. 人工确认后，将需求目录从 `active/` 移入 `archive/`。

## 输出要求

`closeout.md` 必须包含：

- 需求结果。
- 交付摘要。
- 验收摘要。
- 稳定知识候选。
- 流程改进候选。
- 仅归档记录。
- 结项确认。

## 质量门

结项完成前必须满足：

- 验收结论明确。
- 稳定知识和临时材料没有混在一起。
- 长期知识更新可追溯到本次需求。
- 未完成事项有负责人、范围和后续处理建议。

