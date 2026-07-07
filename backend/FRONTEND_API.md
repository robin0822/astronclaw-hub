# AstronClaw 后端接口说明文档（前端版）

本文档按当前 `backend/app` 实际 FastAPI OpenAPI 自动同步，供前端开发联调使用。

## 1. 接入概览

- 服务地址：`http://127.0.0.1:8000`
- 业务 API 前缀：`/api/v1/astron-claw`
- OpenAPI/Swagger：`http://127.0.0.1:8000/docs`
- 认证方式：登录后在请求头携带 `Authorization: Bearer <accessToken>`
- 当前实际 operation 数：`232`，其中业务接口 `226` 个，开发/测试辅助接口 `5` 个，健康检查 `1` 个。

## 2. 统一响应

成功响应统一为：

```json
{"code":0,"message":"success","data":{},"requestId":"req_xxx"}
```

失败响应统一为：

```json
{"code":403001,"message":"forbidden","data":{},"requestId":"req_xxx"}
```

分页对象通常为：

```json
{"items":[],"page":1,"pageSize":20,"total":0}
```

## 3. 登录示例

```http
POST /api/v1/astron-claw/auth/login
Content-Type: application/json
```

```json
{"username":"admin","password":"Admin@123456"}
```

前端保存 `data.accessToken`，后续请求统一携带：

```http
Authorization: Bearer <accessToken>
```

## 4. 常见错误码

| code | 含义 | 前端建议 |
| --- | --- | --- |
| `400001` | 请求参数或业务对象无效 | 展示字段级提示或刷新列表 |
| `401001` | 未登录或 token 无效 | 跳转登录页 |
| `401002` | 账号锁定 | 展示锁定提示 |
| `401003` | 账号停用 | 提示联系管理员 |
| `401004` | 密码过期 | 引导重置密码 |
| `403001` | 权限不足 | 隐藏入口或提示无权限 |
| `409001` | 状态不允许 | 刷新对象状态后重试 |
| `409002` | 需要审批 | 展示审批单状态并引导审批 |
| `422001` | 配额不足或限流 | 展示剩余额度、预算或限流提示 |
| `502001` | Claw Proxy/Bridge 超时 | 提示稍后重试 |
| `502002` | 沙箱会话失效 | 引导同步或重新部署 |

## 5. 接口目录

表格说明：`路径参数` 和 `Query` 中带 `*` 表示 OpenAPI 标记为必填；`Body` 为请求体 schema 名称或 `object`；`Response` 为统一响应中的 `data` 结构提示，实际仍包在统一响应对象内。

### 健康检查

| Method | Path | 说明 | 路径参数 | Query | Body | Response | 权限/备注 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `GET` | `/health` | Health | - | - | - | - | 公开 |

### 开发/测试辅助

| Method | Path | 说明 | 路径参数 | Query | Body | Response | 权限/备注 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `POST` | `/dev/agent-logs` | Dev Agent Log | - | - | object | - | 开发/测试辅助，生产前端不要调用 |
| `POST` | `/dev/cost/archive` | Dev Archive Cost | - | - | object | - | 开发/测试辅助，生产前端不要调用 |
| `POST` | `/dev/model-call-logs` | Dev Model Call Log | - | - | object | - | 开发/测试辅助，生产前端不要调用 |
| `POST` | `/dev/model-gateway/call` | Dev Model Gateway Call | - | - | object | - | 开发/测试辅助，生产前端不要调用 |
| `POST` | `/dev/seed` | Dev Seed | - | - | - | - | 开发/测试辅助，生产前端不要调用 |

### 认证与当前用户

| Method | Path | 说明 | 路径参数 | Query | Body | Response | 权限/备注 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `POST` | `/auth/login` | Login | - | - | LoginRequest | - | 登录/验证码/密码流程，除 /auth/logout 外无需 token |
| `POST` | `/auth/logout` | Logout | - | - | - | - | 登录/验证码/密码流程，除 /auth/logout 外无需 token |
| `POST` | `/auth/refresh` | Refresh Token | - | - | object | - | 登录/验证码/密码流程，除 /auth/logout 外无需 token |
| `GET` | `/auth/sso/callback` | Sso Callback | - | provider, subject, username | - | - | 登录/验证码/密码流程，除 /auth/logout 外无需 token |
| `GET` | `/auth/sso/login` | Sso Login | - | provider | - | - | 登录/验证码/密码流程，除 /auth/logout 外无需 token |
| `POST` | `/auth/sso/logout` | Sso Logout | - | - | - | - | 登录/验证码/密码流程，除 /auth/logout 外无需 token |
| `GET` | `/me` | Me | - | - | - | - | 登录用户 |
| `GET` | `/me/permissions` | Me Permissions | - | - | - | - | 登录用户 |

### Agent 管理

