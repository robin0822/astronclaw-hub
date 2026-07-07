# AstronClaw 后端交付文档目录

本目录基于根目录下 1 份需求文档和 2 份对接文档整理生成，供后端开发、前端联调和项目评审使用。

| 文件 | 用途 |
| --- | --- |
| `01-backend-architecture-design.md` | 后端架构设计：系统边界、总体架构、代码目录、模块职责、数据模型、状态机、外部对接、安全与可观测性 |
| `02-requirement-implementation-plan.md` | 需求实现技术方案：按 FR-01 至 FR-11 拆解实现方式、关键流程、错误处理和 P0/P1/P2 落地策略 |
| `03-code-logic-overview.md` | 代码逻辑概述：请求链路、创建部署、生命周期、批量任务、同步、告警、Skill、知识、成本、审计、Claw Proxy 客户端逻辑 |
| `04-frontend-api-documentation.md` | 提供给前端阅读的接口文档：业务后端 API、请求响应、分页、错误码、智能体、批量、权限、Skill、知识、模型、监控、成本、审计接口 |
| `05-backend-test-plan.md` | 后端测试方案：测试目标、分层策略、P0 需求测试矩阵、核心用例、Claw Proxy 契约、安全合规、异常恢复、CI 门禁和验收清单 |

重要边界：

1. 前端统一调用业务后端 `/api/v1/astron-claw`。
2. Claw Proxy `/api/v1/bot` 是后端到沙箱层的服务间接口，不暴露给前端。
3. `CLAW_PROXY_AUTH_TOKEN`、模型 `apiKey`、租户 `api_secret` 等密钥不得下发到前端。
4. 当前仓库未提供实际后端源码，文档中的代码架构与逻辑为建议落地设计。

阅读建议：

1. 后端负责人先读 `02-requirement-implementation-plan.md` 的需求追踪矩阵，确认完整范围。
2. 架构评审读 `01-backend-architecture-design.md` 与 `02-requirement-implementation-plan.md`。
3. 后端开发读 `03-code-logic-overview.md`。
4. 前端联调读 `04-frontend-api-documentation.md`，其中“补充接口”章节覆盖 Claw Proxy 能力在业务后端侧的代理接口。
5. 测试负责人和验收人员读 `05-backend-test-plan.md`，按测试矩阵和验收检查清单准备用例、报告和联调门禁。
