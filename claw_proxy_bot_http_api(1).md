# Claw Proxy Bot 沙箱 HTTP 接口文档

本文面向需要直接对接 Claw Proxy 的业务系统。所有接口均以
`CLAW_PROXY_BASE_URL` 为 Base URL，路径统一以 `/api/v1/bot` 开头。

本文只覆盖 Claw Proxy / 沙箱 HTTP 层，不覆盖本项目业务后端
`/api/v1/astron-claw`，也不覆盖 Bridge Server 的对话、会话、媒体接口。
如果新系统需要聊天能力，`deploy` 时仍需要把自己的 `bridgeToken` 作为不透明字符串传给沙箱。

## 1. 公共约定

### 1.1 Base URL

```text
{CLAW_PROXY_BASE_URL}/api/v1/bot...
```

示例：

```text
https://claw-proxy.example.com/api/v1/bot/deploy
```

### 1.2 pre 环境配置

当前工作区未发现单独的 `pre.env` 文件；项目根目录 `.env` 中配置的是 pre 环境 Claw Proxy：

```dotenv
CLAW_PROXY_BASE_URL=https://astronclaw-api-pre.xf-yun.com/astronclaw-proxy
CLAW_PROXY_AUTH_TOKEN=ak-ba7d...a940
```

完整 API 前缀：

```text
https://astronclaw-api-pre.xf-yun.com/astronclaw-proxy/api/v1/bot
```

说明：

| 配置项 | pre 环境值 | 说明 |
| --- | --- | --- |
| `CLAW_PROXY_BASE_URL` | `https://astronclaw-api-pre.xf-yun.com/astronclaw-proxy` | Claw Proxy 服务根地址 |
| `CLAW_PROXY_AUTH_TOKEN` | `ak-ba7d...a940` | 服务间共享密钥，文档中只脱敏展示 |
| `TEAM_API_BASE_URL` | 未单独配置 | Team API client 会回退使用 `CLAW_PROXY_BASE_URL` |

请求头示例：

```http
Authorization: Bearer ak-ba7d...a940
Content-Type: application/json
```

完整密钥仅应放在后端环境变量或密钥管理系统中，不建议写进可传播文档，也不要下发给前端、浏览器或移动端。

### 1.3 认证

所有接口统一使用 Bearer Token：

```http
Authorization: Bearer <CLAW_PROXY_AUTH_TOKEN>
Content-Type: application/json
```

`CLAW_PROXY_AUTH_TOKEN` 不是本业务后端生成的用户 token，也不是 JWT。当前项目只从环境变量读取它，并作为服务间共享密钥透传给 Claw Proxy；校验逻辑在 Claw Proxy 服务侧，不在本仓库。

对接方需要从 Claw Proxy 服务提供方或部署配置中拿到这个密钥，并只放在服务端配置里，例如：

```dotenv
CLAW_PROXY_BASE_URL=https://claw-proxy.example.com
CLAW_PROXY_AUTH_TOKEN=ak_xxx
```

客户端代码拼 header 时可兼容两种配置方式：

| 配置值 | 最终请求头 |
| --- | --- |
| `ak_xxx` | `Authorization: Bearer ak_xxx` |
| `Bearer ak_xxx` | `Authorization: Bearer ak_xxx` |

如果是新系统自建一套 Claw Proxy，可以由部署侧生成一个高强度随机密钥，分别配置到 Claw Proxy 服务端和调用方后端。不要把该 token 下发到浏览器或移动端。

### 1.4 响应格式

成功响应以 `code == 0` 为准，业务数据放在 `data`。

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

失败响应示例：

```json
{
  "code": 400003,
  "message": "Sandbox session has expired",
  "data": null
}
```

当前项目的错误处理约定：

| 错误 | 建议处理 |
| --- | --- |
| HTTP `400` / `404` | 视为沙箱实例不可用或会话失效 |
| 业务码 `400003` | 视为沙箱会话失效，需要重新部署 |
| 业务码 `300003` | Bot 部署失败 |
| 其他非 0 `code` | 按具体操作提示失败 |
| 网络错误 / 超时 | 视为 Claw Proxy 不可用 |