| Method | Path | 说明 | 路径参数 | Query | Body | Response | 权限/备注 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `GET` | `/agents` | List Agents | - | keyword, status, departmentId, ownerId, modelId, page, pageSize | - | - | agent:view/create/update/delete/deploy/ops/batch/share 按动作区分 |
| `POST` | `/agents` | Create Agent | - | - | AgentCreateRequest | - | agent:view/create/update/delete/deploy/ops/batch/share 按动作区分 |
| `DELETE` | `/agents/{agent_id}` | Delete Agent | agent_id* | - | - | - | agent:view/create/update/delete/deploy/ops/batch/share 按动作区分 |
| `GET` | `/agents/{agent_id}` | Get Agent | agent_id* | - | - | - | agent:view/create/update/delete/deploy/ops/batch/share 按动作区分 |
| `POST` | `/agents/{agent_id}/archive` | Lifecycle | agent_id* | - | object | - | agent:view/create/update/delete/deploy/ops/batch/share 按动作区分 |
| `POST` | `/agents/{agent_id}/backup-restore` | Restore Backup | agent_id* | - | object | - | agent:ops 写操作 |
| `GET` | `/agents/{agent_id}/backup-restore/{task_id}` | Backup Status | agent_id*, task_id* | - | - | - | agent:ops 写操作 |
| `DELETE` | `/agents/{agent_id}/backups` | Delete Backups | agent_id* | - | - | - | agent:ops 写操作 |
| `POST` | `/agents/{agent_id}/backups` | Start Backup | agent_id* | - | - | - | agent:ops 写操作 |
| `GET` | `/agents/{agent_id}/backups/{task_id}` | Backup Status | agent_id*, task_id* | - | - | - | agent:ops 写操作 |
| `GET` | `/agents/{agent_id}/crons` | List Crons | agent_id* | - | - | - | agent:ops 写操作 |
| `POST` | `/agents/{agent_id}/crons` | Create Cron | agent_id* | - | object | - | agent:ops 写操作 |
| `DELETE` | `/agents/{agent_id}/crons/{cron_id}` | Delete Cron | agent_id*, cron_id* | - | - | - | agent:ops 写操作 |
| `PUT` | `/agents/{agent_id}/crons/{cron_id}` | Update Cron | agent_id*, cron_id* | - | object | - | agent:ops 写操作 |
| `GET` | `/agents/{agent_id}/crons/{cron_id}/runs` | Cron Runs | agent_id*, cron_id* | limit | - | - | agent:ops 写操作 |
| `POST` | `/agents/{agent_id}/deploy` | Lifecycle | agent_id* | - | object | - | agent:deploy 或 agent:ops |
| `GET` | `/agents/{agent_id}/dev-file/content` | Dev File Content | agent_id* | path* | - | - | agent:view/create/update/delete/deploy/ops/batch/share 按动作区分 |
| `PUT` | `/agents/{agent_id}/dev-file/content` | Save Dev File | agent_id* | - | object | - | agent:view/create/update/delete/deploy/ops/batch/share 按动作区分 |
| `GET` | `/agents/{agent_id}/dev-file/download` | Download Dev File | agent_id* | path* | - | - | agent:view/create/update/delete/deploy/ops/batch/share 按动作区分 |
| `GET` | `/agents/{agent_id}/dev-file/meta` | Dev File Meta | agent_id* | path* | - | - | agent:view/create/update/delete/deploy/ops/batch/share 按动作区分 |
| `GET` | `/agents/{agent_id}/dev-files` | Dev Files | agent_id* | path, page, pageSize | - | - | agent:view/create/update/delete/deploy/ops/batch/share 按动作区分 |
| `GET` | `/agents/{agent_id}/dev-files/search` | Dev File Search | agent_id* | keyword*, path | - | - | agent:view/create/update/delete/deploy/ops/batch/share 按动作区分 |
| `DELETE` | `/agents/{agent_id}/knowledge-bases/{kb_id}/bind` | Unbind Kb | agent_id*, kb_id* | - | - | - | agent:view/create/update/delete/deploy/ops/batch/share 按动作区分 |
| `POST` | `/agents/{agent_id}/knowledge-bases/{kb_id}/bind` | Bind Kb | agent_id*, kb_id* | - | - | - | agent:view/create/update/delete/deploy/ops/batch/share 按动作区分 |
| `GET` | `/agents/{agent_id}/logs` | Agent Logs | agent_id* | logType, level, keyword, startTime, endTime, page, pageSize | - | - | agent:ops 写操作 |
| `GET` | `/agents/{agent_id}/memory-preview` | Memory Preview | agent_id* | - | - | - | agent:view/create/update/delete/deploy/ops/batch/share 按动作区分 |
| `PUT` | `/agents/{agent_id}/model` | Switch Model | agent_id* | - | object | - | agent:view/create/update/delete/deploy/ops/batch/share 按动作区分 |
| `GET` | `/agents/{agent_id}/plugins/astronmem` | Astronmem Status | agent_id* | - | - | - | agent:ops 写操作 |
| `POST` | `/agents/{agent_id}/plugins/astronmem` | Astronmem Toggle | agent_id* | - | object | - | agent:ops 写操作 |
| `POST` | `/agents/{agent_id}/restart` | Lifecycle | agent_id* | - | object | - | agent:deploy 或 agent:ops |
| `POST` | `/agents/{agent_id}/rollback` | Rollback Agent | agent_id* | - | object | - | agent:view/create/update/delete/deploy/ops/batch/share 按动作区分 |
| `GET` | `/agents/{agent_id}/runtime-config` | Get Runtime Config | agent_id* | page, pageSize | - | - | agent:view/create/update/delete/deploy/ops/batch/share 按动作区分 |
| `PUT` | `/agents/{agent_id}/runtime-config` | Runtime Config | agent_id* | - | object | - | agent:view/create/update/delete/deploy/ops/batch/share 按动作区分 |
| `GET` | `/agents/{agent_id}/runtime-skills` | Runtime Skills | agent_id* | - | - | - | agent:view/create/update/delete/deploy/ops/batch/share 按动作区分 |
| `GET` | `/agents/{agent_id}/share-grants` | List Share | agent_id* | - | - | - | agent:view/create/update/delete/deploy/ops/batch/share 按动作区分 |
| `POST` | `/agents/{agent_id}/share-grants` | Create Share | agent_id* | - | object | - | agent:view/create/update/delete/deploy/ops/batch/share 按动作区分 |
| `DELETE` | `/agents/{agent_id}/share-grants/{grant_id}` | Delete Share | agent_id*, grant_id* | - | - | - | agent:view/create/update/delete/deploy/ops/batch/share 按动作区分 |
| `DELETE` | `/agents/{agent_id}/skill-env-vars` | Delete Skill Env Vars | agent_id* | - | object | - | agent:ops 写操作 |
| `GET` | `/agents/{agent_id}/skill-env-vars` | Skill Env Vars | agent_id* | - | - | - | agent:ops 写操作 |
| `PUT` | `/agents/{agent_id}/skill-env-vars` | Put Skill Env Vars | agent_id* | - | object | - | agent:ops 写操作 |
| `POST` | `/agents/{agent_id}/skills/{skill_id}/install` | Bind Skill | agent_id*, skill_id* | - | - | - | agent:view/create/update/delete/deploy/ops/batch/share 按动作区分 |
| `POST` | `/agents/{agent_id}/skills/{skill_id}/uninstall` | Bind Skill | agent_id*, skill_id* | - | - | - | agent:view/create/update/delete/deploy/ops/batch/share 按动作区分 |
| `POST` | `/agents/{agent_id}/start` | Lifecycle | agent_id* | - | object | - | agent:deploy 或 agent:ops |
| `GET` | `/agents/{agent_id}/state-events` | Agent State Events | agent_id* | page, pageSize | - | - | agent:view/create/update/delete/deploy/ops/batch/share 按动作区分 |
| `POST` | `/agents/{agent_id}/stop` | Lifecycle | agent_id* | - | object | - | agent:deploy 或 agent:ops |
| `POST` | `/agents/{agent_id}/sync` | Sync Agent | agent_id* | - | - | - | agent:view/create/update/delete/deploy/ops/batch/share 按动作区分 |
| `GET` | `/agents/{agent_id}/teams` | Teams | agent_id* | sessionId* | - | - | agent:view/create/update/delete/deploy/ops/batch/share 按动作区分 |
| `GET` | `/agents/{agent_id}/teams/{team_id}/outputs` | Team Kind | agent_id*, team_id* | sessionId* | - | - | agent:view/create/update/delete/deploy/ops/batch/share 按动作区分 |
| `GET` | `/agents/{agent_id}/teams/{team_id}/progress` | Team Kind | agent_id*, team_id* | sessionId* | - | - | agent:view/create/update/delete/deploy/ops/batch/share 按动作区分 |
| `GET` | `/agents/{agent_id}/teams/{team_id}/result` | Team Kind | agent_id*, team_id* | sessionId* | - | - | agent:view/create/update/delete/deploy/ops/batch/share 按动作区分 |
| `POST` | `/agents/{agent_id}/upgrade` | Lifecycle | agent_id* | - | object | - | agent:view/create/update/delete/deploy/ops/batch/share 按动作区分 |
| `GET` | `/agents/{agent_id}/versions` | Agent Versions | agent_id* | page, pageSize | - | - | agent:view/create/update/delete/deploy/ops/batch/share 按动作区分 |
| `POST` | `/agents/{agent_id}/violation-offline` | Lifecycle | agent_id* | - | object | - | agent:view/create/update/delete/deploy/ops/batch/share 按动作区分 |
| `POST` | `/batch-tasks` | Create Batch | - | - | object | - | agent:batch |
| `GET` | `/batch-tasks/{batch_id}` | Get Batch | batch_id* | - | - | - | agent:batch |
| `GET` | `/batch-tasks/{batch_id}/export` | Export Batch | batch_id* | - | - | - | agent:batch |
| `GET` | `/batch-tasks/{batch_id}/items` | Get Batch Items | batch_id* | page, pageSize | - | - | agent:batch |

