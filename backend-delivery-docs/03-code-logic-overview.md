# AstronClaw 后端代码逻辑概述

## 1. 请求处理主链路

```text
HTTP Request
  -> request_id middleware
  -> auth middleware
  -> permission/data-scope dependency
  -> route handler
  -> service
  -> repository / external client
  -> audit log
  -> unified response
```

统一响应：

```json
{
  "code": 0,
  "message": "success",
  "data": {},
  "requestId": "req_xxx"
}
```

分页响应：

```json
{
  "items": [],
  "page": 1,
  "pageSize": 20,
  "total": 0
}
```

## 2. 登录认证逻辑

一期先实现账号密码登录；后续私有化接入客户统一登录系统时，仍复用业务后端 token、RBAC 和数据权限。

账号密码登录：

```text
AuthRoutes.login
  -> 根据 username 查询 users
  -> 校验用户状态 active、锁定状态、密码过期状态
  -> 使用 bcrypt/argon2 校验 password_hash
  -> 查询 roles、permissions、data_scope
  -> 创建 sessions 或签发 JWT/refresh token
  -> 写 login_logs(result=success)
  -> 返回 accessToken、user、roles、permissions、dataScope
```

登录失败：

```text
AuthRoutes.login
  -> 用户不存在或密码错误
  -> 增加失败计数
  -> 达到阈值后锁定账号
  -> 写 login_logs(result=failed)
  -> 返回 401，不暴露密码 hash 或内部细节
```

退出登录：

```text
AuthRoutes.logout
  -> 撤销当前 session / token
  -> 写 login_logs 或 audit_logs
```

私有化 SSO：

```text
SsoRoutes.callback
  -> 校验客户身份源返回的 code/assertion/header
  -> 解析 external_subject / employee_no / mobile
  -> 映射或创建本地 users
  -> 复用本地权限计算
  -> 颁发业务后端 token
```

外部身份源只替换“用户如何证明自己是谁”，不替代后端的角色、权限、数据范围和审计模型。

## 3. 创建智能体逻辑

```text
AgentRoutes.create_agent
  -> PermissionService.require("agent:create")
  -> AgentService.validate_create_payload
  -> SeatService.check_available
  -> ModelService.check_model_available
  -> SkillService.check_skill_scope
  -> KnowledgeService.check_knowledge_scope
  -> BridgeClient.create_token
  -> AgentRepo.insert(status="deploying", bot_id="agt_xxx")
  -> DeployTaskRepo.insert(action="deploy")
  -> Batch/Deploy worker enqueue
  -> AuditService.record("agent:create")
```

异步部署 worker：

```text
DeployWorker.run(task_id)
  -> load agent and config snapshot
  -> build modelsConfig from llm_models + secret manager
  -> BotClient.deploy(botId, bridgeToken, modelsConfig, traceUid, astronmenApiKey)
  -> save proxy_instance_id
  -> SkillClient.install for each selected skill
  -> SkillClient.add_env if needed
  -> BotClient.restart if env changed
  -> update agent status to running
  -> update task status to success
  -> write audit
  -> on error: update status, write alert, write audit
```

## 4. 智能体详情逻辑

```text
GET /agents/{id}
  -> 校验 agent:view 和数据范围
  -> 查询 agents 主表
  -> 查询 runtime snapshot
  -> 查询绑定 Skill 和知识库
  -> 查询最近部署任务、告警、审计
  -> 组装详情 DTO 返回
```

详情不实时调用所有外部系统，优先使用最近同步快照，避免页面响应被 Claw Proxy 或监控系统拖慢。需要实时刷新时提供独立 `POST /agents/{id}/sync`。

## 5. 生命周期操作逻辑

### 5.1 重启

```text
AgentService.restart(agent_id)
  -> 校验状态 running/abnormal
  -> 创建 deploy_task(action="restart")
  -> worker 调用 BotClient.restart(instanceId)
  -> 触发健康检查
  -> 成功写 running，失败写 abnormal
```

### 5.2 停用

