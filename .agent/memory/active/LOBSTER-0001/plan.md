# 技术方案

## 当前状态

AstronClaw 当前仓库以 Agent 工作流文档、长期知识和代码地图为主，已明确本次需求编号为 `LOBSTER-0001`，功能建设落在现有 ops 平台的智能体管理模块。

已确认的业务边界如下：

- 前端入口沿用 `/agents`，不新增独立“龙虾”一级菜单。
- 业务后端统一对前端暴露 `/api/v1/astron-claw`。
- 前端不得直接调用 Claw Proxy `/api/v1/bot`。
- P0 聚焦龙虾实例管理最小闭环：列表、详情、创建、部署、启停、重启、删除、Skill/知识库绑定、状态同步、基础日志和操作审计。
- 批量、成本、渠道、诊断、复杂审批、Agent Team 等能力仅做后续预留，不进入 P0 验收。
- Claw Proxy `/api/v1/bot` 的部署、启停、重启、Skill 安装、状态查询接口契约和错误码已有可联调版本。
- P0 验收要求真实接入监控/日志系统；开发环境 mock 仅作为联调兜底，响应必须标记 `dataSource=mock`。

当前仓库还没有实际前后端工程代码。进入实现阶段前，需要在当前仓库补充或接入 ops 平台前端、业务后端、任务 worker、数据库迁移和外部适配层代码结构。

## 目标状态

在现有 ops 平台中完成智能体龙虾管理 P0 闭环，使平台管理员、运营人员、运维人员和业务负责人可以在授权范围内完成：

- 在 `/agents` 查询、筛选和查看龙虾实例列表。
- 在 `/agents/:id` 查看基础配置、运行状态、模型、Skill、知识库、部署历史、基础日志、告警摘要和审计记录。
- 创建龙虾并完成权限、数据范围、席位、模型、资源、Skill 和知识库前置校验。
- 通过异步部署任务调用 Claw Proxy，部署成功后回写 `proxy_instance_id` 并流转为 `running`。
- 执行启动、停止、重启、删除等生命周期操作，并记录状态事件和审计日志。
- 在授权范围内绑定或解绑 Skill、知识库，运行中变更通过后端适配 Claw Proxy。
- 周期性同步运行状态、资源指标、服务状态和外部实例可用性，列表和详情读取最近一次快照。
- 查询运行日志、部署日志、操作日志，敏感字段脱敏，敏感日志查看或导出写审计。

核心架构目标：

```text
浏览器 /ops
  -> /agents, /agents/:id
  -> 业务后端 /api/v1/astron-claw
  -> RBAC / 数据范围 / 席位 / 审计 / 任务编排 / 错误转换
  -> Claw Proxy 适配层 /api/v1/bot
  -> 监控系统、日志系统、模型、Skill、知识库、组织权限等平台能力
```

## 影响范围

- 模块：
  - 前端 `agents` 模块：列表页、详情页、创建表单、生命周期操作、Skill/知识库绑定、日志和审计视图。
  - 后端 `astron-claw` 模块：API、权限校验、聚合查询、状态机、任务编排、审计写入。
  - Worker 模块：部署任务、生命周期任务、状态同步任务、日志索引任务。
  - 适配层：Claw Proxy、监控系统、日志系统、模型管理、Skill 管理、知识库、席位、组织权限。
- API：
  - 新增或补齐 `/api/v1/astron-claw/agents` 资源接口。
  - 新增部署、启停、重启、删除、绑定、日志、审计等子资源接口。
  - 统一分页、筛选、错误码、数据来源、脱敏字段和任务状态响应。
- 数据：
  - 新增 P0 最小表集合：`agents`、`agent_versions`、`agent_deploy_tasks`、`agent_runtime_snapshots`、`agent_runtime_configs`、`agent_bind_skills`、`agent_bind_knowledge`、`agent_state_events`、`agent_logs_index`、`audit_logs`。
  - 所有高影响操作必须写入 `audit_logs`。
  - 每次生命周期状态变化必须写入 `agent_state_events`。
- 配置：
  - `CLAW_PROXY_BASE_URL`、鉴权凭据引用、超时、重试、幂等键策略。
  - 状态同步周期、日志数据源、监控数据源、mock 开关、数据源标识。
  - 审计保留周期、敏感字段脱敏规则、可导出日志权限。
