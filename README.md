# atsron-claw-hub

运营管理项目仓库。

## 项目说明

该仓库用于承载 `atsron-claw-hub` 运营管理项目。

## Agent 记忆结构

该仓库采用单仓库版 Agent 记忆结构：

- `docs/wiki/`：长期可复用的业务知识。
- `docs/codemap/`：稳定的代码地图、模块职责和系统说明。
- `.agent/memory/active/`：进行中的需求项目记忆。
- `.agent/memory/archive/`：已结项的需求项目记忆。
- `.agent/templates/`：各交付阶段可复用的项目记忆模板。

每个新需求开始时，在 `.agent/memory/active/<需求ID>/` 下创建独立目录，
把 `.agent/templates/` 中的模板复制进去，并随着需求从进入、澄清、方案、
实现、验收、结项逐步更新。

项目记忆用于记录单个需求的过程事实；长期知识只接收结项后确认有复用价值的内容。
