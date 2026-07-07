# 前端 E2E 测试说明

## Mock UI 自动化

Mock UI 自动化不依赖后端服务，Playwright 会在浏览器启动前注入稳定的业务数据，并拦截 `/api/v1/astron-claw/**` 请求。

```powershell
npm run test:e2e:mock
```

如果本机 Playwright 浏览器未安装，可以临时使用系统 Chrome：

```powershell
$env:PLAYWRIGHT_USE_SYSTEM_CHROME='1'; npm run test:e2e:mock
```

当前覆盖范围：

- 登录页表单提交和 redirect 跳转。
- 主题切换、深色模式持久化和常见页面深色样式检查。
- 侧边栏主要功能页面跳转和页面标题可见性。
- 智能体列表搜索、详情弹窗、状态同步、运行日志刷新。
- 公开分享页授权资源展示。

## 真实接口契约测试

接口契约测试需要后端服务可访问，默认不会执行破坏性写接口。按需配置后运行：

```powershell
$env:E2E_ENABLE_API_CONTRACT='1'; $env:BACKEND_BASE_URL='http://127.0.0.1:8000'; npm run test:e2e:api
```

需要覆盖写接口、下载接口或开发文件接口时，再显式打开对应环境变量，避免误操作真实环境数据。
