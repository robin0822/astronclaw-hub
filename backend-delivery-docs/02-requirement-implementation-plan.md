# AstronClaw 需求实现技术方案

## 1. 实施原则

1. 业务后端统一提供 `/api/v1/astron-claw` API，前端不直接访问 Claw Proxy。
2. 所有外部沙箱能力通过适配层调用 `/api/v1/bot`，并把外部错误码转换成前端可理解的业务错误。
3. P0 优先覆盖智能体、权限、监控告警、模型网关、安全审计、运维自动化、核心验收指标。
4. P1/P2 能力以可扩展的数据模型和任务框架预留，不阻塞 P0 验收。
5. 需求文档中 FR-10 虽被注释，但其内容属于金融保险场景的安全合规底线，应落入身份、权限、数据安全、审计、模型行为安全的后端设计。

## 1.1 需求追踪矩阵

| 编号 | 需求点 | 后端模块 | 关键落库 | 对外接口 | 验收重点 |
| --- | --- | --- | --- | --- | --- |
| FR-01.2 | 智能体列表、筛选、详情 | `agent` | `agents`、`agent_runtime_snapshots`、`agent_bind_skills`、`agent_bind_knowledge` | `/agents`、`/agents/{id}` | 字段覆盖列表要求，详情含配置、日志、历史、统计、告警、审计 |
| FR-01.3 | 创建与部署 | `deployment` | `agent_deploy_tasks`、`agent_versions` | `/agents`、`/agent-tasks/{id}` | 前置校验、任务队列、成功回写 `instanceId`、失败告警 |
| FR-01.4 | 批量部署/管理 | `batch` | `batch_tasks`、`batch_task_items` | `/batch-tasks` | 支持筛选结果、部门、标签、导入清单，结果可导出 |
| FR-01.5 | 生命周期 | `agent_lifecycle` | `agent_state_events`、`agent_versions`、`approval_requests` | `/agents/{id}/start|stop|restart|upgrade|archive|violation-offline` | 状态机、违规下线证据链、闲置归档、灰度升级、回滚 |
| FR-01.7 | 状态自动同步 | `runtime_sync` | `sync_jobs`、`sync_failures`、`agent_runtime_snapshots` | `/agents/{id}/sync`、`/sync-jobs` | 在线/离线、容器、负载、QPS、服务人数、失败原因 |
| FR-01.8 | 远程一体化运维 | `ops` | `agent_logs_index`、`agent_runtime_configs`、`ops_tasks` | `/agents/{id}/logs`、`/agents/{id}/runtime-config`、`/ops-tasks` | 运行/部署/升级/容器/模型日志，参数调整，异常清理 |
| FR-02.2 | 组织架构 | `identity` | `departments`、`positions`、`org_sync_jobs` | `/org/departments/*`、`/org/sync-jobs` | OA/HR 同步、手工维护、批量导入、账号状态 |
| FR-02.3 | 角色权限 | `rbac` | `roles`、`permissions`、`role_permissions`、`user_roles` | `/roles`、`/permissions`、`/permission-matrix` | 模块/页面/按钮/数据范围/高危权限 |
| FR-02.4 | 登录与 SSO | `auth`、`sso` | `users`、`sessions`、`login_logs`、`sso_providers` | `/auth/*`、`/sso/*` | 一期账号密码登录、登录锁定、Token 续期、OIDC/SAML/CAS/LDAP 预留 |
| FR-02.5 | 席位 | `seat` | `seat_packages`、`seat_assignments`、`seat_events` | `/seat-packages`、`/seat-assignments` | 分配、回收、到期提醒、使用率预警、调拨审计 |
| FR-03 | 监控告警 | `monitor`、`alert` | `metric_samples`、`alert_rules`、`alerts`、`alert_events` | `/monitor/*`、`/alerts/*` | 真实监控/日志数据、5 秒刷新、告警闭环、通知中心 |
| FR-04 | 模型网关 | `model_gateway` | `llm_models`、`model_quota_policies`、`model_route_policies`、`model_call_logs` | `/models`、`/model-quotas`、`/model-route-policies` | 密钥掩码、探针、限流、智能路由、调用审计 |
| FR-05 | 成本核算 | `cost` | `cost_rules`、`resource_packages`、`cost_daily_stats`、`budgets` | `/cost/*`、`/cost-rules`、`/budgets` | 部门/项目/模型/智能体/资源包，多周期归档，预算告警 |
| FR-06 | 运维自动化 | `ops` | `inspection_tasks`、`inspection_runs`、`self_heal_tasks`、`backup_tasks` | `/inspection-*`、`/diagnostics/{id}/fix`、`/agents/{id}/backups` | 巡检报告、自愈联动、高风险审批、备份恢复 |
| FR-07 | Skill 管理 | `skill` | `skills`、`skill_versions`、`skill_reviews`、`agent_bind_skills`、`skill_env_vars` | `/skills`、`/agents/{id}/skills/*`、`/agents/{id}/skill-env-vars` | 审核、版本、权限、离线包、安全扫描 |
| FR-08 | 知识和记忆 | `knowledge`、`memory` | `knowledge_bases`、`knowledge_files`、`knowledge_parse_tasks`、`memories`、`memory_share_requests` | `/knowledge-*`、`/memories`、`/agents/{id}/memory-preview` | 文件校验、解析切片、权限隔离、共享审批、AstronMem |
| FR-09 | 消息渠道与嵌入 | `channel` | `message_channels`、`channel_bind_agents`、`business_systems`、`channel_audit_logs` | `/channels`、`/business-systems` | 本期可预留；告警推送和业务嵌入需留接口 |
| 实例共享 | 个人/部门/项目共享 | `share` | `share_grants`、`share_approval_requests` | `/agents/{id}/share-grants` | 授权、审批、回收、普通用户可用资源 |
| FR-10 | 安全合规基线 | `security`、`audit` | `audit_logs`、`security_policies`、`export_tasks`、`sensitive_events` | `/audit/*`、`/security-policies`、`/exports` | 脱敏、加密、防篡改、导出审计、模型内容审核 |
| FR-11 | 问题诊断 | `diagnosis` | `diagnosis_tickets`、`diagnosis_kb`、`diagnosis_decision_trees`、`fix_tasks` | `/diagnostics`、`/diagnosis-kb`、`/diagnostics/{id}/fix` | 异常聚合、根因、建议、一键修复、知识沉淀 |