### Skill 与知识库

| Method | Path | 说明 | 路径参数 | Query | Body | Response | 权限/备注 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `GET` | `/knowledge-bases` | Knowledge Bases | - | - | - | - | knowledge:manage 写操作；列表按数据权限 |
| `POST` | `/knowledge-bases` | Create Kb | - | - | object | - | knowledge:manage 写操作；列表按数据权限 |
| `GET` | `/knowledge-bases/{kb_id}/files` | Kb Files | kb_id* | - | - | - | knowledge:manage 写操作；列表按数据权限 |
| `POST` | `/knowledge-bases/{kb_id}/files` | Create Kb File | kb_id* | - | object | - | knowledge:manage 写操作；列表按数据权限 |
| `GET` | `/knowledge-bases/{kb_id}/grants` | Knowledge Grants | kb_id* | - | - | - | knowledge:manage 写操作；列表按数据权限 |
| `POST` | `/knowledge-bases/{kb_id}/grants` | Create Knowledge Grant | kb_id* | - | object | - | knowledge:manage 写操作；列表按数据权限 |
| `DELETE` | `/knowledge-files/{file_id}` | Delete Knowledge File | file_id* | - | - | - | knowledge:manage 写操作；列表按数据权限 |
| `POST` | `/knowledge-files/{file_id}/reindex` | Reindex Knowledge File | file_id* | - | - | - | knowledge:manage 写操作；列表按数据权限 |
| `GET` | `/skills` | Skills | - | keyword, status, source, category, page, pageSize | - | - | skill:manage 写操作；列表按登录用户可见范围 |
| `POST` | `/skills` | Create Skill | - | - | object | - | skill:manage 写操作；列表按登录用户可见范围 |
| `POST` | `/skills/import` | Create Skill | - | - | object | - | skill:manage 写操作；列表按登录用户可见范围 |
| `GET` | `/skills/{skill_id}` | Skill Detail | skill_id* | - | - | - | skill:manage 写操作；列表按登录用户可见范围 |
| `PUT` | `/skills/{skill_id}` | Update Skill | skill_id* | - | object | - | skill:manage 写操作；列表按登录用户可见范围 |
| `GET` | `/skills/{skill_id}/grants` | Skill Grants | skill_id* | - | - | - | skill:manage 写操作；列表按登录用户可见范围 |
| `POST` | `/skills/{skill_id}/grants` | Create Skill Grant | skill_id* | - | object | - | skill:manage 写操作；列表按登录用户可见范围 |
| `POST` | `/skills/{skill_id}/review` | Review Skill | skill_id* | - | object | - | skill:manage 写操作；列表按登录用户可见范围 |
| `GET` | `/skills/{skill_id}/reviews` | Skill Reviews | skill_id* | - | - | - | skill:manage 写操作；列表按登录用户可见范围 |
| `GET` | `/skills/{skill_id}/versions` | Skill Versions | skill_id* | - | - | - | skill:manage 写操作；列表按登录用户可见范围 |

