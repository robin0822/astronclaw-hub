# AstronClaw 后端测试方案

## 1. 测试目标与依据

本文用于补齐 AstronClaw 后端交付测试文档，测试范围依据：

1. `astronclaw-chinalife-requirements.md` 中 FR-01 至 FR-11 的业务需求。
2. `claw_proxy_bot_http_api(1).md` 中 Claw Proxy `/api/v1/bot` 能力。
3. `沙箱机器人对接字段与密钥交付说明.md` 中 ID、token、key、secret 归属。
4. 本目录 `01-backend-architecture-design.md` 至 `04-frontend-api-documentation.md` 的后端设计和业务 API。

测试目标：

| 目标 | 验证重点 |
| --- | --- |
| 需求可验收 | P0 能力、核心接口、关键状态流转和验收指标可被测试用例覆盖 |
| 集成边界正确 | 前端只调用 `/api/v1/astron-claw`，后端代理 Claw Proxy，密钥不下发前端 |
| 状态一致 | 业务台账、异步任务、Claw Proxy 返回、监控快照、审计日志一致 |
| 安全合规 | 权限、数据范围、高危审批、密钥脱敏、审计留痕、文件安全和模型调用审计可验证 |
| 故障可恢复 | 外部超时、会话失效、部署失败、任务失败、告警闭环和自愈路径可验证 |

## 2. 测试分层

| 层级 | 范围 | 主要验证 |
| --- | --- | --- |
| 单元测试 | service、client、permission、状态机、成本规则 | 纯业务规则、错误转换、边界条件 |
| API 测试 | `/api/v1/astron-claw` 所有前端接口 | 请求校验、响应结构、分页、错误码、权限 |
| 集成测试 | Bridge、Claw Proxy、密钥系统、监控、日志、对象存储 | 外部调用契约、超时重试、数据回写 |
| 异步任务测试 | 部署、批量、同步、成本归档、巡检、备份恢复 | 任务状态、幂等、失败重试、进度统计 |
| 安全测试 | RBAC、数据权限、密钥、审计、导出、文件路径 | 越权拦截、脱敏、审计完整性 |
| 验收测试 | FR 需求场景和端到端流程 | 从创建到部署、运维、监控、成本、审计闭环 |

## 3. 测试环境与数据

### 3.1 环境

| 环境 | 用途 | 外部依赖 |
| --- | --- | --- |
| local | 单元测试和 API mock 测试 | mock Claw Proxy、mock Bridge、内存或测试数据库 |
| test | 后端集成测试 | test Claw Proxy、test Bridge、测试密钥系统、测试对象存储 |
| pre | 预验收联调 | pre Claw Proxy、pre Bridge、真实监控或预生产监控 |

pre 环境的 Claw Proxy Base URL 和 token 只允许配置在后端环境变量或密钥系统中。测试报告、接口日志和截图不得出现完整 token、模型 `apiKey`、租户 `api_secret`。

### 3.2 基础测试数据

| 数据 | 最小数量 | 说明 |
| --- | --- | --- |
| 部门 | 3 | 总部、一级部门、二级部门，用于数据范围测试 |
| 用户 | 6 | 超级管理员、平台管理员、部门管理员、模型管理员、安全审计员、普通用户 |
| 角色 | 5 | 覆盖查看、创建、运维、审计、导出等权限差异 |
| 席位包 | 2 | 一个充足、一个即将耗尽 |
| 模型 | 3 | 主模型、备用模型、异常模型 |
| Skill | 4 | 已审核、待审核、禁用、安装失败 |
| 知识库 | 3 | 个人、部门、企业级 |
| 智能体 | 8 | draft、deploying、running、abnormal、stopped、upgrading、archived、violation_offline |
| 告警 | 6 | P0/P1/P2、待处理、处理中、已闭环 |

## 4. P0 需求测试矩阵