- 任务：
  - 部署任务：异步调用 Claw Proxy 创建运行实例。
  - 生命周期任务：启动、停止、重启。
  - 状态同步任务：周期拉取 Claw Proxy 和监控系统状态。
  - 日志索引任务：维护 `agent_logs_index` 与外部日志系统查询索引。
- 监控：
  - 列表和详情运行态字段来自 `agent_runtime_snapshots`。
  - 详情页展示最近同步时间、数据来源和快照新鲜度。
  - Claw Proxy 调用失败率、部署任务耗时、同步延迟、日志查询失败率需要有基础指标或日志可追踪。

## 模块设计

### 前端模块

- `AgentsList`：
  - 路由：`/agents`
  - 能力：状态、名称、部门、负责人、模型筛选；展示 P0 列表字段；提供创建入口、详情跳转和授权范围内的快捷生命周期操作。
  - 数据来源：`GET /api/v1/astron-claw/agents`。
- `AgentDetail`：
  - 路由：`/agents/:id`
  - 能力：基础信息、运行快照、模型配置、Skill、知识库、部署历史、日志、告警摘要、审计。
  - 数据来源：详情接口为主，日志和审计可按分页独立请求。
- `AgentCreate`：
  - 路由：`/agents/create` 或创建弹窗。
  - 字段：名称、描述、部门、负责人、主模型、备用模型、资源配置、可选 Skill、可选知识库。
  - 校验：前端做交互校验，后端做最终权限和业务校验。
- `AgentBindingPanel`：
  - 负责 Skill 和知识库查看、绑定、解绑。
  - 运行中实例变更时展示任务状态或操作结果。
- `AgentLogAuditPanel`：
  - 基础日志和审计日志分页查询。
  - 敏感日志查看或导出只展示后端授权后的脱敏结果。

### 后端模块

- `agent-service`：
  - 负责龙虾主数据、版本快照、列表筛选、详情聚合和编辑规则。
- `agent-lifecycle-service`：
  - 负责状态机、启动、停止、重启、删除、状态事件写入。
- `agent-deploy-service`：
  - 负责部署任务创建、幂等控制、任务状态更新和失败记录。
- `agent-binding-service`：
  - 负责 Skill、知识库绑定关系校验、保存和运行中变更适配。
- `agent-runtime-sync-service`：
  - 负责同步 Claw Proxy、监控系统运行态并写入快照。
- `agent-log-service`：
  - 负责日志索引、外部日志系统查询、脱敏和日志数据来源标记。
- `audit-service`：
  - 负责创建、编辑、部署、启停、删除、绑定、日志查看/导出等审计记录。
- `claw-proxy-adapter`：
  - 只封装 Claw Proxy `/api/v1/bot` 调用、鉴权、超时、重试、错误转换，不承载平台业务权限。

### 数据流

创建流程：

```text
前端创建表单
  -> POST /api/v1/astron-claw/agents
  -> 登录态 / RBAC / 数据范围 / 席位 / 模型 / 资源 / Skill / 知识库校验
  -> 写 agents、agent_versions、agent_runtime_configs、绑定关系
  -> 写 audit_logs、agent_state_events
  -> 返回 agent_id 和初始状态
```

部署流程：

```text
前端触发部署
  -> POST /api/v1/astron-claw/agents/{id}/deploy
  -> 校验状态、权限、关键配置完整性
  -> 写 agent_deploy_tasks，状态置为 deploying
  -> Worker 调用 Claw Proxy /api/v1/bot
  -> 成功：回写 proxy_instance_id，状态 running，写快照、事件、审计
  -> 失败：记录阶段和错误码，状态 abnormal 或 stopped，写事件、审计
```

运行态查询流程：

```text
状态同步任务
  -> Claw Proxy 状态查询 + 监控系统指标
  -> 写 agent_runtime_snapshots
  -> GET 列表/详情读取最近快照
  -> 响应包含 snapshotTime、dataSource、freshness
```

生命周期流程：

```text
前端启停/重启/删除
  -> 后端校验权限、数据范围和当前状态
  -> 对需要外部动作的操作创建任务并调用 Claw Proxy
  -> 写 agent_state_events 和 audit_logs
  -> 删除仅允许 stopped -> deleted 软删除
```

## 接口与数据

### API 设计

统一前缀：`/api/v1/astron-claw`

