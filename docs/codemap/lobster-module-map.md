# 智能体龙虾模块实现地图

## 模块职责

`agents` 模块负责龙虾实例的管理闭环：

- 创建和编辑基础配置。
- 展示列表和详情。
- 发起部署任务。
- 执行启停、重启、删除等生命周期操作。
- 聚合 Skill、知识库、模型、运行状态、日志和审计记录。

## 前端页面规划

| 页面 | 路由 | 关键能力 |
| --- | --- | --- |
| 龙虾列表 | `/agents` | 查询、筛选、创建、批量入口预留、生命周期快捷操作。 |
| 龙虾详情 | `/agents/:id` | 基础信息、运行状态、模型配置、Skill、知识库、日志、审计。 |
| 创建龙虾 | `/agents/create` 或弹窗 | 填写名称、部门、负责人、模型、Skill、知识库、资源配置。 |
| 分享页 | `/share/:id` | 展示被分享龙虾的基础信息和访问提示。 |

## 后端 API 规划

业务后端统一提供 `/api/v1/astron-claw` 前缀：

```text
GET    /api/v1/astron-claw/agents
POST   /api/v1/astron-claw/agents
GET    /api/v1/astron-claw/agents/{id}
PATCH  /api/v1/astron-claw/agents/{id}
POST   /api/v1/astron-claw/agents/{id}/deploy
POST   /api/v1/astron-claw/agents/{id}/start
POST   /api/v1/astron-claw/agents/{id}/stop
POST   /api/v1/astron-claw/agents/{id}/restart
DELETE /api/v1/astron-claw/agents/{id}
GET    /api/v1/astron-claw/agents/{id}/skills
PUT    /api/v1/astron-claw/agents/{id}/skills
GET    /api/v1/astron-claw/agents/{id}/knowledge-bases
PUT    /api/v1/astron-claw/agents/{id}/knowledge-bases
GET    /api/v1/astron-claw/agents/{id}/logs
GET    /api/v1/astron-claw/agents/{id}/audit-logs
```

## Claw Proxy 适配

前端不直接访问 Claw Proxy。业务后端通过适配层调用 `/api/v1/bot`：

```text
业务前端
  -> /api/v1/astron-claw
  -> 业务后端鉴权、审计、任务编排、错误转换
  -> /api/v1/bot
  -> Claw Proxy / 沙箱运行时
```

## 实现顺序

1. 建立数据库表和状态枚举。
2. 实现列表、详情、创建接口的 mock 数据闭环。
3. 接前端 `/agents` 列表和详情。
4. 实现部署任务表和部署状态流转。
5. 实现启停、重启、删除接口。
6. 接 Skill 和知识库绑定。
7. 接运行状态同步、日志和审计。
8. 最后替换 mock，接真实 Claw Proxy。

## 关键不变量

- 前端永远不保存完整模型密钥或沙箱令牌。
- 所有高影响操作必须写入审计日志。
- 对 Claw Proxy 的错误必须转换为平台业务错误。
- 删除优先使用软删除，保留审计和历史记录。
- 详情页展示的运行态数据以最近一次同步快照为准。