### 1.5 核心 ID

| 字段 | 来源 | 用途 |
| --- | --- | --- |
| `botId` | 调用方业务系统生成 | 部署时写入 OpenClaw 配置，便于追踪 |
| `instanceId` | `POST /api/v1/bot/deploy` 返回 | 后续所有实例级接口的路径参数 |

本项目生成 `botId` 的规则是 `generate_id("agt")`：使用 `uuid4().hex[:12]` 取 12 位随机十六进制串，再加 `agt_` 前缀，例如 `agt_1a2b3c4d5e6f`。调用方也可以使用自己的业务主键或同等唯一 ID，只要能稳定保存 `botId -> instanceId` 映射即可。

## 2. 接口总表

| 能力 | Method | Path |
| --- | --- | --- |
| 部署实例 | `POST` | `/api/v1/bot/deploy` |
| 重启实例 | `POST` | `/api/v1/bot/{instanceId}/restart` |
| 停止实例 | `POST` | `/api/v1/bot/{instanceId}/stop` |
| 切换模型 | `PUT` | `/api/v1/bot/{instanceId}/model` |
| 升级实例 | `POST` | `/api/v1/bot/{instanceId}/upgrade` |
| 自动修复 | `POST` | `/api/v1/bot/{instanceId}/doctor/fix` |
| 安装 skill | `POST` | `/api/v1/bot/{instanceId}/skill/install` |
| 卸载 skill | `POST` | `/api/v1/bot/{instanceId}/skill/uninstall` |
| 查询 skill | `GET` | `/api/v1/bot/{instanceId}/skill/list` |
| 添加环境变量 | `POST` | `/api/v1/bot/{instanceId}/skill/add_env` |
| 删除环境变量 | `POST` | `/api/v1/bot/{instanceId}/skill/remove_env` |
| 文件列表 | `GET` | `/api/v1/bot/{instanceId}/dev/files` |
| 文件搜索 | `GET` | `/api/v1/bot/{instanceId}/dev/files/search` |
| 文件元信息 | `GET` | `/api/v1/bot/{instanceId}/dev/file/meta` |
| 读取文件 | `GET` | `/api/v1/bot/{instanceId}/dev/file/content` |
| 保存文件 | `PUT` | `/api/v1/bot/{instanceId}/dev/file/content` |
| 文件下载 URL | `GET` | `/api/v1/bot/{instanceId}/dev/file/download` |
| 记忆预览 | `GET` | `/api/v1/bot/memory/preview` |
| 插件开关状态 | `POST` | `/api/v1/bot/{instanceId}/plugin/enabled` |
| 开关 astronmem | `POST` | `/api/v1/bot/{instanceId}/plugin/astronmem` |
| 创建定时任务 | `POST` | `/api/v1/bot/{instanceId}/cron` |
| 查询定时任务 | `GET` | `/api/v1/bot/{instanceId}/crons` |
| 更新定时任务 | `PUT` | `/api/v1/bot/{instanceId}/cron` |
| 删除定时任务 | `DELETE` | `/api/v1/bot/{instanceId}/cron` |
| 查询运行历史 | `GET` | `/api/v1/bot/{instanceId}/cron/runs` |
| Team 列表 | `GET` | `/api/v1/bot/{instanceId}/team/list` |
| Team 进度 | `GET` | `/api/v1/bot/{instanceId}/team/{teamId}/progress` |
| Team 产物 | `GET` | `/api/v1/bot/{instanceId}/team/{teamId}/outputs` |
| Team 结果 | `GET` | `/api/v1/bot/{instanceId}/team/{teamId}/result` |
| 开始备份 | `POST` | `/api/v1/bot/{instanceId}/backup` |
| 备份状态 | `GET` | `/api/v1/bot/{instanceId}/backup/status` |
| 开始恢复 | `POST` | `/api/v1/bot/{instanceId}/backup/restore` |
| 恢复状态 | `GET` | `/api/v1/bot/{instanceId}/backup/restore/status` |
| 删除备份 | `DELETE` | `/api/v1/bot/{instanceId}/backup` |