## 2. FR-01 智能体集群统一管理

### 2.1 列表与详情

后端从 `agents`、`agent_runtime_snapshots`、`agent_bind_skills`、`agent_bind_knowledge` 聚合返回列表。支持状态、名称、部门、负责人、模型筛选。运行态字段由状态同步任务周期性从 Claw Proxy、监控系统和容器平台采集。

列表字段必须完整覆盖需求文档：实例名称、运行 `instanceId`、状态、版本、部门、负责人、容器数、Skill 数、绑定知识库、主模型、备用模型、CPU、内存、存储、GPU、并发阈值、单日调用上限、超时阈值、当前服务人数、最大服务人数、QPS、创建时间、最近更新时间。

详情页后端聚合：

| 区块 | 数据来源 |
| --- | --- |
| 配置 | `agents`、`agent_runtime_configs`、`agent_versions.config_snapshot` |
| 运行日志 | `agent_logs_index` 或日志系统查询 |
| 部署历史 | `agent_deploy_tasks` |
| 版本历史 | `agent_versions` |
| 绑定 Skill | `agent_bind_skills`、`skills` |
| 绑定知识库 | `agent_bind_knowledge`、`knowledge_bases` |
| 调用统计 | `model_call_logs`、`cost_daily_stats` |
| 告警记录 | `alerts` |
| 审计记录 | `audit_logs` |

### 2.2 创建与部署

技术流程：

1. 校验用户权限、部门权限、席位、模型状态、资源配额、Skill 权限、知识库权限。
2. 生成 `botId`，建议规则为 `agt_` + 12 位随机十六进制。
3. 调用 Bridge Server 申请 `bridgeToken`。
4. 组装 `modelsConfig`，密钥从后端密钥系统读取，不能由前端传完整密钥。
5. 创建 `agents` 记录，状态为 `deploying`。
6. 创建 `agent_deploy_tasks`，由异步 worker 调用 `POST /api/v1/bot/deploy`。
7. 保存返回的 `instanceId` 到 `proxy_instance_id`。
8. 逐个调用 `/skill/install`，按需调用 `/skill/add_env`。
9. 成功后状态改为 `running`，失败则改为 `abnormal` 或 `stopped`，写告警和审计。

