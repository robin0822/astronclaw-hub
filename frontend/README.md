# AstronClaw Frontend

企业智能体管理平台前端。生产环境应连接 AstronClaw 业务后端，前端不保存模型密钥、运行服务 token 或租户级密钥。

## 启动

```bash
npm install
npm run dev
```

默认开发地址为 `http://localhost:5174`，`/api` 会通过 Vite 代理转发到 `BACKEND_BASE_URL`。

## 环境变量

开发环境默认读取 `.env.development`，如需个人本地覆盖可新建 `.env.local`：

- `VITE_ASTRONCLAW_API_BASE_URL`：前端调用的业务 API 前缀，默认 `/api/v1/astron-claw`。
- `BACKEND_BASE_URL`：开发代理目标，默认 `http://127.0.0.1:8000`。
- API 默认超时为 60s；长耗时接口在调用处单独设置 `timeoutMs`。

## 鉴权与权限

登录、会话持久化和退出登录由后端维护。前端登录页只调用 `POST /auth/login`，退出按钮调用 `POST /auth/logout`；业务接口收到 HTTP 401 或业务码 `401001` 时，统一跳转到 `/login?redirect=...`。

前端不再用本地 `AuthProvider`、`sessionStorage` 用户信息或路由守卫判断能否访问页面。具体菜单权限、按钮权限和接口权限应以后端返回结果为准，页面只负责展示接口成功、失败、空态和加载态。

`/share/:id?token=` 不强制跳登录；页面通过业务后端 `GET /share/:id?token=` 校验链接有效期和授权范围后再展示。

## 密钥处理

模型 API Key 只作为录入表单的临时值。保存到前端 store/localStorage 前会被剔除，生产环境应由后端密钥托管服务完成写入、轮换和审计，前端不回显密钥明文。

## 检查

```bash
npm run format:check
npm run lint
npm run typecheck
npm run test
npm run build
npm run check
```

单元/组件测试使用 Vitest、Testing Library 和 MSW；浏览器端到端测试使用 Playwright：

```bash
npm run test
npm run test:e2e
```
