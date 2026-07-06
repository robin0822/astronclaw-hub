# 智能体龙虾数据模型

## P0 最小表集合

| 表名 | 说明 |
| --- | --- |
| `agents` | 龙虾实例主表。 |
| `agent_versions` | 龙虾配置和版本快照。 |
| `agent_deploy_tasks` | 部署任务。 |
| `agent_runtime_snapshots` | 运行状态快照。 |
| `agent_runtime_configs` | 运行时参数配置。 |
| `agent_bind_skills` | 龙虾与 Skill 的绑定关系。 |
| `agent_bind_knowledge` | 龙虾与知识库的绑定关系。 |
| `agent_state_events` | 生命周期状态事件。 |
| `agent_logs_index` | 日志索引，实际日志可在日志系统中。 |
| `audit_logs` | 审计日志。 |

## `agents` 核心字段

| 字段 | 说明 |
| --- | --- |
| `id` | 平台内部龙虾 ID。 |
| `bot_id` | 业务侧生成的 bot 标识。 |
| `proxy_instance_id` | Claw Proxy 返回的运行实例 ID。 |
| `name` | 龙虾名称。 |
| `description` | 描述。 |
| `status` | 生命周期状态。 |
| `department_id` | 所属部门。 |
| `owner_id` | 负责人。 |
| `primary_model_id` | 主模型。 |
| `fallback_model_id` | 备用模型。 |
| `resource_profile` | CPU、内存、GPU、存储等资源配置。 |
| `created_by` | 创建人。 |
| `created_at` | 创建时间。 |
| `updated_at` | 更新时间。 |
| `deleted_at` | 软删除时间。 |

## 关系说明

```text
agents
  1 -> n agent_versions
  1 -> n agent_deploy_tasks
  1 -> n agent_runtime_snapshots
  1 -> n agent_runtime_configs
  1 -> n agent_bind_skills
  1 -> n agent_bind_knowledge
  1 -> n agent_state_events
  1 -> n audit_logs
```

## 状态事件

每次状态变化都要写入 `agent_state_events`：

| 字段 | 说明 |
| --- | --- |
| `agent_id` | 龙虾 ID。 |
| `from_status` | 变化前状态。 |
| `to_status` | 变化后状态。 |
| `reason` | 变化原因。 |
| `operator_id` | 操作人，系统任务可为空并记录任务 ID。 |
| `task_id` | 关联任务 ID。 |
| `created_at` | 事件时间。 |

## 审计要求

以下操作必须写 `audit_logs`：

- 创建、编辑、删除龙虾。
- 部署、启动、停止、重启。
- 绑定或解绑 Skill。
- 绑定或解绑知识库。
- 修改模型配置。
- 查看或导出敏感日志。
- 高危操作审批通过后的实际执行。