### 模型与网关

| Method | Path | 说明 | 路径参数 | Query | Body | Response | 权限/备注 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `GET` | `/model-call-logs` | Model Logs | - | page, pageSize, modelId, agentId, userId, departmentId, projectId, status, startTime, endTime | - | - | 登录用户；部分写操作按 RBAC 校验 |
| `GET` | `/model-policy-hits` | Policy Hits | - | startTime, endTime, modelId | - | - | model:manage；密钥明文需要 model:secret_view |
| `GET` | `/model-quotas` | Model Quotas | - | - | - | - | 登录用户；部分写操作按 RBAC 校验 |
| `POST` | `/model-quotas` | Create Model Quota | - | - | object | - | 登录用户；部分写操作按 RBAC 校验 |
| `DELETE` | `/model-quotas/{quota_id}` | Delete Model Quota | quota_id* | - | - | - | 登录用户；部分写操作按 RBAC 校验 |
| `PUT` | `/model-quotas/{quota_id}` | Update Model Quota | quota_id* | - | object | - | 登录用户；部分写操作按 RBAC 校验 |
| `GET` | `/model-route-policies` | Route Policies | - | - | - | - | 登录用户；部分写操作按 RBAC 校验 |
| `POST` | `/model-route-policies` | Create Route Policy | - | - | object | - | 登录用户；部分写操作按 RBAC 校验 |
| `DELETE` | `/model-route-policies/{policy_id}` | Delete Route Policy | policy_id* | - | - | - | 登录用户；部分写操作按 RBAC 校验 |
| `PUT` | `/model-route-policies/{policy_id}` | Update Route Policy | policy_id* | - | object | - | 登录用户；部分写操作按 RBAC 校验 |
| `GET` | `/models` | Models | - | page, pageSize, keyword, status, provider, type | - | - | model:manage；密钥明文需要 model:secret_view |
| `POST` | `/models` | Create Model | - | - | object | - | model:manage；密钥明文需要 model:secret_view |
| `GET` | `/models/{model_id}` | Model Detail | model_id* | - | - | - | model:manage；密钥明文需要 model:secret_view |
| `PUT` | `/models/{model_id}` | Update Model | model_id* | - | object | - | model:manage；密钥明文需要 model:secret_view |
| `POST` | `/models/{model_id}/disable` | Model Action | model_id* | - | object | - | model:manage；密钥明文需要 model:secret_view |
| `POST` | `/models/{model_id}/enable` | Model Action | model_id* | - | object | - | model:manage；密钥明文需要 model:secret_view |
| `POST` | `/models/{model_id}/probe` | Model Action | model_id* | - | object | - | model:manage；密钥明文需要 model:secret_view |
| `GET` | `/models/{model_id}/secret` | Model Secret View | model_id* | - | - | - | model:manage；密钥明文需要 model:secret_view |

### 监控、告警、诊断与成本