```text
AgentService.stop(agent_id)
  -> 校验状态 running/abnormal
  -> 状态置为 stopping
  -> worker 调用 BotClient.stop(instanceId)
  -> 状态置为 stopped
```

### 5.3 升级

```text
AgentService.upgrade(agent_id)
  -> 保存当前配置和版本快照
  -> 状态置为 upgrading
  -> worker 调用 BotUpgradeClient.upgrade(instanceId)
  -> 如果返回新 instanceId，则覆盖 proxy_instance_id
  -> 健康检查成功后进入 running
  -> 失败时支持按快照回滚
```

### 5.4 切换模型

```text
ModelSwitchService.switch(agent_id, model_id)
  -> 校验模型启用和权限
  -> 从 secret manager 取 apiKey
  -> 调用 PUT /api/v1/bot/{instanceId}/model
  -> 更新 agent.primary_model_id
  -> 写模型变更审计
```

## 6. 批量任务逻辑

```text
BatchRoutes.create
  -> 解析目标范围：当前页、筛选结果、部门、标签、导入清单
  -> 校验权限和影响范围
  -> 高危操作创建审批或二次确认
  -> 冻结目标 ID 列表
  -> 创建 batch_tasks 和 batch_task_items
  -> worker 分批执行
```

worker 执行原则：

1. 单个 item 成功或失败不影响整体继续，除非策略为失败暂停。
2. 每个 item 独立记录错误码、失败原因、开始结束时间。
3. 批量升级支持灰度批次和回滚。
4. 任务进度通过 `success_count`、`failed_count`、`skipped_count` 汇总。

## 7. 状态同步逻辑

```text
sync_agent_status job every N seconds
  -> 查询 running/deploying/upgrading/abnormal 实例
  -> 调用 Claw Proxy 或监控系统获取状态
  -> 更新 agent_runtime_snapshots
  -> 根据规则识别异常标签
  -> 状态变化写 audit 或 state event
  -> 触发告警规则
```

异常规则示例：

| 条件 | 标记 |
| --- | --- |
| Claw Proxy 返回 400003 | 会话失效 |
| 连续 3 次同步失败 | 状态同步失败 |
| QPS 高于阈值 | 队列积压风险 |
| 模型错误率高 | 模型不可用或降级 |
| 节点离线 | 容器运行异常 |

## 8. 告警与诊断逻辑

```text
AlertRuleEngine.evaluate(event/metric)
  -> 匹配规则
  -> 创建或合并告警
  -> P0/P1 自动进入 diagnosis_tickets
  -> 通知中心计数更新
  -> 可选企业微信/邮件推送
```

告警闭环：

```text
claim -> processing -> fix action -> verify -> close
```

修复动作成功后，反向更新告警、实例状态、巡检项。

## 9. Skill 管理逻辑

```text
SkillService.import_skill
  -> 校验上传文件或 URL
  -> 保存包到对象存储
  -> 执行格式校验、依赖校验、安全扫描
  -> 创建 skill(status=pending_review)
```

安装到智能体：

```text
SkillService.install_to_agent
  -> 校验 skill 已审核且用户有权限
  -> 调用 Claw Proxy /skill/install
  -> 更新 agent_bind_skills
  -> 写审计
```

## 10. 知识库逻辑

```text
KnowledgeService.upload
  -> 校验文件类型、大小、病毒、敏感信息
  -> 保存原始文件
  -> 创建 parse job
```

解析 job：

```text
parse -> chunk -> embedding -> index -> status indexed
```

绑定智能体时校验知识库范围，删除知识文件前检查是否被智能体引用。

## 11. 模型网关与成本逻辑

模型调用流水可以来自业务后端网关日志或下游模型网关回流。成本计算按日归档：

```text
model_call_logs + agent_runtime_snapshots + seat usage
  -> cost_daily_stats
  -> cost reports and budget alerts
```

密钥处理：