### 2.3 生命周期操作

| 业务操作 | 后端处理 | Claw Proxy |
| --- | --- | --- |
| 启用/部署 | 创建部署任务，异步执行 | `POST /deploy` |
| 停用 | 校验状态，异步停止，释放资源标记 | `POST /{instanceId}/stop` |
| 重启 | 创建重启任务，完成后健康检查 | `POST /{instanceId}/restart` |
| 升级 | 记录版本快照，调用升级，更新 `instanceId` | `POST /{instanceId}/upgrade` |
| 模型切换 | 校验模型和密钥，保存配置快照 | `PUT /{instanceId}/model` |
| 自动修复 | 创建修复任务并轮询状态 | `POST /{instanceId}/doctor/fix` |
| 删除 | 先 stop，再软删业务记录 | `POST /stop` |

### 2.4 批量操作

批量任务必须异步执行。后端先冻结目标清单，写入 `batch_tasks.scope_snapshot` 和 `batch_task_items`，worker 按批次执行。

支持能力：

| 能力 | 技术方案 |
| --- | --- |
| 批量部署/启用 | 对待部署或已停止实例逐个创建部署 item |
| 批量停用/下线 | 逐个调用 stop，失败 item 单独记录 |
| 批量重启 | 逐个调用 restart，完成后触发健康检查 |
| 批量升级 | 支持灰度批次、失败暂停、可回滚版本快照 |
| 批量删除/归档 | 执行依赖检查和高危审批 |
| 批量模型切换 | 校验模型可用性后逐个调用 `/model` |
| 批量 Skill 同步 | 调用 install/uninstall 并保存每个实例结果 |

批量范围解析：

| 范围 | 后端处理 |
| --- | --- |
| 当前页 | 前端传当前页 ID，后端二次校验权限 |
| 筛选结果 | 前端传筛选条件，后端在服务端重新查询并冻结目标快照 |
| 指定部门 | 展开部门和子部门实例，按数据权限裁剪 |
| 指定标签 | 按标签关系表查询实例 |
| 导入清单 | 上传 CSV/Excel，解析后生成预检结果 |

批量预检必须覆盖资源配额、席位、权限、模型可用性、渠道绑定、Skill/知识库权限、影响范围。高危批量任务进入审批流。

### 2.5 状态同步、远程运维与日志

状态同步 job 定时采集：

1. Claw Proxy 会话是否有效、实例是否可调用。
2. 容器平台的 pod/container 状态、CPU、内存、GPU、存储、网络。
3. 模型网关的错误率、时延、QPS、Token、调用成功率。
4. 会话层服务人数、排队量、响应延迟。

远程运维接口需要支持：

| 能力 | 技术实现 |
| --- | --- |
| 运行/部署/升级/容器/模型调用日志 | 接入日志平台，按 `agentId`、`instanceId`、`logType`、时间范围查询 |
| 远程参数调整 | 更新 `agent_runtime_configs`，必要时调用 Claw Proxy 模型切换或重启 |
| 节点重启/容器重建/异常清理 | 创建 `ops_tasks`，按任务执行并写审计 |
| 批量漏洞修复/安全补丁 | 高风险任务，进入审批后由 worker 执行 |
| 问题诊断跳转 | 告警或实例详情中返回 `diagnosisId` |

## 3. FR-02 统一身份权限

### 3.1 RBAC 与数据权限

权限采用 `角色 -> 权限项 -> 数据范围` 模型。权限项编码建议：

```text
agent:view
agent:create
agent:update
agent:delete
agent:deploy
agent:batch
agent:audit_view
model:secret_view
audit:export
```

数据范围支持：全部、本部门、本部门及下级、本人、指定部门、指定项目、指定智能体。

### 3.2 一期账号密码登录

一期先实现账号密码登录，满足管理后台独立运行和前后端联调。后续私有化项目接入客户登录系统时，不改变前端业务接口和后端权限模型，只替换认证入口。