| 需求 | 核心用例 | 验收断言 |
| --- | --- | --- |
| FR-01 智能体管理 | 创建、部署、详情、启停、重启、升级、模型切换、批量操作 | 状态机正确，`botId` 和 `instanceId` 映射保存，失败写告警和审计 |
| FR-02 统一身份权限 | 账号密码登录、角色权限、数据范围、席位校验、SSO 预留 | 登录成功颁发业务 token，无权限返回 403，跨部门数据不可见，席位不足返回 `422001` |
| FR-03 监控告警 | 看板、指标、告警认领、处理、闭环、诊断联动 | 生产数据源非前端 mock，告警闭环后通知计数同步 |
| FR-04 模型网关 | 模型台账、密钥掩码、探针、限流、模型切换、调用审计 | 前端不返回完整密钥，限流命中记录，切换调用 Claw Proxy `/model` |
| FR-05 成本核算 | 部门、项目、模型、智能体成本统计和导出 | Token、容器、席位成本计算可追溯，报表维度正确 |
| FR-06 运维自动化 | 巡检、修复、备份、恢复、任务失败告警 | 巡检报告可导出，自愈反向更新告警和实例状态 |
| FR-07 Skill 管理 | 导入、审核、授权、安装、卸载、环境变量 | 未审核 Skill 不能安装，环境变量密文保存且查询只返回掩码 |
| FR-08 知识和记忆 | 上传、校验、解析、绑定、删除引用检查、AstronMem | 文件安全校验生效，权限隔离正确，插件状态可查询和切换 |
| FR-10 安全合规基线 | 高危审批、审计防篡改、导出审计、敏感字段脱敏 | 高危操作未审批不可执行，审计字段完整，敏感值不明文展示 |
| FR-11 问题诊断 | 异常聚合、知识库匹配、一键修复、故障沉淀 | P0/P1 告警自动生成诊断，修复后可验证闭环 |

FR-09 消息渠道在需求文档中标注“暂时不做”，本期至少测试接口占位、告警通知预留、业务系统嵌入授权模型和调用来源审计是否具备可扩展基础。

## 5. 核心功能测试用例

### 5.1 智能体创建与部署

| 编号 | 前置条件 | 操作 | 预期结果 |
| --- | --- | --- | --- |
| AGT-001 | 用户有 `agent:create`，席位充足，模型启用 | `POST /agents` 创建智能体 | 返回 `deploying` 和 `deployTaskId`，生成 `agt_` 前缀 `botId` |
| AGT-002 | 创建任务已入队 | worker 调 Bridge 创建 `bridgeToken`，调 Claw Proxy `/deploy` | 保存 `proxy_instance_id`，状态变为 `running` |
| AGT-003 | 选择 2 个已审核 Skill | 部署后安装 Skill | 逐个调用 `/skill/install`，本地绑定表状态为 installed |
| AGT-004 | Skill 需要环境变量 | 调 `/skill/add_env` 后重启 | 环境变量写密钥系统，查询只返回掩码，重启任务成功 |
| AGT-005 | Claw Proxy 返回 `300003` | 执行部署 | 任务失败，智能体 `abnormal`，写告警和审计，返回失败阶段和建议 |
| AGT-006 | Claw Proxy 超时 | 执行部署 | 按重试策略重试；超过阈值后返回 `502001` 并保留任务失败原因 |

### 5.2 生命周期与状态机

| 编号 | 初始状态 | 操作 | 预期状态 |
| --- | --- | --- | --- |
| LFC-001 | `running` | `POST /agents/{id}/stop` | `stopping -> stopped`，调用 Claw Proxy `/stop` |
| LFC-002 | `running` | `POST /agents/{id}/restart` | 健康检查成功后仍为 `running` |
| LFC-003 | `running` | `POST /agents/{id}/upgrade` | `upgrading -> running`，如返回新 `instanceId` 则覆盖映射 |
| LFC-004 | `running` | `PUT /agents/{id}/model` | 调 `/model`，保存主备模型快照，写模型变更审计 |
| LFC-005 | `draft` | `POST /agents/{id}/restart` | 返回 `409001 invalid state` |
| LFC-006 | `running` | 违规下线 | 进入 `violation_offline`，保留证据链和审批记录 |

### 5.3 批量任务