## 3. 实例生命周期

### 3.1 部署实例

```http
POST /api/v1/bot/deploy
```

请求体：

```json
{
  "botId": "agt_1a2b3c4d5e6f",
  "bridgeToken": "sk-xxx",
  "modelsConfig": {
    "models": [
      {
        "provider": "maas",
        "model": "xminimaxm26",
        "baseUrl": "https://maas-api.example.com/v2",
        "apiKey": "api_key:api_secret"
      }
    ],
    "defaultModel": {
      "provider": "maas",
      "model": "xminimaxm26"
    }
  },
  "traceUid": "user_xxx",
  "astronmenApiKey": "api_key:api_secret"
}
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `botId` | string | 是 | 调用方业务 Bot ID；本项目格式如 `agt_1a2b3c4d5e6f` |
| `bridgeToken` | string | 是 | 对话 Bridge token；Claw Proxy 不负责创建 |
| `modelsConfig.models[]` | array | 是 | 可用模型列表 |
| `modelsConfig.models[].provider` | string | 是 | 模型供应商 |
| `modelsConfig.models[].model` | string | 是 | 模型 ID |
| `modelsConfig.models[].baseUrl` | string | 是 | 模型服务地址 |
| `modelsConfig.models[].apiKey` | string | 是 | 模型鉴权信息 |
| `modelsConfig.defaultModel` | object | 是 | 默认模型，包含 `provider` 和 `model` |
| `traceUid` | string | 否 | 链路追踪用户 ID |
| `astronmenApiKey` | string | 否 | 记忆服务鉴权，格式通常为 `api_key:api_secret` |

响应 `data`：

```json
{
  "instanceId": "sandbox-session-id"
}
```

注意：当前项目按“部署实例”和“安装 skill”分步处理。`deploy` 只要求完成 OpenClaw 配置与启动，不假设 skill 已安装。

### 3.2 重启实例

```http
POST /api/v1/bot/{instanceId}/restart
```

无请求体。成功返回 `code == 0`。

### 3.3 停止实例

```http
POST /api/v1/bot/{instanceId}/stop
```

无请求体。成功返回 `code == 0`。

调用方通常把 stop 用在清理流程里；如果实例已不存在，建议业务侧按幂等清理处理。

### 3.4 切换模型

```http
PUT /api/v1/bot/{instanceId}/model
```

请求体：

```json
{
  "provider": "maas",
  "modelId": "xminimaxm26",
  "baseUrl": "https://maas-api.example.com/v2",
  "apiKey": "api_key:api_secret"
}
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `provider` | string | 是 | 模型供应商 |
| `modelId` | string | 是 | 目标模型 ID，字段名是 `modelId` |
| `baseUrl` | string | 是 | 模型服务地址 |
| `apiKey` | string | 是 | 模型鉴权信息 |

成功返回 `code == 0`。底层应完成模型配置更新，并重启相关 gateway。

### 3.5 升级实例

```http
POST /api/v1/bot/{instanceId}/upgrade
```

无请求体。

响应 `data`：

```json
{
  "instanceId": "sandbox-session-id",
  "upgraded": true
}
```

`instanceId` 可能保持不变，也可能返回升级后的新实例 ID。调用方应以响应中的 `instanceId` 覆盖本地映射；如果响应未带该字段，则继续使用旧值。

### 3.6 自动修复

```http
POST /api/v1/bot/{instanceId}/doctor/fix
```

无请求体。该接口是异步/轮询式：首次调用触发修复，后续调用返回当前状态。

响应 `data`：

```json
{
  "status": "running",
  "output": "checking..."
}
```

`status` 常见值：

| 值 | 含义 |
| --- | --- |
| `running` | 修复中 |
| `completed` | 修复完成 |
| `failed` | 修复失败 |

