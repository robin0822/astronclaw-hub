# AstronClaw 前端接口文档

## 1. 公共约定

Base URL：

```text
/api/v1/astron-claw
```

认证：

```http
Authorization: Bearer <user_access_token>
Content-Type: application/json
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

分页结构：

```json
{
  "items": [],
  "page": 1,
  "pageSize": 20,
  "total": 0
}
```

前端注意：

1. 前端只调用本业务后端，不调用 Claw Proxy `/api/v1/bot`。
2. 前端不接收完整 `CLAW_PROXY_AUTH_TOKEN`、模型 `apiKey`、租户 `api_secret`。
3. 密钥类字段仅展示掩码或引用 ID。

## 2. 登录与当前用户

一期先提供账号密码登录。后续私有化部署接入客户统一登录系统时，前端仍只接收业务后端 token；登录入口可替换为跳转 SSO 或网关免登录，但业务 API 认证方式不变。

### 2.1 账号密码登录

```http
POST /auth/login
```

请求：

```json
{
  "username": "admin",
  "password": "Admin@123456"
}
```

响应：

```json
{
  "accessToken": "eyJxxx",
  "tokenType": "Bearer",
  "expiresIn": 7200,
  "refreshToken": "rt_xxx",
  "user": {
    "id": "u001",
    "username": "admin",
    "name": "系统管理员",
    "department": { "id": "dep001", "name": "总部" },
    "status": "active"
  },
  "roles": ["super_admin"],
  "permissions": ["agent:view", "agent:create", "agent:deploy"],
  "dataScope": {
    "type": "all",
    "departmentIds": []
  }
}
```

失败响应：

| code | message | 场景 |
| --- | --- | --- |
| `401001` | unauthorized | 用户名或密码错误 |
| `401002` | account locked | 登录失败次数过多，账号临时锁定 |
| `401003` | account disabled | 账号停用、冻结或离职 |
| `401004` | password expired | 密码过期，需要修改密码 |

### 2.2 刷新 Token

```http
POST /auth/refresh
```

请求：

```json
{
  "refreshToken": "rt_xxx"
}
```

响应结构同登录接口，可返回新的 `accessToken` 和 `refreshToken`。如果一期不启用 refresh token，可省略该接口，由前端在 `401001` 后回到登录页。

### 2.3 退出登录

```http
POST /auth/logout
```

退出后当前 token 或 session 失效，并写登录日志。

### 2.4 当前用户

```http
GET /me
GET /me/permissions
```

`GET /me/permissions` 返回当前用户角色、权限码和数据范围，用于前端菜单、按钮和页面访问控制。

### 2.5 私有化 SSO 预留

后续接入客户登录系统时，可新增以下入口，具体协议按客户环境确认：

```http
GET /auth/sso/login?provider=customer
GET /auth/sso/callback?provider=customer
POST /auth/sso/logout
```

SSO 成功后仍由业务后端返回或写入自己的 access token，前端后续调用 `/api/v1/astron-claw` 不直接使用客户身份系统的 token。

## 3. 智能体管理

### 3.1 查询智能体列表

```http
GET /agents?keyword=&status=&departmentId=&ownerId=&modelId=&page=1&pageSize=20
```

响应：

```json
{
  "items": [
    {
      "id": "agt_db_001",
      "botId": "agt_1a2b3c4d5e6f",
      "instanceId": "sandbox-session-id",
      "name": "寿险业务助手",
      "type": "astronclaw",
      "status": "running",
      "version": "1.0.0",
      "department": { "id": "dep001", "name": "运营部" },
      "owner": { "id": "u001", "name": "张三" },
      "containerCount": 1,
      "skillCount": 3,
      "knowledgeBaseCount": 2,
      "primaryModel": { "id": "m001", "name": "xminimaxm26" },
      "backupModel": { "id": "m002", "name": "backup-model" },
      "cpu": 2,
      "memory": "4Gi",
      "storage": "20Gi",
      "gpu": 0,
      "concurrencyLimit": 20,
      "dailyCallLimit": 10000,
      "timeoutMs": 300000,
      "currentUsers": 12,
      "maxUsers": 100,
      "qps": 3.2,
      "createdAt": "2026-07-01T10:00:00+08:00",
      "updatedAt": "2026-07-01T11:00:00+08:00"
    }
  ],
  "page": 1,
  "pageSize": 20,
  "total": 1
}
```

### 3.2 创建智能体

```http
POST /agents
```

请求：

```json
{
  "name": "寿险业务助手",
  "type": "astronclaw",
  "departmentId": "dep001",
  "ownerId": "u001",
  "description": "用于寿险业务问答",
  "resourceSpec": {
    "cpu": 2,
    "memory": "4Gi",
    "storage": "20Gi",
    "gpu": 0
  },
  "primaryModelId": "m001",
  "backupModelId": "m002",
  "concurrencyLimit": 20,
  "dailyCallLimit": 10000,
  "timeoutMs": 300000,
  "skillIds": ["sk001", "sk002"],
  "knowledgeBaseIds": ["kb001"],
  "memoryPolicy": "personal",
  "messageChannelIds": []
}
```

响应：

```json
{
  "id": "agt_db_001",
  "botId": "agt_1a2b3c4d5e6f",
  "status": "deploying",
  "deployTaskId": "task_001"
}
```

### 3.3 查询智能体详情

```http
GET /agents/{agentId}
```

响应包括 `basic`、`runtime`、`skills`、`knowledgeBases`、`deployHistory`、`versionHistory`、`callStats`、`alerts`、`auditLogs`。

### 3.4 生命周期操作

```http
POST /agents/{agentId}/deploy
POST /agents/{agentId}/start
POST /agents/{agentId}/stop
POST /agents/{agentId}/restart
POST /agents/{agentId}/upgrade
POST /agents/{agentId}/archive
DELETE /agents/{agentId}
```

通用响应：

```json
{
  "taskId": "task_001",
  "status": "queued"
}
```

### 3.5 切换模型

```http
PUT /agents/{agentId}/model
```

请求：

```json
{
  "primaryModelId": "m003",
  "backupModelId": "m002"
}
```

### 3.6 查询部署任务

```http
GET /agent-tasks/{taskId}
```

响应：

```json
{
  "id": "task_001",
  "agentId": "agt_db_001",
  "action": "deploy",
  "status": "running",
  "phase": "install_skill",
  "progress": 60,
  "node": "worker-01",
  "startedAt": "2026-07-01T10:00:00+08:00",
  "endedAt": null,
  "errorCode": null,
  "errorMessage": null,
  "retryAdvice": null
}
```

## 4. 批量任务

### 4.1 创建批量任务

```http
POST /batch-tasks
```

请求：

```json
{
  "type": "restart",
  "scopeType": "selected",
  "targetIds": ["agt_db_001", "agt_db_002"],
  "strategy": {
    "batchSize": 10,
    "pauseOnFailure": false,
    "grayPercent": null
  },
  "reason": "例行维护"
}
```

`type` 可选：`deploy`、`start`、`stop`、`restart`、`upgrade`、`delete`、`archive`、`switch_model`、`sync_skill`。

### 4.2 查询批量任务

```http
GET /batch-tasks/{batchTaskId}
```

响应：

```json
{
  "id": "bat_001",
  "type": "restart",
  "status": "running",
  "total": 100,
  "successCount": 80,
  "failedCount": 2,
  "skippedCount": 0,
  "progress": 82,
  "operator": { "id": "u001", "name": "张三" },
  "approvalId": null,
  "createdAt": "2026-07-01T10:00:00+08:00"
}
```

### 4.3 查询批量明细

```http
GET /batch-tasks/{batchTaskId}/items?page=1&pageSize=50
```

### 4.4 导出批量结果

```http
GET /batch-tasks/{batchTaskId}/export
```

返回文件下载地址或直接文件流。

## 5. 组织权限

### 5.1 组织树

```http
GET /org/departments/tree
```

### 5.2 用户列表

```http
GET /org/users?keyword=&departmentId=&status=&seatStatus=&page=1&pageSize=20
```

### 5.3 角色与权限

```http
GET /roles
POST /roles
PUT /roles/{roleId}
DELETE /roles/{roleId}
GET /permissions
PUT /roles/{roleId}/permissions
```

### 5.4 当前用户权限

```http
GET /me/permissions
```

响应：

```json
{
  "user": { "id": "u001", "name": "张三" },
  "roles": ["platform_admin"],
  "permissions": ["agent:view", "agent:create", "agent:deploy"],
  "dataScope": {
    "type": "department_and_children",
    "departmentIds": ["dep001", "dep002"]
  }
}
```

## 6. Skill 管理

```http
GET /skills?keyword=&status=&source=&category=&page=1&pageSize=20
POST /skills
POST /skills/import
GET /skills/{skillId}
PUT /skills/{skillId}
POST /skills/{skillId}/review
POST /agents/{agentId}/skills/{skillId}/install
POST /agents/{agentId}/skills/{skillId}/uninstall
```

Skill 响应字段：

```json
{
  "id": "sk001",
  "name": "图片生成",
  "packageName": "image_create",
  "packageUrl": "https://example.com/skill.zip",
  "source": "custom",
  "version": "1.0.0",
  "status": "enabled",
  "category": "media",
  "creator": { "id": "u001", "name": "张三" },
  "updatedAt": "2026-07-01T10:00:00+08:00",
  "boundAgentCount": 3,
  "allowedRoles": ["platform_admin"],
  "securityReviewStatus": "approved"
}
```

## 7. 知识库与记忆

```http
GET /knowledge-bases
POST /knowledge-bases
GET /knowledge-bases/{knowledgeBaseId}/files
POST /knowledge-bases/{knowledgeBaseId}/files
DELETE /knowledge-files/{fileId}
POST /knowledge-files/{fileId}/reindex
POST /agents/{agentId}/knowledge-bases/{knowledgeBaseId}/bind
DELETE /agents/{agentId}/knowledge-bases/{knowledgeBaseId}/bind
```

记忆接口：

```http
GET /memories?scope=&keyword=&page=1&pageSize=20
POST /memories
PUT /memories/{memoryId}
DELETE /memories/{memoryId}
POST /memories/{memoryId}/share
GET /agents/{agentId}/plugins/astronmem
POST /agents/{agentId}/plugins/astronmem
```

开启或关闭 AstronMem：

```json
{
  "action": "enable"
}
```

## 8. 模型网关

```http
GET /models?keyword=&status=&provider=&type=&page=1&pageSize=20
POST /models
PUT /models/{modelId}
POST /models/{modelId}/enable
POST /models/{modelId}/disable
POST /models/{modelId}/probe
GET /model-call-logs?modelId=&agentId=&userId=&departmentId=&status=&startTime=&endTime=
```

新增模型请求：

```json
{
  "name": "xminimaxm26",
  "provider": "maas",
  "modelKey": "xminimaxm26",
  "type": "chat",
  "baseUrl": "https://maas-api.example.com/v2",
  "authType": "api_key",
  "apiKey": "api_key:api_secret",
  "unitPrice": 0.01,
  "contextLength": 32768,
  "defaultTimeoutMs": 300000
}
```

查询模型时 `apiKey` 只返回掩码：

```json
{
  "secretRef": "sec_001",
  "apiKeyMasked": "api_***_secret"
}
```

## 9. 监控告警

### 9.1 全域看板

```http
GET /monitor/overview?departmentId=&projectId=&modelId=&agentType=
```

响应：

```json
{
  "runningAgentCount": 120,
  "abnormalAgentCount": 3,
  "availableModelCount": 8,
  "abnormalModelCount": 1,
  "pendingAlertCount": 5,
  "todayCallCount": 23000,
  "avgLatencyMs": 850,
  "resourceUsageRate": 0.72
}
```

### 9.2 告警

```http
GET /alerts?level=&status=&sourceType=&departmentId=&startTime=&endTime=&page=1&pageSize=20
GET /alerts/{alertId}
POST /alerts/{alertId}/claim
POST /alerts/{alertId}/process
POST /alerts/{alertId}/transfer
POST /alerts/{alertId}/suspend
POST /alerts/{alertId}/close
```

闭环请求：

```json
{
  "resolution": "已重启实例并验证恢复",
  "relatedOperationId": "task_001"
}
```

## 10. 问题诊断与运维

```http
GET /diagnostics?level=&objectType=&page=1&pageSize=20
GET /diagnostics/{diagnosisId}
POST /diagnostics/{diagnosisId}/fix
GET /inspection-tasks
POST /inspection-tasks
POST /inspection-tasks/{taskId}/run
GET /inspection-runs/{runId}
GET /inspection-runs/{runId}/export
```

一键修复响应：

```json
{
  "fixTaskId": "fix_001",
  "status": "running"
}
```

## 11. 成本核算

```http
GET /cost/overview?startDate=&endDate=&departmentId=&projectId=
GET /cost/by-department?startDate=&endDate=
GET /cost/by-project?startDate=&endDate=
GET /cost/by-model?startDate=&endDate=
GET /cost/by-agent?startDate=&endDate=
GET /cost/export?dimension=&startDate=&endDate=
```

成本字段：

```json
{
  "dimensionId": "dep001",
  "dimensionName": "运营部",
  "callCount": 10000,
  "tokens": 2300000,
  "modelCost": 230.5,
  "containerCost": 120.0,
  "seatCost": 80.0,
  "totalCost": 430.5
}
```

## 12. 审计

```http
GET /audit/operation-logs?module=&actorId=&action=&startTime=&endTime=&page=1&pageSize=20
GET /audit/login-logs?userId=&status=&startTime=&endTime=&page=1&pageSize=20
GET /audit/model-call-logs?modelId=&agentId=&userId=&startTime=&endTime=&page=1&pageSize=20
GET /audit/export
```

审计日志字段：

```json
{
  "id": "aud_001",
  "actor": { "id": "u001", "name": "张三" },
  "module": "agent",
  "action": "restart",
  "objectType": "agent",
  "objectId": "agt_db_001",
  "ip": "10.0.0.1",
  "result": "success",
  "errorMessage": null,
  "createdAt": "2026-07-01T10:00:00+08:00"
}
```

## 13. 常见错误码

| code | message | 前端建议 |
| --- | --- | --- |
| `0` | success | 正常处理 |
| `400001` | invalid request | 展示表单错误 |
| `401001` | unauthorized | 跳转登录 |
| `403001` | forbidden | 展示无权限 |
| `409001` | invalid state | 刷新数据后重试 |
| `409002` | approval required | 引导提交审批 |
| `422001` | quota exceeded | 展示资源或席位不足 |
| `502001` | claw proxy timeout | 提示沙箱服务超时 |
| `502002` | sandbox session expired | 提示重新部署 |
| `502003` | bot deploy failed | 展示失败阶段和建议 |

## 14. 补充接口：实例运行与日志

### 14.1 手动同步实例状态

```http
POST /agents/{agentId}/sync
```

响应：

```json
{
  "status": "running",
  "lastSyncAt": "2026-07-02T09:00:00+08:00",
  "syncError": null
}
```

### 14.2 查询实例日志

```http
GET /agents/{agentId}/logs?logType=runtime&keyword=&startTime=&endTime=&page=1&pageSize=50
```

`logType` 可选：`runtime`、`deploy`、`upgrade`、`container`、`model_call`。

### 14.3 更新远程运行参数

```http
PUT /agents/{agentId}/runtime-config
```

请求：

```json
{
  "concurrencyLimit": 20,
  "dailyCallLimit": 10000,
  "timeoutMs": 300000,
  "resourceSpec": {
    "cpu": 2,
    "memory": "4Gi",
    "storage": "20Gi",
    "gpu": 0
  },
  "primaryModelId": "m001",
  "backupModelId": "m002"
}
```

## 15. 补充接口：Claw Proxy 代理能力

### 15.1 运行时 Skill

```http
GET /agents/{agentId}/runtime-skills
```

用于查询沙箱实际安装的 Skill，并与平台绑定记录比对。

### 15.2 Skill 环境变量

```http
GET /agents/{agentId}/skill-env-vars
PUT /agents/{agentId}/skill-env-vars
DELETE /agents/{agentId}/skill-env-vars
```

新增/更新请求：

```json
{
  "skillId": "sk001",
  "env": {
    "XFYUN_APP_ID": "app_id",
    "XFYUN_API_KEY": "api_key",
    "XFYUN_API_SECRET": "api_secret"
  },
  "restartAfterUpdated": true
}
```

查询响应只返回掩码：

```json
{
  "items": [
    {
      "skillId": "sk001",
      "envName": "XFYUN_API_KEY",
      "maskedValue": "api_***_key",
      "updatedAt": "2026-07-02T09:00:00+08:00"
    }
  ]
}
```

### 15.3 沙箱文件

```http
GET /agents/{agentId}/dev-files?path=/root/.openclaw&page=1&pageSize=20
GET /agents/{agentId}/dev-files/search?keyword=demo&path=/root/.openclaw
GET /agents/{agentId}/dev-file/meta?path=/root/.openclaw/demo.md
GET /agents/{agentId}/dev-file/content?path=/root/.openclaw/demo.md
PUT /agents/{agentId}/dev-file/content
GET /agents/{agentId}/dev-file/download?path=/root/.openclaw/demo.md
```

保存文件请求：

```json
{
  "path": "/root/.openclaw/demo.md",
  "content": "# updated\n",
  "etag": "b1946ac92492d2347c6235b4d2611184"
}
```

### 15.4 记忆预览与插件

```http
GET /agents/{agentId}/memory-preview
GET /agents/{agentId}/plugins/astronmem
POST /agents/{agentId}/plugins/astronmem
```

开关请求：

```json
{
  "action": "enable"
}
```

### 15.5 定时任务

```http
POST /agents/{agentId}/crons
GET /agents/{agentId}/crons
PUT /agents/{agentId}/crons/{cronId}
DELETE /agents/{agentId}/crons/{cronId}
GET /agents/{agentId}/crons/{cronId}/runs?limit=100
```

创建请求：

```json
{
  "name": "每日晨报",
  "expression": "0 8 * * *",
  "type": "cron",
  "task": "推送今日晨报",
  "timeZone": "Asia/Shanghai",
  "channel": "openclaw-weixin"
}
```

`cronId` 由后端生成并返回。

### 15.6 Agent Team 查询

```http
GET /agents/{agentId}/teams?sessionId=session_xxx
GET /agents/{agentId}/teams/{teamId}/progress?sessionId=session_xxx
GET /agents/{agentId}/teams/{teamId}/outputs?sessionId=session_xxx
GET /agents/{agentId}/teams/{teamId}/result?sessionId=session_xxx
```

前端传 `sessionId`，后端负责拼接 `session_key=agent:main:main:{sessionId}`。

### 15.7 备份恢复

```http
POST /agents/{agentId}/backups
GET /agents/{agentId}/backups/{taskId}
POST /agents/{agentId}/backup-restore
GET /agents/{agentId}/backup-restore/{taskId}
DELETE /agents/{agentId}/backups
```

开始备份响应：

```json
{
  "taskId": "bkt_001",
  "proxyTaskId": "backup_task_xxx",
  "status": "running"
}
```

## 16. 补充接口：审批、共享、席位

### 16.1 审批

```http
POST /approvals
GET /approvals?status=&type=&page=1&pageSize=20
GET /approvals/{approvalId}
POST /approvals/{approvalId}/approve
POST /approvals/{approvalId}/reject
```

创建审批请求：

```json
{
  "type": "batch_delete_agent",
  "riskLevel": "high",
  "reason": "试点结束清理",
  "payload": {
    "agentIds": ["agt_db_001"]
  }
}
```

### 16.2 实例共享

```http
POST /agents/{agentId}/share-grants
GET /agents/{agentId}/share-grants
DELETE /agents/{agentId}/share-grants/{grantId}
```

请求：

```json
{
  "scopeType": "department",
  "scopeId": "dep001",
  "permission": "use",
  "expiresAt": "2026-12-31T23:59:59+08:00",
  "reason": "部门试用"
}
```

### 16.3 席位

```http
GET /seat-packages
POST /seat-packages
GET /seat-assignments?departmentId=&userId=&agentId=
POST /seat-assignments
DELETE /seat-assignments/{assignmentId}
POST /seat-assignments/{assignmentId}/transfer
```

席位不足错误示例：

```json
{
  "code": 422001,
  "message": "quota exceeded",
  "data": {
    "required": 10,
    "available": 3,
    "seatPackageId": "seat_pkg_001"
  },
  "requestId": "req_xxx"
}
```

## 17. 补充接口：模型流控、渠道和诊断知识库

### 17.1 模型限额与路由

```http
GET /model-quotas
POST /model-quotas
PUT /model-quotas/{quotaId}
DELETE /model-quotas/{quotaId}
GET /model-route-policies
POST /model-route-policies
PUT /model-route-policies/{policyId}
DELETE /model-route-policies/{policyId}
GET /model-policy-hits?startTime=&endTime=&modelId=
```

### 17.2 消息渠道与业务系统

```http
GET /channels
POST /channels
PUT /channels/{channelId}
POST /channels/{channelId}/test
POST /channels/{channelId}/reconnect
POST /channels/{channelId}/disable
GET /business-systems
POST /business-systems
PUT /business-systems/{systemId}/agents
GET /channel-audit-logs
```

消息渠道完整管理可按项目范围延后，但通知、告警推送和业务系统嵌入需要预留接口。

### 17.3 诊断知识库

```http
GET /diagnosis-kb?module=&errorCode=&keyword=&page=1&pageSize=20
POST /diagnosis-kb
PUT /diagnosis-kb/{entryId}
DELETE /diagnosis-kb/{entryId}
POST /diagnosis-kb/from-diagnosis/{diagnosisId}
GET /diagnosis-decision-trees
POST /diagnosis-decision-trees
PUT /diagnosis-decision-trees/{treeId}
```
