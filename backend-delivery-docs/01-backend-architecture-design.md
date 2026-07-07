# AstronClaw 后端架构设计

## 1. 设计依据与边界

本文依据根目录需求文档 `astronclaw-chinalife-requirements.md`、Claw Proxy HTTP 对接文档 `claw_proxy_bot_http_api(1).md`、字段与密钥交付说明 `沙箱机器人对接字段与密钥交付说明.md` 编写。

当前仓库 `backend/README.md` 为空，未提供可分析的后端源代码。因此本文给出的是建议后端代码架构、模块边界、核心表结构、流程和接口设计，供后续开发落地。

系统边界：

| 层级 | 职责 |
| --- | --- |
| 前端管理台 | 调用本业务后端 `/api/v1/astron-claw`，不直接持有 Claw Proxy token |
| AstronClaw 业务后端 | 负责用户权限、业务台账、审批、任务、审计、成本、监控聚合，并代理调用 Claw Proxy |
| Claw Proxy 沙箱层 | 提供 `/api/v1/bot` 实例生命周期、Skill、文件、记忆、定时任务、Team、备份恢复能力 |
| Bridge Server | 生成 `bridgeToken`，支撑对话通道，不属于 Claw Proxy HTTP 层 |
| 外部企业系统 | OA/HR/SSO、企业微信、监控、日志、密钥系统、对象存储等 |

## 2. 总体架构

建议采用分层单体优先、可演进微服务的后端架构。第一期以一个业务后端服务承载核心模块，内部按领域分包，避免过早拆服务导致联调成本升高。批量任务、监控采集、成本归档等异步能力通过队列和调度器解耦。

```text
Frontend
  |
  | HTTPS + user JWT/session
  v
API Gateway / AstronClaw Backend
  |
  |-- auth         统一登录、SSO、RBAC、数据权限
  |-- agent        智能体台账、创建、部署、生命周期、批量任务
  |-- skill        Skill 仓库、审核、安装、卸载、授权
  |-- knowledge    知识库、文件、解析、索引、绑定
  |-- model        模型台账、限流、路由、模型审计
  |-- monitor      指标聚合、告警、诊断、巡检
  |-- cost         用量采集、成本规则、归档报表
  |-- ops          自动化任务、备份恢复、自愈
  |-- audit        操作日志、登录日志、导出日志、敏感操作追溯
  |-- integration  Claw Proxy、Bridge、SSO、OA/HR、企业微信客户端
  |
  | async jobs / scheduler / event bus
  v
Database + Redis + Object Storage + Metrics/Logs + Secret Manager
  |
  v
Claw Proxy / Bridge Server / Enterprise Systems
```

## 3. 推荐技术栈

| 类型 | 建议 |
| --- | --- |
| Web 框架 | FastAPI 或 Spring Boot。若后续 Python 生态对接 OpenClaw 更密集，优先 FastAPI |
| ORM | SQLAlchemy 2.x / Alembic 或 MyBatis/JPA |
| 数据库 | PostgreSQL 或 MySQL 8，要求支持事务、索引、JSON 字段 |
| 缓存 | Redis，用于会话、权限缓存、限流、任务锁、短期指标 |
| 异步任务 | Celery/RQ/Arq 或 Spring Scheduler + MQ |
| 消息队列 | RabbitMQ、Kafka 或 Redis Stream，用于批量部署、状态同步、告警事件 |
| 文件存储 | S3/OSS/MinIO，保存上传文件、报告、离线包 |
| 可观测性 | Prometheus、Grafana、Loki/ELK、OpenTelemetry |
| 密钥 | Vault、KMS、K8s Secret 或客户指定密钥系统 |

## 4. 后端代码目录建议