| Method | Path | 说明 | 路径参数 | Query | Body | Response | 权限/备注 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `GET` | `/alerts` | Alerts | - | page, pageSize, level, status, sourceType, departmentId, startTime, endTime | - | - | alert:manage 写操作；列表登录可读 |
| `POST` | `/alerts` | Create Alert | - | - | object | - | alert:manage 写操作；列表登录可读 |
| `GET` | `/alerts/{alert_id}` | Alert Detail | alert_id* | - | - | - | alert:manage 写操作；列表登录可读 |
| `POST` | `/alerts/{alert_id}/claim` | Alert Action | alert_id* | - | object | - | alert:manage 写操作；列表登录可读 |
| `POST` | `/alerts/{alert_id}/close` | Alert Action | alert_id* | - | object | - | alert:manage 写操作；列表登录可读 |
| `GET` | `/alerts/{alert_id}/events` | Alert Events | alert_id* | - | - | - | alert:manage 写操作；列表登录可读 |
| `POST` | `/alerts/{alert_id}/process` | Alert Action | alert_id* | - | object | - | alert:manage 写操作；列表登录可读 |
| `POST` | `/alerts/{alert_id}/suspend` | Alert Action | alert_id* | - | object | - | alert:manage 写操作；列表登录可读 |
| `POST` | `/alerts/{alert_id}/transfer` | Alert Action | alert_id* | - | object | - | alert:manage 写操作；列表登录可读 |
| `GET` | `/cost-rules` | List Cost Rules | - | ruleType, status, page, pageSize | - | - | security:manage / ops:manage / monitor:view 按接口区分 |
| `POST` | `/cost-rules` | Create Cost Rule | - | - | CostRuleRequest | - | security:manage / ops:manage / monitor:view 按接口区分 |
| `GET` | `/cost/by-agent` | Cost | - | startDate, endDate, departmentId, projectId, period | - | - | security:manage / ops:manage / monitor:view 按接口区分 |
| `GET` | `/cost/by-department` | Cost | - | startDate, endDate, departmentId, projectId, period | - | - | security:manage / ops:manage / monitor:view 按接口区分 |
| `GET` | `/cost/by-model` | Cost | - | startDate, endDate, departmentId, projectId, period | - | - | security:manage / ops:manage / monitor:view 按接口区分 |
| `GET` | `/cost/by-project` | Cost | - | startDate, endDate, departmentId, projectId, period | - | - | security:manage / ops:manage / monitor:view 按接口区分 |
| `GET` | `/cost/by-resource-package` | Cost | - | startDate, endDate, departmentId, projectId, period | - | - | security:manage / ops:manage / monitor:view 按接口区分 |
| `GET` | `/cost/export` | Cost Export | - | dimension, startDate, endDate, departmentId, projectId, period | - | - | security:manage / ops:manage / monitor:view 按接口区分 |
| `GET` | `/cost/overview` | Cost | - | startDate, endDate, departmentId, projectId, period | - | - | security:manage / ops:manage / monitor:view 按接口区分 |
| `GET` | `/diagnostics` | Diagnostics | - | page, pageSize, level, objectType | - | - | security:manage / ops:manage / monitor:view 按接口区分 |
| `GET` | `/diagnostics/{diagnosis_id}` | Diagnosis Detail | diagnosis_id* | - | - | - | security:manage / ops:manage / monitor:view 按接口区分 |
| `POST` | `/diagnostics/{diagnosis_id}/fix` | Fix Diagnosis | diagnosis_id* | - | object | - | security:manage / ops:manage / monitor:view 按接口区分 |
| `GET` | `/inspection-runs/{run_id}` | Inspection Run | run_id* | - | - | - | security:manage / ops:manage / monitor:view 按接口区分 |
| `GET` | `/inspection-runs/{run_id}/export` | Inspection Export | run_id* | format | - | - | security:manage / ops:manage / monitor:view 按接口区分 |
| `GET` | `/inspection-tasks` | Inspection Tasks | - | - | - | - | security:manage / ops:manage / monitor:view 按接口区分 |
| `POST` | `/inspection-tasks` | Create Inspection Task | - | - | object | - | security:manage / ops:manage / monitor:view 按接口区分 |
| `POST` | `/inspection-tasks/{task_id}/run` | Run Inspection | task_id* | - | object | - | security:manage / ops:manage / monitor:view 按接口区分 |
| `GET` | `/monitor/metrics` | List Metrics | - | sourceType, sourceId, metricName, page, pageSize | - | - | security:manage / ops:manage / monitor:view 按接口区分 |
| `POST` | `/monitor/metrics` | Collect Metrics | - | - | object | - | security:manage / ops:manage / monitor:view 按接口区分 |
| `GET` | `/monitor/overview` | Monitor Overview | - | - | - | - | security:manage / ops:manage / monitor:view 按接口区分 |
| `GET` | `/ops-tasks` | List Ops Tasks | - | status, taskType, targetType, page, pageSize | - | - | security:manage / ops:manage / monitor:view 按接口区分 |
| `POST` | `/ops-tasks` | Create Ops Task | - | - | object | - | security:manage / ops:manage / monitor:view 按接口区分 |
| `GET` | `/ops-tasks/{task_id}` | Ops Task Detail | task_id* | - | - | - | security:manage / ops:manage / monitor:view 按接口区分 |
| `GET` | `/security-policies` | Security Policies | - | category, status | - | - | security:manage / ops:manage / monitor:view 按接口区分 |
| `GET` | `/security-policies/{policy_id}` | Security Policy Detail | policy_id* | - | - | - | security:manage / ops:manage / monitor:view 按接口区分 |
| `PUT` | `/security-policies/{policy_id}` | Update Security Policy | policy_id* | - | object | - | security:manage / ops:manage / monitor:view 按接口区分 |

### 审计、审批与导出

| Method | Path | 说明 | 路径参数 | Query | Body | Response | 权限/备注 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `GET` | `/approvals` | Approvals | - | page, pageSize, status, type | - | - | approval:manage 决策；创建/列表登录可用 |
| `POST` | `/approvals` | Create Approval | - | - | object | - | approval:manage 决策；创建/列表登录可用 |
| `GET` | `/approvals/{approval_id}` | Approval Detail | approval_id* | - | - | - | approval:manage 决策；创建/列表登录可用 |
| `POST` | `/approvals/{approval_id}/approve` | Approval Action | approval_id* | - | object | - | approval:manage 决策；创建/列表登录可用 |
| `POST` | `/approvals/{approval_id}/reject` | Approval Action | approval_id* | - | object | - | approval:manage 决策；创建/列表登录可用 |
| `GET` | `/audit/export` | Audit Export | - | approvalId | - | - | audit:export；导出下载会记录敏感事件 |
| `GET` | `/audit/login-logs` | Audit Login Logs | - | page, pageSize, userId, status, startTime, endTime | - | - | audit:view；导出类接口需要 audit:export |
| `GET` | `/audit/model-call-logs` | Model Logs | - | page, pageSize, modelId, agentId, userId, departmentId, projectId, status, startTime, endTime | - | - | audit:view；导出类接口需要 audit:export |
| `GET` | `/audit/model-call-logs/export` | Model Call Logs Export | - | approvalId | - | - | audit:export；导出下载会记录敏感事件 |
| `GET` | `/audit/operation-logs` | Operation Logs | - | page, pageSize, module, actorId, action, startTime, endTime | - | - | audit:view；导出类接口需要 audit:export |
| `GET` | `/audit/sensitive-events` | Sensitive Events | - | page, pageSize, eventType, objectType, objectId, actorId, result | - | - | audit:view；导出类接口需要 audit:export |
| `GET` | `/exports` | List Exports | - | page, pageSize, type, status, applicantId | - | - | audit:export；导出下载会记录敏感事件 |
| `GET` | `/exports/{export_key}` | Get Export | export_key* | - | - | - | audit:export；导出下载会记录敏感事件 |
| `GET` | `/exports/{export_key}/download` | Download Export | export_key* | - | - | - | audit:export；导出下载会记录敏感事件 |

### 组织、SSO、角色与席位