登录流程：

```text
POST /auth/login
  -> 按 username 查询本地用户
  -> 校验账号状态、失败锁定状态
  -> 校验 password_hash
  -> 创建 session 或签发 JWT
  -> 返回 accessToken、expiresIn、user、permissions、dataScope
  -> 写 login_logs
```

退出流程：

```text
POST /auth/logout
  -> 撤销当前 session 或 token
  -> 写 login_logs / audit_logs
```

本地账号能力：

| 能力 | 技术要求 |
| --- | --- |
| 初始管理员 | 部署脚本或初始化接口创建首个超级管理员，首次登录后强制改密可选 |
| 密码存储 | 只保存 bcrypt/argon2 hash，不保存明文或可逆密文 |
| 密码策略 | 最小长度、复杂度、历史密码复用限制可配置 |
| 登录失败锁定 | 连续失败 N 次锁定 M 分钟，防止暴力破解 |
| 会话过期 | access token 短有效期，refresh token 可选；退出后 token 失效 |
| 用户状态 | `active`、`locked`、`disabled`、`departed` 等状态影响登录 |
| 权限返回 | 登录后返回当前用户基础信息、角色、权限码和数据范围 |
| 审计 | 登录成功、失败、退出、密码重置、账号冻结均留痕 |

### 3.3 私有化登录系统接入预留

本期保留 OIDC/SAML/CAS/LDAP 适配接口。用户通过外部身份源认证后，业务后端仍统一颁发自己的会话或 JWT，前端只使用业务后端 token。

适配原则：

1. 外部登录系统只负责身份认证，不直接替代业务后端 RBAC。
2. 外部用户标识通过 `sso_subject`、手机号、工号或客户确认字段映射到本地 `users`。
3. 组织、人员、岗位可由 OA/HR/LDAP/AD 定时同步，也可首次登录时 JIT 创建。
4. 若客户采用统一网关免登录，后端只信任内网可信网关注入的签名用户头。
5. 登录方式切换不影响 `/api/v1/astron-claw` 业务接口和前端权限判断。

### 3.4 席位管理

创建智能体、授权用户、共享实例时校验席位。席位不足返回明确错误码，并写操作审计。

席位管理需细化为：

1. 席位包：总量、已用量、剩余量、有效期、所属部门/项目。
2. 席位分配：按用户、部门、项目、智能体授权。
3. 席位回收：离职、转岗、共享到期、实例归档时自动触发。
4. 到期提醒：到期前 30/15/7/1 天产生通知或告警。
5. 使用率预警：剩余席位低于阈值触发 P2/P1 告警。
6. 调拨审计：跨部门调拨记录前后部门、数量、操作人、审批单。

## 4. FR-03 运行监控告警

### 4.1 指标采集

采集来源包括 Claw Proxy、容器平台、模型网关、数据库、队列、日志系统。`collect_metrics` job 按周期写入短期指标库和 `agent_runtime_snapshots`。

监控看板默认 5 秒刷新，后端返回 `refreshIntervalSeconds` 便于前端按配置刷新。生产环境告警必须来自真实监控/日志系统，开发环境可使用 mock 数据，但响应中需要标记 `dataSource=mock|prometheus|loki|claw_proxy|model_gateway`。

### 4.2 告警闭环

告警状态：

```text
pending -> claimed -> processing -> closed
pending -> suspended -> processing
```

严重/一般告警自动生成问题诊断待办。闭环时必须记录处置人、处置时间、处置说明和关联操作。

告警识别规则至少覆盖：链路中断、节点离线、模型调用失败、算力卡顿、存储不足、渠道断连、任务失败、权限异常。告警字段包括告警编号、级别、来源对象、错误码、分类、触发时间、责任人、影响范围、详情、根因、建议措施。

## 5. FR-04 大模型统一接入管理

模型密钥使用 `secret_ref` 保存引用。新增或编辑模型时，后端写密钥系统并保存引用 ID。前端只看到掩码。

调用审计字段包括调用人、部门、项目、智能体、模型、时间、输入摘要、输出摘要、耗时、token、费用、状态、错误码。审计保留不少于 180 天，具体以客户合规要求为准。

