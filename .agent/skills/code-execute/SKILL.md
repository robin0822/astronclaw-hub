---
name: code-execute
description: 用于按已确认 plan.md 执行代码实现，适用于创建分支、修改代码、补测试、更新 progress.md，并保证改动范围与需求和技术方案一致。
---

# 代码执行 Skill

## 目标

按已确认技术方案完成实现，并持续更新：

```text
.agent/memory/active/<需求ID>/progress.md
```

## 必读材料

- `.agent/memory/active/<需求ID>/requirements.md`
- `.agent/memory/active/<需求ID>/plan.md`
- `.agent/templates/progress.template.md`
- `docs/codemap/`

## 工作步骤

1. 确认当前 Git 分支；如需新分支，使用 `feature/<需求ID>-<简短名称>`。
2. 从 `plan.md` 的验收标准、状态机、接口契约、错误码和审计要求抽取测试用例。
3. 先写会失败的行为测试，再实现生产代码让测试通过；不得先写实现再补只验证实现细节的测试。
4. 按 `plan.md` 的实现步骤推进，不做未列入范围的扩展。
5. 每完成一个阶段，更新 `progress.md`。
6. 执行项目已有测试、lint、类型检查或构建命令。
7. 提交前复查 diff 是否只覆盖本次需求。
8. push 前执行 `scripts/quality-gate.sh`；即使忘记执行，`.githooks/pre-push` 也会自动拦截。

## 输出要求

- 代码改动。
- 必要测试。
- `progress.md`。
- 关键提交记录。

## 质量门

代码执行完成前必须满足：

- 改动能追溯到 `requirements.md` 或 `plan.md`。
- 生产代码行为变化有具体测试锚点，并通过 `scripts/diff-to-test-map.cjs` 检查。
- 无关重构不混入本次需求。
- 测试失败或未执行必须记录原因。
- `scripts/agent-code-review.cjs` 没有 actionable 发现。
- git push 必须通过 `.githooks/pre-push` 的硬门禁。