1. 新增模型时，完整 `apiKey` 写入密钥系统。
2. `llm_models.secret_ref` 保存引用。
3. 前端查询只返回 `apiKeyMasked`。
4. 部署和切换模型时后端临时读取密钥并传给 Claw Proxy。

## 12. 审计逻辑

所有写操作、高危读操作、导出操作都记录审计：

```text
AuditService.record(
  actor,
  module,
  action,
  object_type,
  object_id,
  before_value,
  after_value,
  result,
  ip,
  request_id
)
```

审计日志建议加入 hash 链字段 `hash_prev`、`hash_current`，为防篡改或 WORM 存储预留。

## 13. Claw Proxy 客户端逻辑

客户端统一实现：

1. 从配置读取 `CLAW_PROXY_BASE_URL`。
2. 从环境变量或密钥系统读取 `CLAW_PROXY_AUTH_TOKEN`。
3. 自动拼接 `/api/v1/bot`。
4. 注入 Bearer Token。
5. 统一超时、重试、错误码转换、脱敏日志。

错误转换示例：

| Claw Proxy 错误 | 业务后端错误 |
| --- | --- |
| `400003` | `SANDBOX_SESSION_EXPIRED` |
| `300003` | `BOT_DEPLOY_FAILED` |
| HTTP `404` | `SANDBOX_INSTANCE_NOT_FOUND` |
| timeout | `CLAW_PROXY_TIMEOUT` |

## 14. 补充代码逻辑

### 14.1 沙箱文件代理

```text
DevFileRoutes.list/read/save/download
  -> 校验 agent:view 或 agent:ops
  -> 根据 agentId 查 proxy_instance_id
  -> 校验 path 在 /root/.openclaw 白名单下
  -> 读取操作调用 DevFileClient
  -> 写入操作校验 etag 并写 agent_dev_files_audit
  -> 返回文件元信息、内容或 downloadUrl
```

### 14.2 Cron 任务

```text
CronService.create
  -> 校验 agent 权限和 channel 合法性
  -> 后端生成 cron id，例如 sat_xxx
  -> 保存 agent_crons(status=creating)
  -> 调用 CronProxy.create(instanceId, cron payload)
  -> 成功后 status=enabled
```

更新、删除和运行历史都必须复用后端生成的 cron `id`。

### 14.3 Team 查询

```text
TeamService.list_by_session(agent_id, session_id)
  -> session_key = "agent:main:main:{session_id}"
  -> 调用 TeamApiClient.list/progress/outputs/result
  -> 对 300080/300081/300083 按空结果处理
  -> 可选写入 agent_teams 缓存
```

Team 由 OpenClaw 对话过程触发创建，管理后端只负责查询和产物下载入口。

### 14.4 备份恢复

```text
BackupService.start_backup(agent_id)
  -> 调用 BackupClient.start(instanceId)
  -> 保存 backup_tasks(proxy_task_id, status=running)

BackupService.poll(task_id)
  -> 调用 /backup/status 或 /backup/restore/status
  -> 更新 status/phase
```

删除实例前如存在备份策略，需先判断是否保留备份或调用删除备份接口。

### 14.5 审批流

```text
HighRiskOperation.submit
  -> 计算 risk_level
  -> 保存 payload_snapshot
  -> 创建 approval_steps
  -> 通知审批人

ApprovalService.approve
  -> 校验审批人
  -> 审批通过后发布 operation event
  -> worker 按 payload_snapshot 执行
```

执行端不能使用前端重新提交的 payload，必须使用审批时冻结的快照。

### 14.6 实例共享

```text
ShareService.create_grant
  -> 校验 agent:share
  -> 校验席位
  -> 部门/项目级共享创建审批
  -> 审批通过后写 share_grants
  -> 聊天项目按 share_grants 判断普通用户可用资源
```

### 14.7 模型限流与路由

```text
ModelGateway.before_call
  -> resolve user/department/project/agent scope
  -> load quota policy
  -> check qps/concurrency/daily token
  -> choose model route
  -> record policy hit
```

模型调用完成后写 `model_call_logs` 并产生成本事件。