```text
backend/
  app/
    main.py
    api/
      deps.py
      v1/
        auth_routes.py
        agent_routes.py
        batch_routes.py
        skill_routes.py
        knowledge_routes.py
        model_routes.py
        monitor_routes.py
        alert_routes.py
        cost_routes.py
        ops_routes.py
        audit_routes.py
    core/
      config.py
      security.py
      permissions.py
      id_gen.py
      errors.py
      pagination.py
      logging.py
    models/
      agent.py
      skill.py
      knowledge.py
      identity.py
      model_gateway.py
      monitor.py
      cost.py
      ops.py
      audit.py
    schemas/
      agent.py
      skill.py
      knowledge.py
      identity.py
      model_gateway.py
      monitor.py
      common.py
    services/
      agent_service.py
      deployment_service.py
      batch_service.py
      skill_service.py
      knowledge_service.py
      model_service.py
      monitor_service.py
      alert_service.py
      cost_service.py
      ops_service.py
      audit_service.py
      permission_service.py
    clients/
      claw_proxy_base.py
      bot_client.py
      skill_client.py
      dev_file_client.py
      memory_proxy_client.py
      cron_proxy.py
      team_api_client.py
      backup_client.py
      bridge_client.py
      sso_client.py
      org_client.py
      wecom_client.py
    jobs/
      scheduler.py
      sync_agent_status.py
      collect_metrics.py
      cost_archive.py
      inspection_jobs.py
      alert_jobs.py
      batch_worker.py
    repositories/
      agent_repo.py
      task_repo.py
      audit_repo.py
    middleware/
      request_id.py
      auth.py
      audit.py
      error_handler.py
    tests/
```

## 5. 核心模块职责

| 模块 | 职责 | P0 能力 |
| --- | --- | --- |
| auth | 登录、SSO 预留、RBAC、数据权限、席位校验 | 管理员登录、角色权限、按钮权限、用户组织 |
| agent | 智能体台账、创建、部署、重启、停止、升级、删除、详情 | 状态流转、Claw Proxy 映射、批量操作 |
| skill | Skill 台账、上传、导入、审核、授权、安装卸载 | Skill 权限、绑定智能体、离线包分发 |
| knowledge | 知识库、文档上传、解析任务、绑定智能体 | 文件校验、解析状态、权限范围 |
| model | 模型台账、密钥引用、健康探针、切换模型、调用审计 | 主备模型、限额、成本字段 |
| monitor | 指标聚合、状态看板、异常识别 | 核心 KPI、实例状态同步 |
| alert | 告警规则、告警认领、处理、闭环、通知 | P0/P1/P2 告警闭环 |
| cost | 按部门、项目、模型、智能体统计用量与成本 | 日/月归档、预算阈值 |
| ops | 巡检、自愈、备份恢复、定时任务 | 自动巡检、修复任务、备份状态 |
| audit | 登录、操作、模型调用、导出、敏感操作审计 | 180 天保留、防篡改预留 |
| integration | Claw Proxy、Bridge、SSO、OA/HR、企业微信适配 | 服务间密钥托管、错误码转换 |

## 6. 数据模型设计

### 6.1 智能体与实例

| 表 | 关键字段 |
| --- | --- |
| `agents` | `id`、`bot_id`、`proxy_instance_id`、`bridge_token_ref`、`name`、`type`、`status`、`version`、`department_id`、`owner_id`、`primary_model_id`、`backup_model_id`、`resource_spec`、`concurrency_limit`、`daily_call_limit`、`timeout_ms`、`created_at`、`updated_at` |
| `agent_runtime_snapshots` | `agent_id`、`container_count`、`cpu`、`memory`、`gpu`、`storage`、`qps`、`latency_ms`、`current_users`、`max_users`、`last_sync_at`、`sync_error` |
| `agent_deploy_tasks` | `id`、`agent_id`、`action`、`status`、`phase`、`node`、`started_at`、`ended_at`、`error_code`、`error_message`、`retry_advice` |
| `agent_versions` | `agent_id`、`version`、`config_snapshot`、`deployed_at`、`rollback_from` |
| `agent_bind_skills` | `agent_id`、`skill_id`、`package_name`、`installed_version`、`status` |
| `agent_bind_knowledge` | `agent_id`、`knowledge_base_id`、`scope` |

### 6.2 批量任务