| Method | Path | 说明 | 路径参数 | Query | Body | Response | 权限/备注 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `GET` | `/org/departments/tree` | Departments Tree | - | - | - | - | security:manage |
| `GET` | `/org/positions` | Positions | - | departmentId, status, page, pageSize | - | - | security:manage |
| `POST` | `/org/positions` | Create Position | - | - | object | - | security:manage |
| `PUT` | `/org/positions/{position_id}` | Update Position | position_id* | - | object | - | security:manage |
| `GET` | `/org/sync-jobs` | Org Sync Jobs | - | page, pageSize, status, source | - | - | security:manage |
| `POST` | `/org/sync-jobs` | Create Org Sync Job | - | - | object | - | security:manage |
| `GET` | `/org/sync-jobs/{job_id}` | Org Sync Job Detail | job_id* | - | - | - | security:manage |
| `GET` | `/org/users` | Users | - | page, pageSize, keyword, departmentId, status, seatStatus | - | - | security:manage |
| `POST` | `/org/users/{user_id}/password-reset` | Reset User Password | user_id* | - | object | - | security:manage |
| `PUT` | `/org/users/{user_id}/status` | Update User Status | user_id* | - | object | - | security:manage |
| `GET` | `/roles` | Roles | - | page, pageSize, keyword, status | - | - | security:manage |
| `POST` | `/roles` | Create Role | - | - | object | - | security:manage |
| `DELETE` | `/roles/{role_id}` | Delete Role | role_id* | - | - | - | security:manage |
| `PUT` | `/roles/{role_id}` | Update Role | role_id* | - | object | - | security:manage |
| `PUT` | `/roles/{role_id}/permissions` | Update Role Permissions | role_id* | - | object | - | security:manage |
| `GET` | `/seat-assignments` | Seat Assignments | - | departmentId, userId, agentId | - | - | seat:manage |
| `POST` | `/seat-assignments` | Create Seat Assignment | - | - | object | - | seat:manage |
| `DELETE` | `/seat-assignments/{assignment_id}` | Delete Seat Assignment | assignment_id* | - | - | - | seat:manage |
| `POST` | `/seat-assignments/{assignment_id}/transfer` | Transfer Seat | assignment_id* | - | object | - | seat:manage |
| `GET` | `/seat-events` | Seat Events | - | page, pageSize, seatPackageId, assignmentId, eventType, assigneeId | - | - | seat:manage |
| `GET` | `/seat-packages` | Seat Packages | - | - | - | - | seat:manage |
| `POST` | `/seat-packages` | Create Seat Package | - | - | object | - | seat:manage |
| `GET` | `/sso/providers` | List Sso Providers | - | - | - | - | security:manage |
| `POST` | `/sso/providers` | Create Sso Provider | - | - | object | - | security:manage |
| `PUT` | `/sso/providers/{provider_id}` | Update Sso Provider | provider_id* | - | object | - | security:manage |

### 渠道与业务系统

| Method | Path | 说明 | 路径参数 | Query | Body | Response | 权限/备注 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `GET` | `/business-system-audit-logs` | Business System Audit Logs | - | systemId, agentId, page, pageSize | - | - | ops:manage 写操作 |
| `GET` | `/business-systems` | Business Systems | - | - | - | - | ops:manage 写操作 |
| `POST` | `/business-systems` | Create Business System | - | - | object | - | ops:manage 写操作 |
| `POST` | `/business-systems/{system_id}/access` | Business System Access | system_id* | - | object | - | ops:manage 写操作 |
| `GET` | `/business-systems/{system_id}/agents` | Business System Agents | system_id* | - | - | - | ops:manage 写操作 |
| `PUT` | `/business-systems/{system_id}/agents` | Update Business Agents | system_id* | - | object | - | ops:manage 写操作 |
| `GET` | `/channel-audit-logs` | Channel Audit Logs | - | page, pageSize, module, action | - | - | ops:manage 写操作 |
| `GET` | `/channel-message-logs` | Channel Message Logs | - | channelId, sourceType, page, pageSize | - | - | ops:manage 写操作 |
| `GET` | `/channels` | Channels | - | - | - | - | ops:manage 写操作 |
| `POST` | `/channels` | Create Channel | - | - | object | - | ops:manage 写操作 |
| `PUT` | `/channels/{channel_id}` | Update Channel | channel_id* | - | object | - | ops:manage 写操作 |
| `GET` | `/channels/{channel_id}/agents` | Channel Agents | channel_id* | - | - | - | ops:manage 写操作 |
| `PUT` | `/channels/{channel_id}/agents` | Update Channel Agents | channel_id* | - | object | - | ops:manage 写操作 |
| `POST` | `/channels/{channel_id}/disable` | Channel Action | channel_id* | - | - | - | ops:manage 写操作 |
| `POST` | `/channels/{channel_id}/messages` | Create Channel Message | channel_id* | - | object | - | ops:manage 写操作 |
| `POST` | `/channels/{channel_id}/reconnect` | Channel Action | channel_id* | - | - | - | ops:manage 写操作 |
| `POST` | `/channels/{channel_id}/test` | Channel Action | channel_id* | - | - | - | ops:manage 写操作 |

### 记忆与运行时代理

| Method | Path | 说明 | 路径参数 | Query | Body | Response | 权限/备注 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `GET` | `/memories` | Memories | - | scope, keyword, page, pageSize | - | - | 登录用户；按数据范围隔离 |
| `POST` | `/memories` | Create Memory | - | - | object | - | 登录用户；按数据范围隔离 |
| `DELETE` | `/memories/{memory_id}` | Delete Memory | memory_id* | - | - | - | 登录用户；按数据范围隔离 |
| `PUT` | `/memories/{memory_id}` | Update Memory | memory_id* | - | object | - | 登录用户；按数据范围隔离 |
| `POST` | `/memories/{memory_id}/share` | Share Memory | memory_id* | - | object | - | 登录用户；按数据范围隔离 |
| `GET` | `/memory-share-requests` | Memory Share Requests | - | status, memoryId, page, pageSize | - | - | 登录用户；按数据范围隔离 |