| 编号 | 场景 | 预期结果 |
| --- | --- | --- |
| BAT-001 | 按当前页创建批量重启 | 服务端二次校验目标权限，冻结 targetIds |
| BAT-002 | 按筛选条件批量停用 | 后端按筛选条件重新查询并生成 `scope_snapshot` |
| BAT-003 | 批量升级启用灰度 | 按批次执行，失败时根据策略暂停或继续 |
| BAT-004 | 批量删除 | 创建审批单，审批通过后 worker 按 `payload_snapshot` 执行 |
| BAT-005 | 部分 item 失败 | 总任务继续，`successCount`、`failedCount`、失败原因准确 |
| BAT-006 | 导出批量结果 | 导出字段含实例、动作、时间、结果、失败原因、操作人 |

### 5.4 组织权限与席位

| 编号 | 场景 | 预期结果 |
| --- | --- | --- |
| IAM-000 | 使用正确账号密码登录 | 返回 `accessToken`、用户信息、角色、权限码和数据范围，写登录成功日志 |
| IAM-000-1 | 密码错误登录 | 返回 `401001`，写登录失败日志，不暴露账号是否存在的敏感细节 |
| IAM-000-2 | 连续密码错误超过阈值 | 返回 `401002 account locked`，锁定期内拒绝登录 |
| IAM-000-3 | 停用或离职账号登录 | 返回 `401003 account disabled` |
| IAM-000-4 | 退出登录后继续使用旧 token | 返回 401，旧 session 或 token 已失效 |
| IAM-000-5 | 私有化 SSO mock 登录成功 | 外部身份映射到本地用户后，仍返回业务后端 token 和本地权限数据 |
| IAM-001 | 无 `agent:view` 访问智能体列表 | 返回 403，写安全审计 |
| IAM-002 | 部门管理员访问其他部门智能体 | 不返回越权数据 |
| IAM-003 | 高危权限缺失执行删除 | 返回 403 或 `409002 approval required` |
| IAM-004 | 席位不足创建智能体 | 返回 `422001`，包含 `required`、`available`、`seatPackageId` |
| IAM-005 | 用户离职停用 | 账号冻结，席位回收，权限重算 |
| IAM-006 | 跨部门席位调拨 | 写调拨前后值和审批审计 |

### 5.5 监控、告警与诊断

| 编号 | 场景 | 预期结果 |
| --- | --- | --- |
| MON-001 | 查询全域看板 | 返回运行实例、异常实例、可用模型、待处理告警、今日调用量等 KPI |
| MON-002 | 指标数据来自 Prometheus 或日志系统 | 响应标记 `dataSource`，生产环境不得为前端 mock |
| MON-003 | 触发模型错误率高 | 创建 P0/P1 告警和诊断待办 |
| MON-004 | 告警认领、处理、闭环 | 状态按 `pending -> claimed -> processing -> closed` 流转 |
| MON-005 | 一键修复成功 | 调 `/doctor/fix` 或本地 ops 任务，反向关闭告警并更新实例状态 |
| MON-006 | 诊断知识库匹配错误码 | 返回现象、原因、解决方案和验证方式 |

### 5.6 模型网关与成本

| 编号 | 场景 | 预期结果 |
| --- | --- | --- |
| MDL-001 | 新增模型 | 完整 `apiKey` 写密钥系统，列表只返回 `secretRef` 和掩码 |
| MDL-002 | 模型探针失败 | 模型状态异常，触发告警或健康状态更新 |
| MDL-003 | 命中 QPS 限流 | 返回限流错误或排队，写 `model_policy_hits` |
| MDL-004 | 主模型不可用 | 按路由策略切换备用模型 |
| CST-001 | 每日成本归档 | 生成部门、项目、模型、智能体成本统计 |
| CST-002 | 成本导出 | 校验权限，写导出审计，导出数据维度正确 |

### 5.7 Skill、知识和记忆

