---
name: requirement-intake
description: 用于读取和整理一个新需求的入口信息，适用于从用户描述、PRD、Issue、Aone、现有 wiki/codemap 中生成 .agent/memory/active/<需求ID>/intake.md，并建立本次需求的初始上下文快照。
---

# 需求读取 Skill

## 目标

把一个新需求整理成可继续推进的入口档案，输出到：

```text
.agent/memory/active/<需求ID>/intake.md
```

## 必读材料

优先读取：

- `docs/wiki/project-overview.md`
- `docs/wiki/lobster-module-scope.md`
- `docs/codemap/existing-platform-map.md`
- `docs/codemap/lobster-module-map.md`
- `docs/codemap/lobster-data-model.md`
- `.agent/templates/intake.template.md`

如果用户提供了外部文档、Issue、PRD 或链接，也要纳入“来源链接”和“初始摘要”。

## 工作步骤

1. 确认需求 ID；没有 ID 时，为演示需求使用 `LOBSTER-0001`。
2. 创建 `.agent/memory/active/<需求ID>/`。
3. 基于模板生成 `intake.md`。
4. 记录需求来源、目标、相关模块、已有上下文和待确认问题。
5. 不做技术方案，不写代码，只建立上下文快照。

## 输出要求

`intake.md` 必须包含：

- 需求 ID、标题、来源、负责人。
- 关联链接或来源文件。
- 需求的自然语言摘要。
- 相关长期知识和代码地图。
- 初始待确认问题。

## 完成标准

- 需求目录已创建。
- `intake.md` 能让下一个 skill 在不重新询问背景的情况下继续澄清需求。
- 临时判断留在项目记忆中，不直接写入 `docs/wiki/`。