```text
GET    /agents
POST   /agents
GET    /agents/{id}
PATCH  /agents/{id}
POST   /agents/{id}/deploy
GET    /agents/{id}/deploy-tasks
POST   /agents/{id}/start
POST   /agents/{id}/stop
POST   /agents/{id}/restart
DELETE /agents/{id}
GET    /agents/{id}/skills
PUT    /agents/{id}/skills
GET    /agents/{id}/knowledge-bases
PUT    /agents/{id}/knowledge-bases
GET    /agents/{id}/logs
GET    /agents/{id}/audit-logs
```

列表查询参数：

- `status`：生命周期状态。
- `keyword`：名称或运行实例 ID 模糊查询。
- `departmentId`：部门筛选，必须落在用户数据范围内。
- `ownerId`：负责人筛选。
- `modelId`：主模型或备用模型筛选。
- `page`、`pageSize`：分页。

创建请求核心字段：

```json
{
  "name": "string",
  "description": "string",
  "departmentId": "string",
  "ownerId": "string",
  "primaryModelId": "string",
  "fallbackModelId": "string",
  "resourceProfile": {
    "cpu": "string",
    "memory": "string",
    "gpu": "string",
    "storage": "string"
  },
  "skillIds": ["string"],
  "knowledgeBaseIds": ["string"]
}
```

通用响应要求：

- 不返回完整模型密钥、沙箱令牌或可直接调用外部运行时的凭据。
- 运行态字段返回 `snapshotTime`、`dataSource` 和必要的新鲜度标识。
- mock 数据响应必须显式返回 `dataSource=mock`。
- 错误响应包含平台业务错误码、可读信息和必要的外部错误映射，不直接透出外部敏感细节。

### 状态机

P0 状态集合：

- `draft`：已创建但尚未部署。
- `deploying`：部署任务执行中。
- `running`：运行中。
- `stopped`：已停止。
- `abnormal`：运行或部署异常。
- `archived`：已归档，P0 预留。
- `deleted`：已软删除。

关键约束：

- `deploying` 状态不允许重复部署、删除或并发修改关键配置。
- `running` 状态不允许删除，必须先手动停止到 `stopped`。
- 删除只做软删除，保留审计、状态事件和历史记录。
- 每次状态变化写 `agent_state_events`。
- 创建后初始状态仍待产品最终确认；未确认前计划按 `draft` 实现，并在创建响应中返回初始状态。

### 数据模型

`agents`：

- 主字段：`id`、`bot_id`、`proxy_instance_id`、`name`、`description`、`status`、`department_id`、`owner_id`、`primary_model_id`、`fallback_model_id`、`resource_profile`、`created_by`、`created_at`、`updated_at`、`deleted_at`。
- 索引建议：`department_id + name + deleted_at`、`status`、`owner_id`、`primary_model_id`、`proxy_instance_id`。
- 名称唯一性待确认；未确认前按同一部门内未删除记录唯一处理。

`agent_versions`：

- 保存每次关键配置变更快照，支撑部署历史和后续回滚预留。
- 字段建议：`agent_id`、`version_no`、`config_snapshot`、`change_reason`、`created_by`、`created_at`。

`agent_deploy_tasks`：

- 字段建议：`agent_id`、`task_type`、`status`、`stage`、`idempotency_key`、`external_request_id`、`external_error_code`、`business_error_code`、`error_message`、`started_at`、`finished_at`。

`agent_runtime_snapshots`：

- 字段建议：`agent_id`、`proxy_instance_id`、`runtime_status`、`container_count`、`current_users`、`qps`、`resource_usage`、`service_health`、`alert_summary`、`data_source`、`snapshot_at`。

`agent_runtime_configs`：

- 保存资源配置、运行参数、模型路由策略引用，不保存明文密钥。

`agent_bind_skills`、`agent_bind_knowledge`：

- 保存绑定关系、绑定版本、状态、创建人和创建时间。
- 禁用、未审核、无权限、已删除的 Skill/知识库不允许绑定。

`agent_state_events`：

- 字段：`agent_id`、`from_status`、`to_status`、`reason`、`operator_id`、`task_id`、`created_at`。

`agent_logs_index`：

- 保存外部日志定位信息、日志类型、时间范围、数据源、脱敏状态。
- 实际日志内容优先留在日志系统，不在业务库长期保存大文本。