模型台账字段必须覆盖：模型名称、供应商、模型标识、模型类型、接口地址、认证方式、密钥引用、状态、单价、上下文长度、适用场景、默认超时、错误率、平均时延、今日调用量、今日 token、容器成本。

模型类型枚举建议：`chat`、`office`、`industry_compute`、`financial_doc_understanding`、`policy_extract`、`risk_assessment`、`light_reasoning`、`embedding`、`rerank`、`multimodal`。

流量控制：

1. 支持按部门、项目、个人、模型、智能体配置 QPS、并发、日调用量、日 Token。
2. 支持过载策略：排队、拒绝、降级响应、切换备用模型。
3. 智能路由按成本、时延、可用性、模型能力选择模型。
4. 高峰期削峰错峰通过队列调度实现。
5. 限流命中和路由命中写入 `model_policy_hits`。

## 6. FR-05 成本分析核算

成本归档 job 每日执行：

1. 汇总模型调用日志，计算 token 成本。
2. 汇总实例在线时长和资源规格，计算容器成本。
3. 汇总席位包和存储资源，计算基础成本。
4. 按部门、项目、模型、智能体、资源包生成 `cost_daily_stats`。
5. 对高耗模型、高耗部门、闲置智能体触发提示告警。

成本规则补充：

| 成本类型 | 计算方式 |
| --- | --- |
| Token 成本 | `input_tokens/output_tokens * model_unit_price` |
| 容器成本 | CPU、内存、GPU、存储、在线时长或资源规格单价 |
| 席位成本 | 席位包金额按用户、部门、项目或使用时长分摊 |
| 公共成本 | 平台底座、公共模型、公共知识库按部门或使用量分摊 |
| 项目独享成本 | 专属智能体、专属模型、专属资源独立核算 |

成本异常识别包括高耗模型、高耗部门、闲置智能体、低效资源包、预算超额。成本报表需支持日、周、月、季度归档和导出。

## 7. FR-06 运维自动化

巡检任务覆盖服务器、网络、容器、智能体、模型、存储、数据库、消息渠道、证书、备份任务。巡检结果写入 `inspection_runs` 和 `inspection_items`，支持导出 HTML/PDF/Excel。

自愈任务通过 `ops_service` 封装，支持实例重启、渠道重连、模型探针恢复、日志清理、缓存刷新。高风险任务进入审批。

自动巡检项需覆盖服务器、网络、容器、智能体、模型、存储、数据库、消息渠道、证书、备份任务。巡检结果字段包含巡检范围、巡检时间、巡检模式、整体通过率、巡检项统计、明细、建议措施。报告导出支持 HTML、PDF、Excel。

自动化任务包括全域健康巡检、日志清理、备份校验、模型探针、漏洞扫描、依赖检查、安全基线检查。任务失败自动触发告警。

## 8. FR-07 Skill 管理

Skill 导入后进入 `pending_review` 或 `disabled`，审核通过后才能被智能体选择。安装时调用：

```http
POST /api/v1/bot/{instanceId}/skill/install
```

卸载时调用：

```http
POST /api/v1/bot/{instanceId}/skill/uninstall
```

Skill 绑定、解绑、版本更新必须写操作日志。

Skill 导入来源包括官方预置、自定义、第三方、离线导入、URL 导入、Skill 广场导入。导入时执行格式校验、依赖校验、安全扫描；未审核 Skill 不允许被智能体创建和编辑流程选择。Skill 权限支持角色、部门、项目、智能体四类授权。

## 9. FR-08 知识与记忆管理

上传文件后创建解析任务，状态为 `parsing`。解析流程包括格式校验、大小校验、病毒扫描、敏感信息检测、切片、向量化、索引。智能体只能绑定权限范围内的知识库。

记忆管理支持会话、个人、组织、企业四级。AstronMem 插件状态通过 Claw Proxy 插件接口查询和切换。

知识库文件支持 PDF、DOCX、TXT、XLSX、PPTX、MD。上传后状态流转：

```text
uploaded -> validating -> parsing -> chunking -> embedding -> indexed
uploaded/validating/parsing/chunking/embedding -> failed
```