| 编号 | 场景 | 预期结果 |
| --- | --- | --- |
| SKL-001 | 上传 Skill 包 | 执行格式校验、依赖校验、安全扫描 |
| SKL-002 | 安装待审核 Skill | 拒绝安装 |
| SKL-003 | 查询运行时 Skill | 调 `/skill/list`，展示与本地绑定表的漂移 |
| KNB-001 | 上传 PDF/DOCX/TXT/XLSX/PPTX/MD | 类型、大小、病毒、敏感信息校验通过后进入解析 |
| KNB-002 | 删除被智能体引用的文件 | 拒绝删除并返回引用关系 |
| MEM-001 | 查询记忆预览 | 后端取 `astronmenApiKey` 调 `/memory/preview`，前端不接触密钥 |
| MEM-002 | 开关 AstronMem | 调 `/plugin/astronmem`，写操作审计 |

## 6. Claw Proxy 代理测试

### 6.1 代理边界

| 规则 | 测试断言 |
| --- | --- |
| 前端入参使用 `agentId`、`skillId`、`cronId` 等业务 ID | 前端接口不要求传 `instanceId`、`packageName`、完整密钥 |
| 后端从库表或密钥系统解析真实外部参数 | Claw Proxy 请求路径中使用 `proxy_instance_id` |
| 服务间 token 不出后端 | API 响应、日志、错误消息无完整 `CLAW_PROXY_AUTH_TOKEN` |
| 外部错误统一转换 | `400003` 转 `SANDBOX_SESSION_EXPIRED` 或 `502002` |

### 6.2 Claw Proxy 契约用例

| 能力 | Claw Proxy 接口 | 后端业务接口 | 关键断言 |
| --- | --- | --- | --- |
| 部署 | `POST /deploy` | `POST /agents` / worker | 保存 `instanceId`，失败写任务和告警 |
| 重启 | `POST /{instanceId}/restart` | `POST /agents/{id}/restart` | 状态和审计一致 |
| 停止 | `POST /{instanceId}/stop` | `POST /agents/{id}/stop` | 停止幂等处理 |
| 模型切换 | `PUT /{instanceId}/model` | `PUT /agents/{id}/model` | `modelId` 字段映射正确 |
| Skill 安装 | `POST /skill/install` | `POST /agents/{id}/skills/{skillId}/install` | 使用 runtime `packageName` |
| 文件保存 | `PUT /dev/file/content` | `PUT /agents/{id}/dev-file/content` | 路径白名单、etag、写审计 |
| Cron | `POST/PUT/DELETE /cron` | `/agents/{id}/crons*` | `cronId` 后端生成并复用 |
| Team | `/team/*` | `/agents/{id}/teams*` | `session_key=agent:main:main:{sessionId}` |
| 备份恢复 | `/backup*` | `/agents/{id}/backups*` | 保存 `proxyTaskId`，轮询状态 |

## 7. 安全与合规测试

| 编号 | 场景 | 预期结果 |
| --- | --- | --- |
| SEC-001 | API 响应扫描敏感字段 | 不出现完整 token、apiKey、api_secret、bridgeToken 明文 |
| SEC-002 | 日志扫描敏感字段 | 只出现 hash、前后缀或掩码 |
| SEC-003 | 文件路径穿越 | `../`、非 `/root/.openclaw` 路径被拒绝 |
| SEC-004 | 导出审计日志 | 需要权限或审批，导出操作本身写审计 |
| SEC-005 | 高危操作审批后 payload 被篡改 | worker 使用审批时冻结的 `payload_snapshot` |
| SEC-006 | 审计 hash 链 | 新增审计日志包含 `hash_prev`、`hash_current` 或客户认可的防篡改字段 |
| SEC-007 | 模型调用输入含敏感信息 | 写入 `model_call_logs` 前完成摘要和脱敏 |
| SEC-008 | 普通用户访问管理后台接口 | 返回 403，只能使用被授权的聊天资源 |

## 8. 异常与恢复测试

| 异常 | 注入方式 | 预期处理 |
| --- | --- | --- |
| Claw Proxy HTTP 400/404 | mock 返回 400/404 | 识别为实例不可用或会话失效 |
| Claw Proxy `400003` | mock 业务码 | 返回重新部署提示，状态同步标记会话失效 |
| Claw Proxy `300003` | 部署接口返回失败 | 部署任务失败，记录失败阶段 |
| 网络超时 | 延迟超过超时阈值 | 重试后返回 `502001`，日志脱敏 |
| Bridge 创建 token 失败 | mock 500 | 创建任务失败，不调用 `/deploy` |
| Skill 安装部分失败 | 第二个 Skill 返回失败 | 智能体状态按策略处理，失败 Skill 有明细 |
| 批量任务 worker 中断 | 杀掉 worker 后重启 | 未完成 item 可继续或按幂等策略跳过已完成 item |
| 成本归档重复执行 | 同一天执行两次 | 结果幂等，不重复累加 |