`audit_logs`：

- 记录操作人、操作对象、操作类型、结果、请求摘要、风险等级、脱敏后的上下文、时间。
- 审计保留周期默认不少于 180 天，最终以客户合规要求为准。

## Claw Proxy 与外部能力适配边界

业务后端负责：

- 平台登录态、RBAC、数据范围、席位、模型、Skill、知识库权限校验。
- 龙虾主数据、版本、绑定关系、任务、状态事件、审计持久化。
- 外部错误码到平台业务错误码的转换。
- 幂等键生成、任务状态推进、超时和失败记录。
- 敏感字段脱敏和审计。

Claw Proxy 适配层负责：

- 调用 `/api/v1/bot` 完成部署、启动、停止、重启、Skill 安装或卸载、状态查询。
- 注入后端持有的鉴权凭据或密钥引用。
- 设置连接超时、请求超时、有限重试和熔断策略。
- 返回标准化外部响应，不直接暴露给前端。

Claw Proxy 不负责：

- 平台用户权限判断。
- 平台审计落库。
- 部门、席位、模型、Skill、知识库的数据范围判断。
- 前端页面聚合数据结构。

监控和日志系统适配：

- 运行指标从真实监控系统读取，并写入 `agent_runtime_snapshots`。
- 日志查询通过日志系统完成，业务后端只做授权、索引、脱敏、分页和数据来源标识。
- 若开发环境使用 mock，接口必须返回 `dataSource=mock`，且不得作为 P0 验收证据。

## 实现步骤

1. 建立工程骨架
   - 在当前仓库补充或接入 ops 前端、业务后端、worker、数据库迁移和配置目录。
   - 明确前端路由、后端模块命名、数据库迁移工具和测试框架。
2. 定义接口契约和错误码
   - 固化 `/api/v1/astron-claw` API。
   - 定义分页、筛选、任务状态、错误响应、数据来源、脱敏字段。
   - 对齐 Claw Proxy `/api/v1/bot` 契约、超时、重试和错误码映射表。
3. 落地数据模型
   - 新增 P0 最小表集合和索引。
   - 定义状态枚举、状态事件、审计日志、部署任务状态。
   - 为名称唯一性先按部门内唯一实现，后续可按确认结果调整。
4. 实现后端基础能力
   - 列表、详情、创建、编辑预留接口。
   - RBAC、数据范围、席位、模型、Skill、知识库前置校验。
   - 统一审计写入和状态事件写入。
5. 实现部署和生命周期状态机
   - 创建部署任务并置为 `deploying`。
   - Worker 调用 Claw Proxy 部署、启动、停止、重启。
   - 成功/失败均写任务结果、状态事件和审计。
   - 删除只允许 `stopped -> deleted` 软删除。
6. 实现 Skill 和知识库绑定
   - 支持查看、绑定、解绑。
   - 拒绝未审核、禁用、无权限或不可用资源。
   - 运行中绑定变更通过后端调用 Claw Proxy 安装或卸载。
7. 实现状态同步、日志和审计查询
   - 周期同步运行状态和监控指标，写入快照。
   - 列表和详情读取最近快照。
   - 日志查询对接真实日志系统，返回脱敏结果和数据来源。
   - 审计日志按实例分页查询。
8. 实现前端页面
   - `/agents` 列表筛选、表格字段、空状态、错误状态、快捷操作。
   - `/agents/:id` 详情分区和任务状态展示。
   - 创建表单或弹窗、绑定面板、日志/审计面板。
   - 所有高影响操作需要确认反馈、加载态和错误提示。
9. 联调和验收
   - 联调 Claw Proxy、监控系统、日志系统真实数据源。
   - 校验浏览器网络请求中不出现 Claw Proxy `/api/v1/bot`。
   - 覆盖 P0 验收标准、权限失败、部署失败、敏感字段脱敏和审计写入。
10. 收敛待确认项
   - 创建后初始状态。
   - 名称唯一性范围。
   - `running` 状态允许编辑的字段。
   - 敏感日志查看/导出是否需要审批。

## 测试策略

- 单元测试：
  - 状态机合法/非法流转。
  - 名称唯一性、必填字段、资源配置校验。
  - RBAC 和数据范围校验分支。
  - Claw Proxy 错误码转换。
  - 敏感字段脱敏。
  - 审计日志和状态事件写入参数。
