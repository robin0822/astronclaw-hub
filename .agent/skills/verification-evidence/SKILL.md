---
name: verification-evidence
description: 用于验收取证，适用于根据 requirements.md 和 plan.md 执行正向、反向、回归验证，记录页面、接口、日志、指标和审计证据，并生成 .agent/memory/active/<需求ID>/verification.md。
---

# 验收取证 Skill

## 目标

用可回读证据证明需求已完成，输出：

```text
.agent/memory/active/<需求ID>/verification.md
```

## 必读材料

- `.agent/memory/active/<需求ID>/requirements.md`
- `.agent/memory/active/<需求ID>/plan.md`
- `.agent/memory/active/<需求ID>/progress.md`
- `.agent/templates/verification.template.md`

## 工作步骤

1. 从 `requirements.md` 提取验收标准。
2. 从 `plan.md` 提取验证方案。
3. 逐项执行正向用例、反向用例和回归用例。
4. 记录命令、页面路径、接口响应、日志、指标或截图链接。
5. 发现问题时回到代码执行或 CR 协同阶段。
6. 给出明确验收结论和剩余风险。

## 输出要求

`verification.md` 必须包含：

- 环境信息。
- 正向用例证据。
- 反向用例证据。
- 回归用例证据。
- 日志与指标。
- 验收结论。

## 质量门

结项前必须满足：

- 每个 P0 验收标准都有结果。
- 失败项有明确处理或延期说明。
- 高风险问题不能只写“待后续处理”，必须有负责人和处置路径。

