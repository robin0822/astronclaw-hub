# Agent 项目记忆

项目记忆用于记录每个需求的完整交付过程。

`active/` 存放进行中的需求，`archive/` 存放已结项的需求。
每个需求都应有独立目录，例如：

```text
.agent/memory/active/AONE-12345/
  intake.md
  requirements.md
  plan.md
  progress.md
  verification.md
  cr-comments.md
  closeout.md
```

项目记忆是临时事实层。不要把所有过程记录直接升级到 `docs/wiki/`。
结项时，只将经过确认的稳定、可复用知识沉淀到 `docs/wiki/` 或 `docs/codemap/`。
