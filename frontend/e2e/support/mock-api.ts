import { expect, type Page, type Route } from '@playwright/test';
import { mockAgentDetail, mockAgentSummaries, mockRuntimeLogs, mockSharedAgent, mockStoreData } from './mock-data';

const API_PREFIX = '/api/v1/astron-claw';

declare global {
  interface Window {
    /** Playwright 在页面初始化前注入的稳定业务数据，避免 UI mock 测试依赖真实后端。 */
    __ASTRONCLAW_E2E_STORE__?: typeof mockStoreData;
  }
}

function ok(data: unknown) {
  return {
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ code: 0, message: 'success', data, requestId: 'e2e-request' }),
  };
}

function notFound(message = 'mock endpoint not found') {
  return {
    status: 404,
    contentType: 'application/json',
    body: JSON.stringify({ code: 404001, message, data: null, requestId: 'e2e-request' }),
  };
}

function pageResult<T>(items: T[], page = 1, pageSize = 20) {
  const start = (page - 1) * pageSize;
  return { items: items.slice(start, start + pageSize), page, pageSize, total: items.length };
}

function filterAgents(url: URL) {
  const keyword = url.searchParams.get('keyword')?.trim();
  const status = url.searchParams.get('status')?.trim();

  return mockAgentSummaries.filter((agent) => {
    const keywordMatched = !keyword || [agent.name, agent.department.name, agent.owner.name, agent.primaryModel.name].some((value) => value.includes(keyword));
    const statusMatched = !status || status === 'all' || agent.status === status;
    return keywordMatched && statusMatched;
  });
}

function escapeForRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

async function fulfillApi(route: Route) {
  const request = route.request();
  const url = new URL(request.url());
  const path = url.pathname.replace(API_PREFIX, '') || '/';
  const method = request.method().toUpperCase();

  if (method === 'POST' && path === '/auth/login') {
    await route.fulfill(ok({ accessToken: 'e2e-access-token', user: { username: 'admin', name: '平台管理员' } }));
    return;
  }

  if (method === 'POST' && path === '/auth/logout') {
    await route.fulfill(ok({}));
    return;
  }

  if (method === 'GET' && path === '/me') {
    await route.fulfill(ok({ username: 'admin', name: '平台管理员' }));
    return;
  }

  if (method === 'GET' && path === '/me/permissions') {
    await route.fulfill(ok({ roles: ['admin'], permissions: ['agent.create', 'agent.edit', 'agent.lifecycle', 'agent.delete', 'model.manage', 'security.manage'] }));
    return;
  }

  if (method === 'GET' && path === '/agents') {
    const page = Number(url.searchParams.get('page') ?? 1);
    const pageSize = Number(url.searchParams.get('pageSize') ?? 20);
    await route.fulfill(ok(pageResult(filterAgents(url), page, pageSize)));
    return;
  }

  if (method === 'POST' && path === '/agents') {
    await route.fulfill(ok({ id: 'ac-agent-created', botId: 'bot-created', status: 'deploying', deployTaskId: 'task-created' }));
    return;
  }

  if (method === 'GET' && /^\/agents\/[^/]+\/logs$/.test(path)) {
    await route.fulfill(ok(pageResult(mockRuntimeLogs)));
    return;
  }

  if (method === 'GET' && /^\/agents\/[^/]+$/.test(path)) {
    await route.fulfill(ok(mockAgentDetail));
    return;
  }

  if (method === 'POST' && /^\/agents\/[^/]+\/sync$/.test(path)) {
    await route.fulfill(ok({ status: 'running', lastSyncAt: '2026-07-06 10:40:00', syncError: null }));
    return;
  }

  if ((method === 'POST' || method === 'PUT' || method === 'DELETE') && /^\/agents\/[^/]+/.test(path)) {
    await route.fulfill(ok({ taskId: 'task-e2e', status: 'running' }));
    return;
  }

  if (method === 'GET' && /^\/agent-tasks\/[^/]+$/.test(path)) {
    await route.fulfill(ok({ id: 'task-e2e', status: 'completed', progress: 100 }));
    return;
  }

  if (method === 'POST' && path === '/batch-tasks') {
    await route.fulfill(
      ok({
        id: 'batch-e2e',
        type: 'deploy',
        status: 'running',
        total: 1,
        successCount: 0,
        failedCount: 0,
        skippedCount: 0,
        progress: 5,
        createdAt: '2026-07-06 10:40:00',
      }),
    );
    return;
  }

  if (method === 'POST' && /^\/diagnostics\/[^/]+\/fix$/.test(path)) {
    await route.fulfill(ok({ status: 'completed', output: '自动修复完成', taskId: 'fix-e2e' }));
    return;
  }

  if (method === 'GET' && /^\/share\/[^/]+$/.test(path)) {
    await route.fulfill(ok(mockSharedAgent));
    return;
  }

  if (method === 'GET') {
    await route.fulfill(ok(pageResult([])));
    return;
  }

  await route.fulfill(notFound(`${method} ${path}`));
}

export async function mockAstronClawApi(page: Page) {
  await page.addInitScript((storeData) => {
    window.localStorage.removeItem('astronclaw.accessToken');
    window.__ASTRONCLAW_E2E_STORE__ = storeData;
  }, mockStoreData);

  await page.route(`**${API_PREFIX}/**`, fulfillApi);
}

export async function loginByUi(page: Page, redirect = '/agents') {
  await page.goto(`/login?redirect=${encodeURIComponent(redirect)}`);
  await page.getByLabel('账号', { exact: true }).fill('admin');
  await page.getByLabel('密码', { exact: true }).fill('Admin@123456');
  await page.getByRole('button', { name: '登录' }).click();
  await expect(page).toHaveURL(new RegExp(`${escapeForRegExp(redirect)}(?:$|[?#])`));
}

export const appRouteExpectations = [
  { path: '/agents', heading: '智能体龙虾管理' },
  { path: '/org', heading: '组织架构管理' },
  { path: '/monitoring', heading: '监控管理' },
  { path: '/models', heading: '模型网关' },
  { path: '/security', heading: '安全管理' },
  { path: '/ops', heading: '运维自动化' },
  { path: '/skills', heading: 'Skill 管理' },
  { path: '/knowledge', heading: '知识管理' },
  { path: '/memory', heading: '记忆管理' },
  { path: '/seats', heading: '席位管理' },
  { path: '/sharing', heading: '实例共享' },
  { path: '/channels', heading: '消息渠道管理' },
  { path: '/diagnosis', heading: '问题诊断' },
];