## 4. Skill 与环境变量

### 4.1 安装 skill

```http
POST /api/v1/bot/{instanceId}/skill/install
```

请求体：

```json
{
  "packageUrl": "https://example.com/skills/image_create.zip",
  "packageName": "image_create"
}
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `packageUrl` | string | 是 | skill zip 包 URL |
| `packageName` | string | 否 | runtime 包名。为空时底层可从包内或 URL 推导 |

成功返回 `code == 0`。

### 4.2 卸载 skill

```http
POST /api/v1/bot/{instanceId}/skill/uninstall
```

请求体：

```json
{
  "packageName": "image_create"
}
```

`packageName` 是运行时包名，不是调用方数据库里的 skill 主键。

### 4.3 查询已安装 skill

```http
GET /api/v1/bot/{instanceId}/skill/list
```

响应 `data`：

```json
{
  "skills": [
    {
      "name": "image_create",
      "description": "Create images",
      "version": "1.0.0",
      "source": "openclaw-workspace"
    }
  ]
}
```

当前项目依赖字段：

| 字段 | 说明 |
| --- | --- |
| `name` | runtime 包名 |
| `description` | skill 描述 |
| `version` | skill 版本 |
| `source` | skill 来源；当前项目只展示 `openclaw-workspace` 来源 |

### 4.4 添加环境变量

```http
POST /api/v1/bot/{instanceId}/skill/add_env
```

请求体是扁平 JSON 对象：

```json
{
  "XFYUN_APP_ID": "app_id",
  "XFYUN_API_KEY": "api_key",
  "XFYUN_API_SECRET": "api_secret"
}
```

成功返回 `code == 0`。

### 4.5 删除环境变量

```http
POST /api/v1/bot/{instanceId}/skill/remove_env
```

请求体是变量名数组：

```json
[
  "XFYUN_APP_ID",
  "XFYUN_API_KEY",
  "XFYUN_API_SECRET"
]
```

成功返回 `code == 0`。

## 5. 开发文件接口

路径一般在 `/root/.openclaw` 下。当前业务侧常用：

| 目录 | 用途 |
| --- | --- |
| `/root/.openclaw/workspace` | 工作区文件、原生记忆文件 |
| `/root/.openclaw/teams` | Agent Team 产物 |

### 5.1 文件列表

```http
GET /api/v1/bot/{instanceId}/dev/files
```

查询参数：

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `path` | string | 否 | 目录路径，默认可按 `/root/.openclaw` 处理 |
| `page` | int | 否 | 页码，默认 1 |
| `pageSize` | int | 否 | 每页条数 |
| `excludeNames` | string / array | 否 | 排除名称；可重复传参 `excludeNames=.git&excludeNames=node_modules` |

响应 `data`：

```json
{
  "path": "/root/.openclaw",
  "items": [
    {
      "name": "demo.md",
      "fullName": "demo.md",
      "path": "/root/.openclaw/demo.md",
      "isDir": false,
      "size": 1024,
      "extension": ".md",
      "mimeType": "text/markdown",
      "updatedAt": "2026-04-07T10:00:00Z",
      "editable": true,
      "downloadable": true
    }
  ],
  "total": 1
}
```

### 5.2 文件搜索

```http
GET /api/v1/bot/{instanceId}/dev/files/search
```

查询参数：

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `keyword` | string | 是 | 文件名关键字 |
| `path` | string | 否 | 搜索根目录 |
| `limit` | int | 否 | 结果数上限，当前项目默认 50 |

响应 `data`：

```json
{
  "keyword": "demo",
  "items": [
    {
      "name": "demo.md",
      "fullName": "demo.md",
      "path": "/root/.openclaw/demo.md",
      "parentPath": "/root/.openclaw",
      "isDir": false,
      "size": 1024,
      "extension": ".md",
      "mimeType": "text/markdown",
      "updatedAt": "2026-04-07T10:00:00Z",
      "editable": true,
      "downloadable": true
    }
  ],
  "total": 1
}
```

### 5.3 文件元信息

```http
GET /api/v1/bot/{instanceId}/dev/file/meta
```

查询参数：

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `path` | string | 是 | 文件路径 |

响应 `data`：

```json
{
  "name": "demo.md",
  "fullName": "demo.md",
  "path": "/root/.openclaw/demo.md",
  "isDir": false,
  "size": 1024,
  "extension": ".md",
  "mimeType": "text/markdown",
  "updatedAt": "2026-04-07T10:00:00Z",
  "editable": true,
  "downloadable": true
}
```

### 5.4 读取文件

```http
GET /api/v1/bot/{instanceId}/dev/file/content
```

查询参数：

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `path` | string | 是 | 文件路径 |

响应 `data`：

```json
{
  "path": "/root/.openclaw/demo.md",
  "content": "# hello\n",
  "encoding": "utf-8",
  "etag": "b1946ac92492d2347c6235b4d2611184",
  "size": 1024
}
```

### 5.5 保存文件

```http
PUT /api/v1/bot/{instanceId}/dev/file/content
```

请求体：

```json
{
  "path": "/root/.openclaw/demo.md",
  "content": "# updated\n",
  "etag": "b1946ac92492d2347c6235b4d2611184"
}
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `path` | string | 是 | 文件路径 |
| `content` | string | 是 | 新内容 |
| `etag` | string | 否 | 乐观锁版本，读取文件时返回 |

