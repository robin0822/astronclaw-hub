---
name: technical-plan
description: 用于把已确认的 requirements.md 转换为技术方案，适用于生成 .agent/memory/active/<需求ID>/plan.md，覆盖前端页面、后端 API、数据模型、适配层、测试策略、验收方案和回滚方案。
---

# 技术方案 Skill

## 目标

基于已确认需求生成可执行技术方案，输出到：

```text
.agent/memory/active/<需求ID>/plan.md
```

## 必读材料

- `.agent/memory/active/<需求ID>/requirements.md`
- `.agent/templates/plan.template.md`
- `docs/codemap/existing-platform-map.md`
- `docs/codemap/lobster-module-map.md`
- `docs/codemap/lobster-data-model.md`

## 工作步骤

1. 说明当前状态和目标状态。
2. 拆解影响范围：前端、后端、数据、配置、任务、监控。
3. 设计 API 和数据模型变更。
4. 明确 Claw Proxy 或外部能力的适配边界。
5. 制定实现步骤。
6. 制定测试策略、验收方案和回滚方案。

## 输出要求

`plan.md` 必须包含：

- 当前状态。
- 目标状态。
- 影响范围。
- 实现步骤。
- 测试策略。
- 验收方案。
- 回滚方案。
- 确认记录。

## 质量门

进入代码执行前必须满足：

- 每个 P0 验收标准都有对应实现和验证路径。
- 关键数据表、API、页面入口已明确。
- 涉及敏感信息、权限、审计的设计不留空。
- 回滚方案可执行。