### 其他接口

| Method | Path | 说明 | 路径参数 | Query | Body | Response | 权限/备注 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `GET` | `/agent-tasks/{task_id}` | Get Task | task_id* | - | - | - | 登录用户；部分写操作按 RBAC 校验 |
| `GET` | `/alert-rules` | List Alert Rules | - | status, metricName, page, pageSize | - | - | 登录用户；部分写操作按 RBAC 校验 |
| `POST` | `/alert-rules` | Create Alert Rule | - | - | object | - | 登录用户；部分写操作按 RBAC 校验 |
| `PUT` | `/alert-rules/{rule_id}` | Update Alert Rule | rule_id* | - | object | - | 登录用户；部分写操作按 RBAC 校验 |
| `GET` | `/budgets` | List Budgets | - | scopeType, scopeId, status, page, pageSize | - | - | 登录用户；部分写操作按 RBAC 校验 |
| `POST` | `/budgets` | Create Budget | - | - | BudgetRequest | - | 登录用户；部分写操作按 RBAC 校验 |
| `PUT` | `/budgets/{budget_id}` | Update Budget | budget_id* | - | object | - | 登录用户；部分写操作按 RBAC 校验 |
| `POST` | `/budgets/{budget_id}/evaluate` | Evaluate Budget | budget_id* | - | object | - | 登录用户；部分写操作按 RBAC 校验 |
| `GET` | `/diagnosis-decision-trees` | Diagnosis Decision Trees | - | page, pageSize, module, status | - | - | 登录用户；部分写操作按 RBAC 校验 |
| `POST` | `/diagnosis-decision-trees` | Create Diagnosis Decision Tree | - | - | object | - | 登录用户；部分写操作按 RBAC 校验 |
| `PUT` | `/diagnosis-decision-trees/{tree_id}` | Update Diagnosis Decision Tree | tree_id* | - | object | - | 登录用户；部分写操作按 RBAC 校验 |
| `GET` | `/diagnosis-kb` | Diagnosis Kb | - | page, pageSize, module, errorCode, keyword | - | - | 登录用户；部分写操作按 RBAC 校验 |
| `POST` | `/diagnosis-kb` | Create Diagnosis Kb | - | - | object | - | 登录用户；部分写操作按 RBAC 校验 |
| `POST` | `/diagnosis-kb/from-diagnosis/{diagnosis_id}` | Diagnosis Kb From Ticket | diagnosis_id* | - | - | - | 登录用户；部分写操作按 RBAC 校验 |
| `DELETE` | `/diagnosis-kb/{entry_id}` | Delete Diagnosis Kb | entry_id* | - | - | - | 登录用户；部分写操作按 RBAC 校验 |
| `PUT` | `/diagnosis-kb/{entry_id}` | Update Diagnosis Kb | entry_id* | - | object | - | 登录用户；部分写操作按 RBAC 校验 |
| `GET` | `/notifications` | Notifications | - | page, pageSize, status, type | - | - | 登录用户；部分写操作按 RBAC 校验 |
| `POST` | `/notifications/scan-seat-expirations` | Scan Seat Expirations | - | - | - | - | 登录用户；部分写操作按 RBAC 校验 |
| `GET` | `/notifications/summary` | Notification Summary | - | - | - | - | 登录用户；部分写操作按 RBAC 校验 |
| `POST` | `/notifications/{notification_id}/read` | Read Notification | notification_id* | - | - | - | 登录用户；部分写操作按 RBAC 校验 |
| `GET` | `/permission-matrix` | Permission Matrix | - | - | - | - | 登录用户；部分写操作按 RBAC 校验 |
| `GET` | `/permissions` | Permissions | - | - | - | - | 登录用户；部分写操作按 RBAC 校验 |
| `GET` | `/resource-packages` | List Resource Packages | - | targetType, targetId, status, page, pageSize | - | - | 登录用户；部分写操作按 RBAC 校验 |
| `POST` | `/resource-packages` | Create Resource Package | - | - | ResourcePackageRequest | - | 登录用户；部分写操作按 RBAC 校验 |
| `PUT` | `/resource-packages/{package_id}` | Update Resource Package | package_id* | - | object | - | 登录用户；部分写操作按 RBAC 校验 |
| `GET` | `/sync-jobs` | Runtime Sync Jobs | - | page, pageSize, status | - | - | 登录用户；部分写操作按 RBAC 校验 |
| `POST` | `/sync-jobs` | Create Runtime Sync Job | - | - | object | - | 登录用户；部分写操作按 RBAC 校验 |
| `GET` | `/sync-jobs/{job_id}` | Runtime Sync Job Detail | job_id* | - | - | - | 登录用户；部分写操作按 RBAC 校验 |

## 6. 前端重点约定

- `/dev/*` 仅用于本地测试数据构造，生产页面不要调用。
- 模型密钥、SSO 密钥、Claw Proxy token、Bridge token 不会下发前端；页面只展示掩码或引用。
- 高危操作如批量删除、审计导出、模型密钥变更、安全策略停用会返回 `pending_approval` 或 `409002`，前端应进入审批流程。
- 审计导出、模型调用日志导出会冻结审批单中的查询条件；审批通过后再次调用导出接口时，以审批快照为准，不以前端当前 query 为准。
- 导出任务返回 `taskId/status/downloadUrl/watermark`；下载 `/exports/{export_key}/download` 会记录敏感下载事件和操作审计。
- 告警列表支持 `level/status/sourceType/departmentId/startTime/endTime`；诊断列表支持 `level/objectType`。
- 成本接口支持 `startDate/endDate/departmentId/projectId/period`，`period` 可用于日、周、月、季度聚合；导出接口同样返回 `report`。
- 通道配置支持 `userRateLimitPerMinute/qpsLimit/dailyMessageLimit`，触发限流时返回 `422001` 并写入失败消息日志和通道审计。
- 记忆列表 `/memories` 返回分页对象，支持 `scope/keyword/page/pageSize`；不要按旧版数组结构解析。
- 诊断修复 `/diagnostics/{diagnosis_id}/fix` 返回 `fixTaskId` 和 `selfHealTaskId`，前端可跳转修复任务或自愈任务详情。
- 普通用户没有管理后台权限时会返回 `403001`，前端需要根据 `/me/permissions` 控制菜单和按钮可见性。
- Agent、Skill、知识库、Cron、备份等前端只传业务 ID，不需要也不应传 `instanceId`、`packageName` 或完整密钥。
- 诊断知识库接口返回 `symptom`、`reason`、`solution`、`verificationMethod`，前端可按错误码和模块展示故障现象、原因、方案和验证方式。