| 表 | 关键字段 |
| --- | --- |
| `batch_tasks` | `id`、`type`、`scope_type`、`scope_snapshot`、`total`、`success_count`、`failed_count`、`skipped_count`、`status`、`operator_id`、`approval_id`、`created_at` |
| `batch_task_items` | `batch_task_id`、`target_id`、`action`、`status`、`started_at`、`ended_at`、`error_code`、`error_message` |

### 6.3 权限与组织

| 表 | 关键字段 |
| --- | --- |
| `departments` | `id`、`parent_id`、`name`、`leader_id`、`status`、`source` |
| `users` | `id`、`employee_no`、`username`、`password_hash`、`password_updated_at`、`name`、`department_id`、`email`、`mobile`、`status`、`seat_status`、`identity_source`、`sso_subject`、`last_login_at` |
| `roles` | `id`、`name`、`description`、`data_scope`、`status` |
| `permissions` | `code`、`module`、`page`、`action`、`risk_level` |
| `role_permissions` | `role_id`、`permission_code` |
| `user_roles` | `user_id`、`role_id` |
| `seats` | `id`、`package_id`、`assignee_type`、`assignee_id`、`expires_at`、`status` |
| `sessions` | `id`、`user_id`、`access_token_hash`、`refresh_token_hash`、`expires_at`、`refresh_expires_at`、`ip`、`user_agent`、`revoked_at` |
| `login_logs` | `id`、`username`、`user_id`、`login_type`、`result`、`failure_reason`、`ip`、`user_agent`、`created_at` |

### 6.4 模型、成本、审计

| 表 | 关键字段 |
| --- | --- |
| `llm_models` | `id`、`name`、`provider`、`model_key`、`type`、`base_url`、`auth_type`、`secret_ref`、`status`、`unit_price`、`context_length`、`timeout_ms` |
| `model_call_logs` | `id`、`user_id`、`department_id`、`agent_id`、`model_id`、`input_summary`、`output_summary`、`latency_ms`、`tokens`、`cost`、`status`、`error_code` |
| `cost_daily_stats` | `date`、`dimension_type`、`dimension_id`、`call_count`、`tokens`、`model_cost`、`container_cost`、`seat_cost`、`total_cost` |
| `audit_logs` | `id`、`actor_id`、`module`、`action`、`object_type`、`object_id`、`before_value`、`after_value`、`ip`、`result`、`error_message`、`created_at`、`hash_prev`、`hash_current` |

## 7. 状态机设计

智能体状态建议：

```text
draft -> deploying -> running -> stopping -> stopped
running -> upgrading -> running
running -> abnormal -> running/stopped
running/stopped -> archived
running/abnormal -> violation_offline
```

关键约束：

| 操作 | 允许源状态 | 成功目标状态 |
| --- | --- | --- |
| 部署 | `draft`、`stopped`、`abnormal` | `running` |
| 停用 | `running`、`abnormal` | `stopped` |
| 重启 | `running`、`abnormal` | `running` |
| 升级 | `running`、`stopped` | `running` 或 `stopped` |
| 删除 | `draft`、`stopped`、`archived` | 软删除 |
| 违规下线 | `running`、`abnormal` | `violation_offline` |

## 8. 外部对接设计

### 8.1 Claw Proxy

业务后端持有 `CLAW_PROXY_BASE_URL` 与 `CLAW_PROXY_AUTH_TOKEN`，统一通过 `clients/claw_proxy_base.py` 注入请求头：

```http
Authorization: Bearer <CLAW_PROXY_AUTH_TOKEN>
Content-Type: application/json
```

前端不得直接调用 Claw Proxy，也不得接触完整服务间密钥、模型 `apiKey`、租户 `api_secret`。

### 8.2 Bridge Server

创建智能体时先向 Bridge Server 申请 `bridgeToken`，再把 `bridgeToken` 作为不透明字符串传给 `POST /api/v1/bot/deploy`。业务后端保存 token 引用或加密密文。

### 8.3 登录认证与 SSO / OA / HR