响应 `data`：

```json
{
  "success": true,
  "path": "/root/.openclaw/demo.md",
  "etag": "7b8b965ad4bca0e41ab51de7b31363a1",
  "updatedAt": "2026-04-07T10:10:00Z"
}
```

### 5.6 文件下载 URL

```http
GET /api/v1/bot/{instanceId}/dev/file/download
```

查询参数：

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `path` | string | 是 | 文件路径 |

响应 `data`：

```json
{
  "path": "/root/.openclaw/demo.md",
  "downloadUrl": "https://oss.example.com/dev-downloads/demo_abc123.md"
}
```

## 6. 记忆插件

### 6.1 记忆预览

```http
GET /api/v1/bot/memory/preview?api_key={api_key}
```

查询参数：

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `api_key` | string | 是 | 记忆服务鉴权，当前项目传 `api_key:api_secret` |

响应 `data`：

```json
[
  {
    "file_name": "MEMORY.md",
    "content": "..."
  }
]
```

### 6.2 查询插件是否启用

```http
POST /api/v1/bot/{instanceId}/plugin/enabled
```

请求体：

```json
{
  "plugin_name": "astronmem-cloud-openclaw-plugin"
}
```

响应 `data`：

```json
{
  "enabled": true,
  "plugin_name": "astronmem-cloud-openclaw-plugin"
}
```

### 6.3 开启或关闭 astronmem

```http
POST /api/v1/bot/{instanceId}/plugin/astronmem
```

请求体：

```json
{
  "action": "enable"
}
```

`action` 可取：

| 值 | 说明 |
| --- | --- |
| `enable` | 启用 astronmem |
| `disable` | 禁用 astronmem |

响应 `data` 通常透传底层执行结果。当前项目只要求调用成功。

## 7. 定时任务

### 7.1 创建定时任务

```http
POST /api/v1/bot/{instanceId}/cron
```

请求体：