删除知识文件前必须检查是否被智能体引用。知识库权限范围支持个人、部门、项目、企业；知识库共享需审批。记忆共享规则：组织记忆需部门负责人审批，企业记忆需平台管理员审批。

## 10. FR-09 消息渠道与多端接入

需求文档标注消息渠道“暂时不做”，本期建议仅保留数据模型和接口占位，不做完整渠道管理。若需要企业微信告警推送，可作为通知模块最小集成。

即使完整渠道管理延期，后端仍需预留：

| 能力 | 预留设计 |
| --- | --- |
| 渠道台账 | `message_channels` 保存名称、类型、状态、绑定智能体、回调地址、认证方式、责任人 |
| 连接测试 | `/channels/{id}/test` 触发连接探针 |
| 异常重连 | `/channels/{id}/reconnect` 创建重连任务 |
| 渠道限流 | 单用户频率、渠道 QPS、每日消息上限 |
| 消息留痕 | `channel_message_logs` 记录来源、用户、智能体、结果 |
| 企业微信 | 扫码登录、通讯录同步、告警/任务/审批推送预留 |
| 业务系统嵌入 | 支持 iframe、SDK、链接、门户卡片，记录调用来源审计 |

需求提到至少对接合同管理系统、养老金融系统 2 个业务系统。后端应预留 `business_systems`、`business_system_agent_grants`、`business_system_audit_logs`。

## 11. FR-11 问题诊断

诊断对象来自异常智能体、未闭环 P0/P1 告警、模型高错误率、渠道断连、巡检失败。诊断详情聚合告警、指标、日志、最近操作和建议动作。

一键修复调用 Claw Proxy `/doctor/fix` 或本地 ops 任务，完成后反向更新实例状态、告警状态和巡检状态。

诊断知识库需要支持错误码、模块、关键词检索，并维护诊断决策树。历史故障闭环后可一键沉淀为知识库条目，字段包括错误码、现象、原因、解决方案、适用模块、关联告警、验证方式。

## 11.1 FR-10 安全合规基线

需求文档中 FR-10 位于注释块，但其内容对金融保险行业是必要约束。后端设计至少落实：

1. 身份鉴别：用户身份唯一，不允许共享账号；一期支持账号密码登录，后续支持 SSO、MFA 扩展点、密码复杂度、登录失败锁定、会话超时。
2. 访问控制：最小授权原则；高危操作二次确认、审批或双人复核。
3. 数据安全：敏感信息存储加密；通信链路 TLS 或内网安全通道；日志和审计脱敏；文件上传类型、大小、病毒、内容安全检测。
4. 数据导出：统一导出任务，权限控制、审批、水印和审计。
5. 外部模型调用：调用前进行客户隐私和敏感字段脱敏。
6. 审计追溯：登录/登出、权限变更、配置修改、数据导出、模型调用、智能体启停、敏感操作均审计。
7. 防篡改：审计日志支持哈希链、WORM 存储或客户认可的等价机制，保留不少于 180 天。
8. 模型行为安全：输入输出内容审核、违规提示词告警、金融建议合规检测、人工复核扩展点。

## 12. 错误处理

| 来源 | 处理 |
| --- | --- |
| HTTP 400/404 | 视为沙箱实例不可用或会话失效 |
| Claw Proxy `400003` | 会话失效，提示重新部署 |
| Claw Proxy `300003` | Bot 部署失败，记录失败阶段 |
| 网络超时 | 标记外部服务不可用，进入重试或人工处理 |
| 权限失败 | 返回 403，写安全审计 |
| 高危操作未审批 | 返回 409 或业务码 `APPROVAL_REQUIRED` |

## 13. 对比源文档后的补充实现方案

### 13.1 Claw Proxy 完整能力代理

业务后端除生命周期、Skill、模型切换外，还必须代理以下沙箱能力：