一期先实现简单账号密码登录，满足管理后台可用和权限联调需要。后续私有化部署对接客户统一登录系统时，保留同一套后端会话、RBAC 和数据权限模型，只替换身份认证入口。

一期本地登录边界：

| 能力 | 设计 |
| --- | --- |
| 账号来源 | 管理员在用户管理中创建，或通过初始化脚本创建首个超级管理员 |
| 登录凭据 | `username` + `password`，密码只保存强 hash，例如 bcrypt/argon2 |
| 会话 | 登录成功后颁发业务后端 access token，可选 refresh token；前端只持有业务后端 token |
| 权限 | 登录后按本地 `users`、`roles`、`permissions`、`departments` 计算 RBAC 和数据范围 |
| 安全 | 支持密码复杂度、登录失败锁定、会话过期、退出登录、登录日志 |
| 审计 | 登录成功、失败、退出、密码重置、账号冻结均写登录日志或操作审计 |

私有化客户登录系统对接方式：

| 模式 | 后端处理 |
| --- | --- |
| OIDC/OAuth2/SAML/CAS | 外部认证成功后映射或自动创建本地 `users`，再颁发本业务后端 token |
| LDAP/AD | 校验外部账号密码，按配置同步用户、部门、角色映射 |
| 网关免登录 | 从可信网关注入的用户标识解析身份，仍落到本地用户和权限模型 |
| OA/HR 同步 | 定时同步组织、人员、岗位，作为授权和数据范围基础 |

第一期提供本地账号密码登录和预留同步接口；企业侧字段确认后，新增 `org_sync_jobs` 定时同步组织、人员、岗位、角色映射。外部身份源只负责“证明用户是谁”，业务权限仍由 AstronClaw 后端统一计算，避免不同客户身份系统导致权限逻辑分叉。

## 9. 安全设计

1. 服务间密钥、模型密钥、租户应用密钥只存后端密钥系统或加密字段。
2. 审计日志中 token 只保留前后缀或 hash。
3. 所有高危操作，例如删除实例、下线实例、导出审计、查看密钥、变更模型，应校验高危权限并写审计。
4. 文件上传需做类型、大小、病毒、敏感信息校验。
5. 模型调用审计需存输入/输出摘要，不直接保存未脱敏敏感内容。
6. 数据导出统一走后端任务，校验权限并记录导出审计。

## 10. 可观测性与运维

| 能力 | 设计 |
| --- | --- |
| 请求追踪 | 每个请求生成 `request_id`，透传给日志和外部调用 |
| 指标 | 暴露接口耗时、错误率、任务队列积压、Claw Proxy 调用耗时 |
| 日志 | 结构化 JSON 日志，敏感字段脱敏 |
| 告警 | 任务失败、实例异常、模型不可用、存储不足、同步失败触发告警 |
| 巡检 | 定时巡检数据库、队列、Claw Proxy、Bridge、模型、对象存储 |

## 11. 对比源文档后的架构补充

### 11.1 新增领域模块

首版模块覆盖了主干能力。重新对比根目录需求文档和两个 Claw Proxy 对接文档后，后端还需要显式补充以下领域：

| 模块 | 补充原因 | 关键职责 |
| --- | --- | --- |
| `approval` | 批量删除、违规下线、导出审计、查看密钥、停用安全策略属于高危操作 | 审批单、审批节点、二次确认、双人复核、审批审计 |
| `seat` | FR-02.5 要求席位包、席位分配、席位回收、到期提醒 | 席位包管理、席位授权、跨部门调拨、席位不足拦截 |
| `share` | 系统范围包含实例共享 | 个人/部门/项目级共享、授权审批、授权回收、共享审计 |
| `channel` | FR-09 虽标注暂时不做，但消息推送和业务系统嵌入需预留 | 渠道台账、业务系统授权、调用来源审计、企业微信通知 |
| `sandbox_file` | Claw Proxy 提供开发文件读写下载 | 文件列表、搜索、读取、保存、下载 URL、etag 乐观锁、路径白名单 |
| `cron` | Claw Proxy 提供定时任务 | cron 台账、运行历史、表达式校验、渠道限制 |
| `team` | Claw Proxy 提供 Agent Team 查询 | Team 列表、进度、产物、结果、session_key 生成 |
| `backup` | Claw Proxy 提供备份恢复 | 备份任务、恢复任务、状态轮询、删除备份 |
| `quota_router` | FR-04.3 要求流量控制和智能路由 | QPS、Token、并发、日限额、过载策略、主备路由 |
| `diagnosis_kb` | FR-11.3 要求诊断知识库和决策树 | 错误码知识库、诊断决策树、故障沉淀 |