```json
{
  "id": "sat_xxx",
  "name": "每日晨报",
  "expression": "0 8 * * *",
  "type": "cron",
  "task": "推送今日晨报",
  "timeZone": "Asia/Shanghai",
  "channel": "feishu"
}
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `id` | string | 是 | 调用方生成的任务 ID |
| `name` | string | 是 | 任务名称 |
| `expression` | string | 是 | 执行表达式 |
| `type` | string | 是 | `at` 或 `cron` |
| `task` | string | 是 | 要执行的任务描述 |
| `timeZone` | string | 是 | 时区，如 `Asia/Shanghai` |
| `channel` | string | 是 | 推送渠道，如 `feishu`、`dingtalk`、`openclaw-weixin` |

表达式约定：

| 场景 | `type` | `expression` 示例 |
| --- | --- | --- |
| 单次执行 | `at` | `2030-01-01 09:00:00` |
| 每日重复 | `cron` | `0 9 * * *` |
| 每周重复 | `cron` | `0 9 * * 1` |
| 每月重复 | `cron` | `0 9 1 * *` |

响应 `data`：返回创建后的 cron 对象，至少应包含 `id`。

### 7.2 查询定时任务

```http
GET /api/v1/bot/{instanceId}/crons
```

响应 `data`：

```json
{
  "crons": [
    {
      "id": "sat_xxx",
      "name": "每日晨报",
      "expression": "0 8 * * *",
      "type": "cron",
      "task": "推送今日晨报",
      "timeZone": "Asia/Shanghai",
      "channel": "feishu",
      "state": {
        "nextRunAt": "2026-04-08 08:00:00"
      }
    }
  ]
}
```

### 7.3 更新定时任务

```http
PUT /api/v1/bot/{instanceId}/cron
```

请求体与创建接口一致，`id` 必填。响应 `data` 返回更新后的 cron 对象。

### 7.4 删除定时任务

```http
DELETE /api/v1/bot/{instanceId}/cron
```

请求体：

```json
{
  "id": "sat_xxx"
}
```

成功返回 `code == 0`。

### 7.5 查询运行历史

```http
GET /api/v1/bot/{instanceId}/cron/runs?id={cronId}&limit={limit}
```

查询参数：

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `id` | string | 是 | cron ID |
| `limit` | int | 否 | 返回条数，当前项目默认 100 |

响应 `data`：

```json
{
  "entries": [
    {
      "time": "2026-04-08 08:00:00",
      "runAt": "2026-04-08 08:00:00",
      "status": "success",
      "summary": "done",
      "error": "",
      "durationMs": 1234
    }
  ]
}
```

当前项目会兼容 `time` 或 `runAt` 作为执行时间字段。

## 8. Agent Team 查询

Team 创建由 OpenClaw 对话过程触发；Claw Proxy 当前提供 Team 查询接口。
以下接口都支持可选查询参数 `session_key`，用于按会话过滤 execution。

当前项目使用的 `session_key` 形式：

```text
agent:main:main:{session_id}
```

### 8.1 Team 列表

```http
GET /api/v1/bot/{instanceId}/team/list?session_key={sessionKey}
```

响应 `data` 推荐格式：

```json
{
  "teams": [
    {
      "team_id": "team_xxx",
      "team_name": "周报小组"
    }
  ]
}
```

当前项目也兼容 `data` 直接为数组。

### 8.2 Team 进度

```http
GET /api/v1/bot/{instanceId}/team/{teamId}/progress?session_key={sessionKey}
```

响应 `data`：

```json
{
  "team_id": "team_xxx",
  "team_name": "周报小组",
  "executions": [
    {
      "execution_id": "exec-1",
      "task_name": "生成周报",
      "task_prompt": "请生成本周销售周报",
      "session_key": "agent:main:main:session_xxx",
      "status": "running",
      "created_at": "2026-04-30T16:33:10+08:00",
      "completed_at": null,
      "steps": [
        {
          "name": "拉取数据",
          "status": "completed"
        }
      ]
    }
  ]
}
```

### 8.3 Team 产物

```http
GET /api/v1/bot/{instanceId}/team/{teamId}/outputs?session_key={sessionKey}
```

响应 `data`：

```json
{
  "team_id": "team_xxx",
  "team_name": "周报小组",
  "executions": [
    {
      "execution_id": "exec-1",
      "task_name": "生成周报",
      "outputs": [
        {
          "filename": "weekly_report.md",
          "path": "/root/.openclaw/teams/team_xxx/executions/exec-1/output/weekly_report.md",
          "size": 15234
        }
      ]
    }
  ]
}
```

如需下载产物，可再调用文件下载接口：

```http
GET /api/v1/bot/{instanceId}/dev/file/download?path={path}
```

### 8.4 Team 结果

```http
GET /api/v1/bot/{instanceId}/team/{teamId}/result?session_key={sessionKey}
```

响应 `data`：

```json
{
  "teamId": "team_xxx",
  "teamName": "周报小组",
  "executions": [
    {
      "executionId": "exec-1",
      "taskName": "生成周报",
      "content": "Task Complete\n\n..."
    }
  ]
}
```

当前项目对 Team 错误码的处理：

| code | 含义 |
| --- | --- |
| `300080` | Team 不存在 |
| `300081` / `300083` | 步骤或状态数据不存在，可按空 executions 处理 |
| `300082` | Team execution 不存在 |
| `400001` | Sandbox 服务异常 |
| `100001` | Team 服务内部错误 |

## 9. 备份与恢复

### 9.1 开始备份

```http
POST /api/v1/bot/{instanceId}/backup
```

无请求体。

响应 `data`：

```json
{
  "taskId": "backup_task_xxx"
}
```

### 9.2 查询备份状态

```http
GET /api/v1/bot/{instanceId}/backup/status?task_id={taskId}
```

响应 `data`：

```json
{
  "status": "running",
  "phase": "uploading"
}
```

`status` 常见值：`running`、`success`、`failed`。

### 9.3 开始恢复

```http
POST /api/v1/bot/{instanceId}/backup/restore
```

无请求体。

响应 `data`：

```json
{
  "taskId": "restore_task_xxx"
}
```

### 9.4 查询恢复状态

```http
GET /api/v1/bot/{instanceId}/backup/restore/status?task_id={taskId}
```

响应 `data`：

```json
{
  "status": "running",
  "phase": "restoring"
}
```

`status` 常见值：`running`、`success`、`failed`。

### 9.5 删除备份

```http
DELETE /api/v1/bot/{instanceId}/backup
```

无请求体。成功返回 `code == 0`。

## 10. 推荐对接流程

### 10.1 首次部署

1. 调用方创建自己的业务 Bot 记录，生成 `botId`。
2. 如果需要对话能力，先从调用方自己的 Bridge 服务获取 `bridgeToken`。
3. 调 `POST /api/v1/bot/deploy`，保存返回的 `instanceId`。
4. 按需逐个调 `/skill/install` 安装 skill。
5. 按需调 `/skill/add_env` 注入环境变量。
6. 如果环境变量影响运行时配置，调 `/restart`。
7. 将 Bot 状态标记为可用。

### 10.2 重置实例

1. 调 `/stop` 停止旧 `instanceId`。
2. 等待几秒让底层资源释放。
3. 重新调 `/deploy` 获得新 `instanceId`。
4. 重新安装 skill、注入环境变量、必要时重启。
5. 覆盖本地 `botId -> instanceId` 映射。

### 10.3 删除实例

1. 调 `/stop` 停止实例。
2. 如需要清理备份，调 `DELETE /backup`。
3. 本地软删或删除业务记录。

### 10.4 会话失效处理

以下情况建议提示用户重新部署或自动触发重置：

- HTTP `400` / `404`
- 业务码 `400003`
- 连续网络超时且实例状态不可确认

## 11. 当前项目代码来源

| 能力 | 代码位置 |
| --- | --- |
| 公共 Claw Proxy 调用 | `src/app/clients/claw_proxy_base.py` |
| 生命周期 / 模型 | `src/app/clients/bot_client.py` |
| Skill / env | `src/app/clients/skill_client.py` |
| 开发文件 | `src/app/clients/dev_file_client.py` |
| 记忆插件 | `src/app/clients/memory_proxy_client.py` |
| 定时任务 | `src/app/clients/cron_proxy.py` |
| Agent Team | `src/app/clients/team_api_client.py` |
| 升级 | `src/app/clients/bot_upgrade_client.py` |
| 自动修复 | `src/app/clients/bot_doctor_client.py` |
| 备份恢复 | `src/app/clients/backup_client.py` |