- 集成测试：
  - 创建龙虾成功和失败。
  - 部署成功：任务创建、状态 `deploying -> running`、回写 `proxy_instance_id`。
  - 部署失败：记录失败阶段、外部错误码、业务错误码，状态进入 `abnormal` 或 `stopped`。
  - 启动、停止、重启成功和外部失败。
  - `running` 删除被拒绝，`stopped` 删除软删除成功。
  - Skill/知识库绑定权限失败和成功。
  - 状态同步写入快照，列表/详情读取最近快照。
  - 日志查询接真实日志系统，敏感内容脱敏。
- 前端测试：
  - `/agents` 筛选、分页、字段展示和权限范围内数据展示。
  - `/agents/:id` 各分区渲染、快照时间和数据来源展示。
  - 创建表单必填校验、权限错误、部署进度反馈。
  - 生命周期操作确认、加载态、错误提示。
  - Skill/知识库绑定和解绑交互。
- 人工检查：
  - 浏览器网络面板确认前端只访问 `/api/v1/astron-claw`。
  - 检查响应中没有完整密钥、完整令牌、沙箱凭据。
  - 检查 mock 响应明确标记 `dataSource=mock`。
  - 检查真实监控/日志数据源可用于 P0 验收。
- 回归检查：
  - `/org` 数据范围不被绕过。
  - `/models` 模型禁用或无权限时不可选择。
  - `/skills` 未审核、禁用、无权限 Skill 不可绑定。
  - `/knowledge` 无权限、停用、删除知识库不可绑定。
  - `/security` 审计可按龙虾实例追溯高影响操作。

## 验收方案

- 正向用例：
  - 管理员创建只填写必填字段的龙虾，系统返回平台内部 ID 和初始状态。
  - 可部署状态下触发部署，系统创建部署任务，状态进入 `deploying`，成功后回写 `proxy_instance_id` 并流转 `running`。
  - 列表按状态、名称、部门、负责人、模型筛选，只返回授权范围内结果，并展示 P0 字段。
  - 详情展示基础配置、运行状态、模型、Skill、知识库、部署历史、基础日志、告警摘要和审计记录。
  - `running` 状态执行停止或重启，完成后写状态事件和审计日志。
  - `stopped` 状态执行删除，完成软删除并保留历史记录。
  - 用户绑定有权限且状态可用的知识库，详情正确展示。
  - 状态同步任务执行后，列表和详情展示最近一次快照、同步时间和数据来源。
- 反向用例：
  - 无目标部门数据权限时创建或查看失败，不泄露敏感信息。
  - Claw Proxy 部署失败时记录失败阶段、外部错误码和业务错误。
  - `running` 状态删除被拒绝，并提示必须先手动停止。
  - 未审核、禁用或无权限 Skill 绑定被拒绝。
  - 无权限、停用或已删除知识库绑定被拒绝。
  - 前端尝试访问外部运行时能力时，浏览器网络请求中不得出现 `/api/v1/bot`。
  - 接口不得返回完整密钥、完整令牌或沙箱凭据。
- 日志检查：
  - 创建、部署、启动、停止、重启、删除、绑定/解绑 Skill、绑定/解绑知识库、修改模型配置均有审计记录。
  - 部署失败包含失败阶段、外部错误码、业务错误码和可读错误。
  - 查看或导出敏感日志写入审计。
  - 日志内容完成密钥、令牌、个人敏感信息、模型输入输出敏感片段脱敏。
- 指标检查：
  - 部署任务耗时和成功/失败结果可查询。
  - Claw Proxy 调用失败率可追踪。
  - 状态同步最近成功时间和延迟可追踪。
  - 日志查询失败率可追踪。

### P0 验收标准映射

