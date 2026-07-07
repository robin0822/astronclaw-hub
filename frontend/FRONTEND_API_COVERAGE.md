# 前端接口联调用例梳理

来源：`D:\文件\FRONTEND_API.md`
生成时间：2026-07-06 13:47:37
接口总数：232

## Playwright 测试策略

- `frontend/e2e/api-contract-cases.ts` 保存接口目录，按功能分组维护所有接口。
- `frontend/e2e/api-contract.spec.ts` 会先调用 `/auth/login` 获取 `accessToken`，后续请求统一携带 `Authorization: Bearer <accessToken>`。
- 默认只跑非破坏性的 GET 接口，并校验状态码不是 5xx、JSON 响应包含统一 `code/message/requestId/data` 结构。
- POST/PUT/DELETE、开发辅助接口、下载导出接口默认跳过，避免在真实环境误创建、误删除或下载大文件。需要全量压测时，可在测试环境补齐 fixtures 后再打开。

## 运行方式

```bash
cd frontend
npm run test:e2e:api
```

可选环境变量：

- `E2E_USERNAME` / `E2E_PASSWORD`：登录账号，默认 `admin` / `Admin@123456`。
- `E2E_ENABLE_MUTATING_API_TESTS=1`：允许执行 POST/PUT/DELETE 等写操作。只应在可重置的测试环境开启。
- `E2E_ENABLE_DOWNLOAD_API_TESTS=1`：允许执行导出/下载接口。
- `E2E_ENABLE_DEV_API_TESTS=1`：允许执行开发辅助接口。
- `E2E_AGENT_ID`、`E2E_MODEL_ID`、`E2E_ROLE_ID` 等：替换路径参数用的测试数据 ID。

## 功能分组

- 健康检查：1 个接口，默认可跑 GET 1 个，写操作 0 个。
- 开发/测试辅助：5 个接口，默认可跑 GET 0 个，写操作 5 个。
- 认证与当前用户：8 个接口，默认可跑 GET 4 个，写操作 4 个。
- SSO 配置：3 个接口，默认可跑 GET 1 个，写操作 2 个。
- 智能体管理：19 个接口，默认可跑 GET 6 个，写操作 13 个。
- 智能体任务与同步：4 个接口，默认可跑 GET 3 个，写操作 1 个。
- 批量任务：4 个接口，默认可跑 GET 2 个，写操作 1 个。
- 组织、角色与权限：17 个接口，默认可跑 GET 8 个，写操作 9 个。
- 模型网关与模型管理：20 个接口，默认可跑 GET 8 个，写操作 11 个。
- Skill 管理：12 个接口，默认可跑 GET 5 个，写操作 7 个。
- 知识库：10 个接口，默认可跑 GET 3 个，写操作 7 个。
- 监控、告警与通知：19 个接口，默认可跑 GET 8 个，写操作 11 个。
- 诊断与运维自动化：19 个接口，默认可跑 GET 8 个，写操作 10 个。
- 成本核算：16 个接口，默认可跑 GET 9 个，写操作 6 个。
- 审计、安全与导出：10 个接口，默认可跑 GET 5 个，写操作 1 个。
- 审批、席位与共享：15 个接口，默认可跑 GET 6 个，写操作 9 个。
- 渠道与业务系统：17 个接口，默认可跑 GET 7 个，写操作 10 个。
- 记忆与运行时代理：33 个接口，默认可跑 GET 19 个，写操作 14 个。
