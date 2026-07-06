---
name: requirement-clarify
description: 用于需求澄清和范围确认，适用于基于 intake.md、docs/wiki、docs/codemap 生成 .agent/memory/active/<需求ID>/requirements.md，明确目标、范围、业务规则、验收标准、风险和待确认事项。
---

# 需求澄清 Skill

## 目标

把入口需求澄清为可评审、可验收的需求说明，输出到：

```text
.agent/memory/active/<需求ID>/requirements.md
```

## 必读材料

- `.agent/memory/active/<需求ID>/intake.md`
- `.agent/templates/requirements.template.md`
- `docs/wiki/`
- `docs/codemap/`

## 工作步骤

1. 读取 `intake.md` 和长期知识。
2. 区分本次范围、非本次范围和后续预留。
3. 把模糊需求改写为明确业务规则。
4. 写出可验证的验收标准。
5. 标出风险和待确认事项。
6. 如待确认事项影响范围或实现路线，停止进入技术方案阶段。

## 输出要求

`requirements.md` 必须包含：

- 目标。
- 本次范围。
- 非本次范围。
- 用户与业务规则。
- 验收标准。
- 风险。
- 待确认事项。
- 确认记录。

## 质量门

进入技术方案前必须满足：

- P0 范围清晰。
- 至少有一组可验收标准。
- 非本次范围已显式列出。
- 关键待确认事项已解决，或明确由人工确认后继续。