| 能力 | 业务后端接口 | 关键处理 |
| --- | --- | --- |
| 已安装 Skill 查询 | `GET /agents/{agentId}/runtime-skills` | 调 `/skill/list`，与本地绑定表比对，展示漂移 |
| Skill 环境变量 | `GET/PUT/DELETE /agents/{agentId}/skill-env-vars` | 值写密钥系统，调用 `/skill/add_env` 或 `/skill/remove_env`，必要时重启 |
| 沙箱文件 | `/agents/{agentId}/dev-files*` | 路径白名单限制在 `/root/.openclaw`，写操作必须审计，保存用 etag |
| 记忆预览 | `GET /agents/{agentId}/memory-preview` | 后端取 `astronmenApiKey`，调用 `/memory/preview` |
| 插件状态 | `GET/POST /agents/{agentId}/plugins/{pluginName}` | 支持 `astronmem-cloud-openclaw-plugin` 查询和开关 |
| 定时任务 | `/agents/{agentId}/crons*` | 后端生成 cron `id`，持久化表达式，调用 Claw Proxy |
| Agent Team | `/agents/{agentId}/teams*` | 生成 `session_key=agent:main:main:{sessionId}`，查询进度、产物、结果 |
| 备份恢复 | `/agents/{agentId}/backups*` | 保存 Claw Proxy 返回的 `taskId`，轮询状态 |

### 13.2 审批流与高危操作

以下操作必须支持审批或二次确认：

| 操作 | 风险等级 | 策略 |
| --- | --- | --- |
| 批量删除、批量下线 | high | 创建审批单，审批通过后 worker 执行 |
| 违规下线 | critical | 可先执行紧急下线，事后补审批和证据链 |
| 导出审计/模型调用日志 | high | 审批 + 导出水印 + 导出审计 |
| 查看密钥掩码之外的敏感信息 | critical | 默认禁止；如客户要求，双人复核并短时展示 |
| 停用安全策略、变更模型密钥 | high | 审批 + 操作前后值审计 |

审批单保存 `payload_snapshot`，执行时按快照执行，避免审批后请求被篡改。

### 13.3 实例共享

实例共享作为独立模块实现：

1. 支持个人、部门、项目三级共享范围。
2. 共享权限至少包括 `use`、`view_config`、`manage`。
3. 部门/项目级共享默认需要审批。
4. 共享到期自动回收，回收写审计。
5. 普通用户不能进入管理后台，但可在聊天项目中使用被授权资源。

### 13.4 席位管理

席位校验前置到以下流程：

1. 创建智能体。
2. 授权用户使用智能体。
3. 实例共享。
4. 批量授权。
5. 跨部门调拨。

席位不足时返回 `422001 quota exceeded`，并在响应中返回 `required`、`available`、`seatPackageId` 便于前端提示。

### 13.5 模型流控与智能路由

模型调用前执行：

```text
resolve caller scope
  -> check model_quota_policies
  -> check qps/concurrency/token/day limit
  -> choose route by latency/cost/availability/capability
  -> call model
  -> write model_call_logs
  -> emit cost event
```

过载策略包括排队、拒绝、降级响应、切换备用模型。策略命中需要写入 `model_policy_hits`。

### 13.6 监控真实数据源

生产环境不得由前端模拟告警。后端需要支持以下数据源适配：

| 数据源 | 采集内容 |
| --- | --- |
| Claw Proxy | 实例会话有效性、Skill、文件、备份、Cron 状态 |
| K8s/容器平台 | 容器状态、CPU、内存、GPU、存储、节点 |
| 模型网关 | 调用量、错误率、时延、token、费用 |
| 日志系统 | 运行日志、部署日志、容器日志、异常栈 |
| 数据库/队列 | 连接数、慢查询、队列积压、任务失败 |

### 13.7 诊断知识库

诊断知识库需要支持：

1. 错误码、模块、现象、原因、解决方案维护。
2. 决策树维护。
3. 历史故障一键沉淀为知识。
4. 与告警、巡检失败、Claw Proxy 错误码自动匹配。

### 13.8 FR-10 安全合规基线

虽然需求文档中 FR-10 处于注释块，后端仍应把它作为金融保险场景的底线约束：

1. 所有敏感字段入库加密或保存密钥引用。
2. 所有导出走统一导出任务，权限校验并写审计。
3. 操作日志和模型调用日志敏感字段脱敏。
4. 审计日志默认保留不少于 180 天。
5. 高危操作支持二次确认、审批或双人复核。
6. 模型输入输出支持内容审核和合规检测扩展点。