| 验收标准 | 实现路径 | 验证路径 |
| --- | --- | --- |
| 创建必填字段龙虾并返回 ID 和初始状态 | `POST /agents`、`agents`、`agent_versions`、审计 | 创建接口集成测试、前端创建表单测试 |
| 无部门权限时拒绝创建或查看 | RBAC + 数据范围校验 | 权限失败集成测试 |
| 部署成功回写 `proxy_instance_id` 并流转 `running` | 部署任务 + Worker + Claw Proxy 适配 | 部署成功集成测试 |
| 部署失败记录阶段和错误码 | `agent_deploy_tasks` 错误字段 + 错误转换 | 部署失败集成测试 |
| 列表筛选和展示 P0 字段 | `GET /agents` + 快照聚合 | API 测试、前端列表测试 |
| 详情聚合完整信息 | `GET /agents/{id}` + 子资源分页 | API 测试、前端详情测试 |
| `running` 停止或重启 | 生命周期服务 + 状态事件 + 审计 | 生命周期集成测试 |
| `running` 删除被拒绝 | 状态机约束 | 反向用例测试 |
| `stopped` 软删除 | `DELETE /agents/{id}` + `deleted_at` | 删除集成测试 |
| Skill 绑定校验 | Skill 权限/状态校验 + 绑定表 | 绑定失败/成功测试 |
| 知识库绑定展示 | 知识库权限校验 + 绑定表 | 绑定成功和详情展示测试 |
| 快照驱动运行态 | 同步任务 + `agent_runtime_snapshots` | 同步任务测试 |
| 高影响操作审计 | `audit_logs` | 审计查询和落库测试 |
| 前端不直连 Claw Proxy | 后端适配层边界 | 浏览器网络人工检查 |
| 不返回敏感凭据 | 响应 DTO 脱敏 | API 响应断言 |

## 回滚方案

- 代码回滚：
  - 前后端和 worker 按发布版本回滚到上一稳定版本。
  - 若只影响前端，可先隐藏 `/agents` 新增入口或关闭新功能开关。
- 配置回滚：
  - 关闭 Claw Proxy 真实适配开关，切回开发或只读模式。
  - 恢复上一版 Claw Proxy 地址、超时、重试和鉴权配置。
  - 关闭状态同步和日志索引任务，避免持续写入异常数据。
- 数据回滚：
  - P0 表以新增表为主，回滚时优先保留数据和审计，不做物理删除。
  - 如迁移失败，执行数据库迁移工具的 down 脚本；涉及审计和状态事件的数据不应被清理。
  - 已创建的龙虾如外部实例已部署，需要通过运维脚本或 Claw Proxy 管理台人工确认是否停止，不自动删除外部实例。
- 任务回滚：
  - 暂停部署、生命周期、状态同步和日志索引 worker。
  - 对 `running` 或 `deploying` 中的任务做人工对账，避免本地状态和 Claw Proxy 状态不一致。
- 前端回滚：
  - 下线新建、部署、删除等高影响按钮，保留只读详情或回退到旧页面。
  - 清除可能缓存的 mock 数据或错误数据源标识。
- 外部适配回滚：
  - 停止向 Claw Proxy 发起新部署或生命周期操作。
  - 对已经发起的外部请求按幂等键查询最终结果，再决定本地任务状态。

## 确认记录

- 确认人：用户人工输入
- 确认时间：2026-07-06
- 确认链接：Multica Issue AST-1（777c09bf-50e6-4add-978c-2be8f1533652）
- 需求文档：`.agent/memory/active/LOBSTER-0001/requirements.md`
- 计划生成时间：2026-07-07
- 已确认内容：
  - 本次按“现有 ops 平台 + 智能体龙虾模块”推进。
  - P0 严格以“龙虾实例管理最小闭环”为准，批量、成本、渠道、诊断等能力仅预留。
  - 本次功能建设落在当前仓库。
  - 创建龙虾最小必填字段为名称、部门、负责人、主模型、资源配置；Skill 和知识库为可选。
  - Claw Proxy `/api/v1/bot` 的部署、启停、重启、Skill 安装、状态查询接口契约和错误码已有可联调版本。
  - P0 要求真实接入监控/日志系统；开发环境 mock 仅作为联调兜底，必须标记数据来源。
  - 删除必须先由用户手动停止，`running` 状态不允许直接触发“停止后软删除”。

## 待确认问题

- 创建龙虾成功后的初始状态最终使用 `draft`，还是提交创建后立即创建部署任务并进入 `deploying`？
- 名称唯一性范围是全租户唯一、部门内唯一，还是允许重名但用 ID 区分？
- P0 是否要求支持编辑基础配置；若支持，哪些字段在 `running` 状态下允许修改？
- 是否需要在 P0 对“查看敏感日志/导出日志”启用审批，还是仅做权限校验、脱敏和审计？