### 11.2 补充后的目录建议

```text
backend/app/
  api/v1/
    approval_routes.py
    seat_routes.py
    share_routes.py
    channel_routes.py
    sandbox_file_routes.py
    cron_routes.py
    team_routes.py
    backup_routes.py
    quota_routes.py
    diagnosis_kb_routes.py
  services/
    approval_service.py
    seat_service.py
    share_service.py
    channel_service.py
    sandbox_file_service.py
    cron_service.py
    team_service.py
    backup_service.py
    quota_router_service.py
    diagnosis_kb_service.py
  clients/
    dev_file_client.py
    cron_proxy.py
    team_api_client.py
    backup_client.py
```

### 11.3 补充数据模型

| 表 | 用途 | 关键字段 |
| --- | --- | --- |
| `approval_requests` | 高危操作审批 | `id`、`type`、`risk_level`、`applicant_id`、`status`、`payload_snapshot`、`created_at` |
| `approval_steps` | 审批节点 | `approval_id`、`step_no`、`approver_id`、`decision`、`comment`、`decided_at` |
| `seat_packages` | 席位包 | `id`、`name`、`total_count`、`used_count`、`expires_at`、`status` |
| `seat_assignments` | 席位分配 | `seat_package_id`、`assignee_type`、`assignee_id`、`agent_id`、`status` |
| `share_grants` | 实例共享 | `agent_id`、`scope_type`、`scope_id`、`permission`、`expires_at`、`status` |
| `message_channels` | 渠道台账 | `name`、`type`、`status`、`callback_url`、`auth_type`、`owner_id` |
| `business_systems` | 业务系统嵌入 | `name`、`embed_type`、`sso_mode`、`allowed_agent_ids`、`status` |
| `agent_dev_files_audit` | 沙箱文件操作审计 | `agent_id`、`operation`、`path`、`etag`、`operator_id`、`result` |
| `agent_crons` | 定时任务台账 | `id`、`agent_id`、`expression`、`type`、`task`、`time_zone`、`channel`、`status` |
| `agent_cron_runs` | 定时运行历史 | `cron_id`、`run_at`、`status`、`summary`、`error`、`duration_ms` |
| `agent_teams` | Team 缓存 | `agent_id`、`session_id`、`session_key`、`team_id`、`team_name` |
| `agent_team_executions` | Team 执行 | `team_id`、`execution_id`、`task_name`、`status`、`output_paths` |
| `backup_tasks` | 备份恢复 | `agent_id`、`type`、`proxy_task_id`、`status`、`phase`、`started_at`、`ended_at` |
| `model_quota_policies` | 模型限额 | `scope_type`、`scope_id`、`model_id`、`qps_limit`、`daily_call_limit`、`daily_token_limit` |
| `model_route_policies` | 智能路由 | `scope_type`、`strategy`、`primary_model_id`、`backup_model_id`、`fallback_policy` |
| `diagnosis_kb` | 诊断知识库 | `error_code`、`module`、`symptom`、`reason`、`solution`、`tags` |

### 11.4 Claw Proxy 代理边界

后端必须以业务对象 ID 作为前端接口入参，例如 `agentId`、`skillId`、`cronId`。`instanceId`、`packageName`、模型 `apiKey`、`astronmenApiKey`、`CLAW_PROXY_AUTH_TOKEN` 由后端从数据库或密钥系统读取。这样可以避免前端拼接沙箱路径，也避免密钥泄露。