## 7. 关键接口字段说明

### 7.1 Agent 创建与详情

- 创建：`POST /agents`，必填 `name/departmentId/ownerId/primaryModelId`；可选 `skillIds/knowledgeBaseIds/messageChannelIds/resourceSpec/memoryPolicy`。
- 详情：`GET /agents/{agent_id}` 返回运行时、绑定 Skill、绑定知识库、版本、审计日志等聚合信息。
- 创建时选择 Skill 只能传已审核启用的 `skillId`；未审核或禁用 Skill 会返回 `400001`，`data.reason=skill_not_enabled`。
- 创建时选择 `messageChannelIds` 只能传启用状态的渠道；创建成功后会自动建立 Agent 与渠道绑定。
- 归档：`POST /agents/{agent_id}/archive`；删除：`DELETE /agents/{agent_id}`。两者返回的 `data.releasedResources` 会包含资源释放结果：
  - `reclaimedSeats`：已回收的 Agent 席位。
  - `disabledChannelBindings`：已停用的消息渠道绑定。
  - `disabledBusinessSystemGrants`：已停用的业务系统授权。
  - `revokedShareGrants`：已撤销的共享授权。

### 7.2 Skill 管理

- 导入：`POST /skills` 或 `POST /skills/import`，请求体常用字段为 `name/packageName/packageUrl/source/version/category/allowedRoles`。
- 审核：`POST /skills/{skill_id}/review`，请求体 `{"decision":"approved","comment":"..."}`；审核通过后 `status=enabled`。
- 授权：`POST /skills/{skill_id}/grants`，`scopeType` 支持 `role/department/project/agent`，前端用它控制可安装范围。
- 运行时安装：`POST /agents/{agent_id}/skills/{skill_id}/install`；卸载同一路径的 `/uninstall`。
- 环境变量：`GET/PUT/DELETE /agents/{agent_id}/skill-env-vars`；写入时传明文，查询只返回 `valueMasked/secretRef`，不会返回原值。

### 7.3 知识库与文件

- 知识库列表：`GET /knowledge-bases` 按当前登录用户数据权限过滤。
- 上传文件：`POST /knowledge-bases/{kb_id}/files`，请求体常用字段 `filename/fileType/sizeBytes/contentPreview`。
- 文件类型仅支持 `pdf/docx/txt/xlsx/pptx/md`；大小上限 50MB；病毒模拟命中或内容含敏感标记会返回 `400001`。
- 删除文件：`DELETE /knowledge-files/{file_id}`；如果已被智能体绑定引用，会返回 `409001` 并在 `data.references` 中给出引用关系。
- 重建索引：`POST /knowledge-files/{file_id}/reindex`，前端根据返回的解析任务状态刷新文件列表。

### 7.4 模型、调用日志与成本

- 模型列表/详情返回 `applicableScenarios/errorRate/apiKeyMasked/secretRef`；前端只展示掩码，不展示完整密钥。
- 模型调用日志：`GET /model-call-logs` 和 `GET /audit/model-call-logs` 支持 `projectId` 过滤，返回项包含 `projectId/inputSummary/outputSummary/tokens/cost/status`。
- 成本接口：`GET /cost/by-*` 和 `GET /cost/export` 都支持 `departmentId/projectId/period/startDate/endDate`；`/cost/by-project` 用于项目维度展示。

### 7.5 告警、诊断与巡检

- 告警列表/详情返回 `alertNo/sourceObject/impactScope/triggeredAt`，可直接用于告警编号、影响范围和触发时间展示。
- 诊断修复：`POST /diagnostics/{diagnosis_id}/fix` 返回 `fixTaskId/selfHealTaskId/updatedInspectionItemCount`；如果修复关联巡检失败项，后端会同步闭环巡检状态。
- 诊断知识库：`GET /diagnosis-kb` 支持 `module/errorCode/keyword`，返回故障现象、原因、解决方案和验证方式。

## 8. 常用请求体 Schema

以下为 OpenAPI 中定义的请求体 schema。复杂对象以 Swagger 页面为准，本文档列出字段名便于前端快速定位。

| Schema | 字段 | 必填字段 |
| --- | --- | --- |
| `AgentCreateRequest` | name, type, departmentId, ownerId, description, resourceSpec, primaryModelId, backupModelId, concurrencyLimit, dailyCallLimit, timeoutMs, skillIds, knowledgeBaseIds, memoryPolicy, messageChannelIds | name, departmentId, ownerId, primaryModelId |
| `BudgetRequest` | name, scopeType, scopeId, period, limitAmount, thresholdRatio, ownerId, status | name, scopeType, scopeId, limitAmount |
| `CostRuleRequest` | name, ruleType, scopeType, scopeId, threshold, level, status, config | name, ruleType |
| `HTTPValidationError` | detail | - |
| `LoginRequest` | username, password | username, password |
| `ResourcePackageRequest` | name, packageType, targetType, targetId, cpu, memoryGb, gpu, storageGb, fixedDailyCost, status | name |
| `ValidationError` | loc, msg, type | loc, msg, type |
