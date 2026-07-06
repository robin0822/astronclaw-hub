---
name: cr-collaboration
description: 用于 CR/PR 协同和评论处理，适用于记录评审链接、读取未解决评论、更新文档或代码、回复处理结果，并维护 .agent/memory/active/<需求ID>/cr-comments.md。
---

# CR 协同 Skill

## 目标

让人工评审和 Agent 修改过程可追踪，输出和维护：

```text
.agent/memory/active/<需求ID>/cr-comments.md
```

## 必读材料

- `.agent/memory/active/<需求ID>/requirements.md`
- `.agent/memory/active/<需求ID>/plan.md`
- `.agent/memory/active/<需求ID>/progress.md`
- `.agent/templates/cr-comments.template.md`

## 工作步骤

1. 记录 CR/PR 链接、提交和评审范围。
2. 收集未解决评论。
3. 判断评论类型：需求语义、方案设计、代码实现、测试、风险。
4. 对需求或方案变更，回到对应文档更新并重新确认。
5. 对代码评论，修改代码、补测试、提交变更。
6. 在 `cr-comments.md` 记录处理结果、提交和剩余问题。

## 输出要求

`cr-comments.md` 必须包含：

- 未解决评论。
- 已解决评论。
- 处理结果。
- 相关提交。
- 被重新打开的需求或技术决策。

## 质量门

进入验收前必须满足：

- 所有阻塞评论已处理或明确延期。
- 需求范围变化已回写 `requirements.md` 或 `plan.md`。
- 处理结果有提交或文档链接可追踪。

