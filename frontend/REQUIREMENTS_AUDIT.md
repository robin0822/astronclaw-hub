# AstronClaw 前端需求审计

审计日期：2026-07-02
范围：`astronclaw-chinalife-requirements.md`、`backend-delivery-docs/04-frontend-api-documentation.md`、`frontend/src`。

## 本次已完成

- 前端业务 API 统一切到 `/api/v1/astron-claw`；各功能接口已拆分到 `src/api` 根目录下的 kebab-case 模块文件，业务代码按需从各自 API 文件直接导入。
- 已删除旧的 `astronClaw.ts` / `clawProxy.ts` 兼容入口，并移除 `src/api/index.ts` 聚合入口。
- 品牌恢复为“讯飞 AstronClaw”，侧边栏标题由 `P0 核心交付` 改为“核心功能”，并恢复图标式侧边栏；网页 favicon 与龙虾标志一致。
- `智能体龙虾管理` 改为官方 AstronClaw 单页管理，不再提供自定义智能体入口，本地种子智能体类型也统一为官方。
- `npm run build` 已通过，Vite 仅提示 chunk 体积超过 500 kB。

## FR-01.2 专项核对

| 要求                                                                                                                                                                               | 状态   | 前端证据                                                      |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ | ------------------------------------------------------------- |
| 支持按智能体展示                                                                                                                                                                   | 已完成 | `AgentsPage.tsx` 按智能体卡片展示。                           |
| 状态筛选：运行中、已停止、异常、部署中、升级中                                                                                                                                     | 已完成 | `STATUS_OPTIONS` 覆盖五类状态。                               |
| 按名称、部门、负责人、模型搜索                                                                                                                                                     | 已完成 | 搜索框将 `keyword` 传给 `/agents`，本地兜底同时匹配这些字段。 |
| 卡片字段：实例名、instanceId、状态、版本、部门、负责人、容器数、Skill 数、绑定知识库、主/备模型、CPU、内存、存储、GPU、并发、单日上限、超时、当前/最大服务人数、QPS、创建/更新时间 | 已完成 | `agentFields()` 和详情配置区完整渲染。                        |
| 详情分类：配置、运行日志、部署历史、版本历史、绑定 Skill、绑定知识库、调用统计、告警记录、审计记录                                                                                 | 已完成 | `DETAIL_TABS` 覆盖 9 类，详情调用 `/agents/{agentId}`。       |

## 其他需求缺口

- FR-01.3 创建前校验：创建表单已按 `POST /agents` 组织 payload，但模型可用性、资源配额、席位授权、部门权限、Skill 权限、知识库权限仍依赖后端返回校验结果，前端尚未做逐项校验态展示。
- FR-01.4 批量管理：已支持选中实例后批量部署、启动、停止、重启、升级、归档、删除；按筛选结果、部门、标签、导入清单、批量模型切换、批量 Skill 同步和批量策略校验还需要后续页面入口。
- FR-01.8 远程运维：详情已展示运行日志和历史信息；部署日志、升级日志、容器日志、模型调用日志的实时入口，以及远程参数调整 UI 还需要后端日志/参数接口联调后补齐。
- FR-02 至 FR-11：当前项目已有组织权限、监控告警、模型网关、成本、运维、Skill、知识/记忆、共享、安全、诊断等页面结构；其中本次只把诊断修复切到 `/diagnostics/{diagnosisId}/fix`，其余页面多数仍基于本地演示数据，需要继续按后端文档逐页替换为真实接口。
- FR-09 消息渠道：需求文档标注“暂时不做”，当前侧边栏未开放渠道入口，但路由与页面仍保留，后续若启用需接入后端渠道接口。

## 2026-07-02 接口文档更新补充

- 已补齐 `04-frontend-api-documentation.md` 新增 13-16 章的前端 API client：实例同步、实例日志、远程运行参数、运行时 Skill、Skill 环境变量、沙箱文件、记忆预览、AstronMem 插件、定时任务、Agent Team、备份恢复、审批、共享授权、席位、模型配额与路由、渠道、业务系统、诊断知识库。
- `智能体龙虾管理` 详情页已新增：`POST /agents/{agentId}/sync` 手动同步、`GET /agents/{agentId}/logs` 按日志类型查询、`PUT /agents/{agentId}/runtime-config` 保存远程运行参数。
- 已新增本地 `.env`，并更新 `.env.example` 为 `VITE_ASTRONCLAW_API_BASE_URL`、`VITE_ASTRONCLAW_AUTH_TOKEN`、`VITE_ASTRONCLAW_AUTHORIZATION`、`BACKEND_BASE_URL`；真实 `.env` 已加入 frontend `.gitignore`。