## 9. 自动化建议

### 9.1 测试目录建议

```text
backend/tests/
  unit/
    test_agent_state_machine.py
    test_permission_service.py
    test_claw_proxy_error_mapping.py
    test_cost_rules.py
  api/
    test_agents_api.py
    test_batch_tasks_api.py
    test_models_api.py
    test_alerts_api.py
    test_audit_api.py
  integration/
    test_claw_proxy_contract.py
    test_bridge_contract.py
    test_secret_manager.py
    test_dev_files_proxy.py
    test_backup_restore.py
  jobs/
    test_deploy_worker.py
    test_batch_worker.py
    test_sync_agent_status.py
    test_cost_archive.py
  security/
    test_rbac_data_scope.py
    test_secret_masking.py
    test_audit_trail.py
    test_path_whitelist.py
```

### 9.2 Mock 与契约测试

1. local 环境使用 mock Claw Proxy 覆盖成功、业务失败、HTTP 失败、超时。
2. test/pre 环境保留一组真实 Claw Proxy smoke tests，只执行低风险接口，例如部署测试实例、查询 Skill、备份状态、停止测试实例。
3. 契约测试需固定 Claw Proxy 响应样例，尤其覆盖 `code == 0`、`400003`、`300003`、Team 空结果码和备份轮询状态。
4. 所有外部 client 单元测试必须断言 Authorization header 已注入但日志不会打印完整 token。

### 9.3 CI 门禁

| 门禁 | 要求 |
| --- | --- |
| 单元测试 | 每次提交运行，核心 service 和 client 错误映射必须覆盖 |
| API 测试 | PR 阶段运行，校验 OpenAPI/响应快照和权限 |
| 安全扫描 | PR 阶段扫描密钥明文、路径穿越、依赖漏洞 |
| 集成 smoke | 合并到 test/pre 前运行，外部依赖不可用时明确标记为阻塞 |
| 覆盖率 | P0 模块行覆盖率建议不低于 80%，状态机、权限、密钥、错误映射需分支覆盖 |

## 10. 验收检查清单

| 检查项 | 通过标准 |
| --- | --- |
| 文档一致性 | API 测试覆盖 `04-frontend-api-documentation.md` 中 P0 接口 |
| 需求覆盖 | FR-01 至 FR-08、FR-10、FR-11 至少有正向和异常用例 |
| Claw Proxy 集成 | 部署、生命周期、Skill、文件、记忆、Cron、Team、备份恢复均有代理测试 |
| 权限安全 | RBAC、数据范围、高危审批、席位不足、普通用户隔离均通过 |
| 密钥安全 | 前端响应、日志、导出文件无完整服务间 token 和模型密钥 |
| 审计追溯 | 写操作、高危读、导出、生命周期、模型变更均可查询审计 |
| 监控告警 | 真实或预生产数据源可说明，告警认领处理闭环可演示 |
| 异步任务 | 部署、批量、同步、巡检、成本归档、备份轮询状态可追踪 |
| 故障恢复 | 外部超时、会话失效、部署失败、worker 中断有明确处理 |

## 11. 测试报告模板

```text
项目：AstronClaw 后端测试
版本：
环境：local / test / pre
测试时间：
测试负责人：

范围：
- 覆盖模块：
- 未覆盖模块及原因：
- 外部依赖版本或地址：

结果汇总：
- 用例总数：
- 通过：
- 失败：
- 阻塞：
- 跳过：

关键风险：
- P0 阻塞问题：
- 安全合规问题：
- 外部依赖问题：

附件：
- API 测试报告
- 集成测试报告
- 安全扫描报告
- 失败日志脱敏包
```
