import { expect, test, type APIRequestContext } from '@playwright/test';
import { apiContractGroups, type ApiContractCase } from './api-contract-cases';

const API_PREFIX = '/api/v1/astron-claw';
const ENABLE_API_CONTRACT = process.env.E2E_ENABLE_API_CONTRACT === '1';
const ENABLE_MUTATING = process.env.E2E_ENABLE_MUTATING_API_TESTS === '1';
const ENABLE_DOWNLOADS = process.env.E2E_ENABLE_DOWNLOAD_API_TESTS === '1';
const ENABLE_DEV = process.env.E2E_ENABLE_DEV_API_TESTS === '1';

const loginAccount = {
  username: process.env.E2E_USERNAME ?? 'admin',
  password: process.env.E2E_PASSWORD ?? 'Admin@123456',
};

const defaultPathValues: Record<string, string> = {
  agent_id: 'agent-e2e',
  alert_id: 'alert-e2e',
  approval_id: 'approval-e2e',
  batch_id: 'batch-e2e',
  channel_id: 'channel-e2e',
  config_id: 'config-e2e',
  cost_id: 'cost-e2e',
  file_id: 'file-e2e',
  grant_id: 'grant-e2e',
  job_id: 'job-e2e',
  kb_id: 'kb-e2e',
  memory_id: 'memory-e2e',
  model_id: 'model-e2e',
  notification_id: 'notification-e2e',
  policy_id: 'policy-e2e',
  position_id: 'position-e2e',
  provider_id: 'provider-e2e',
  quota_id: 'quota-e2e',
  role_id: 'role-e2e',
  rule_id: 'rule-e2e',
  share_id: 'share-e2e',
  skill_id: 'skill-e2e',
  task_id: 'task-e2e',
  tree_id: 'tree-e2e',
  user_id: 'user-e2e',
};

const defaultQueryValues: Record<string, string> = {
  page: '1',
  pageSize: '20',
  provider: 'customer',
  subject: 'e2e-subject',
  username: loginAccount.username,
};

let tokenPromise: Promise<string | undefined> | undefined;

async function getAccessToken(request: APIRequestContext) {
  tokenPromise ??= request.post(`${API_PREFIX}/auth/login`, { data: loginAccount }).then(async (response) => {
    expect(response.status(), '登录接口不应返回 5xx').toBeLessThan(500);
    const body = await response.json();
    expect(body).toHaveProperty('code');
    if (body.code !== 0) throw new Error(`登录失败：${body.message ?? body.code}`);
    return body.data?.accessToken ?? body.data?.token;
  });
  return tokenPromise;
}

function envNameForPathParam(name: string) {
  return `E2E_${name.replace(/_id$/, '').toUpperCase()}_ID`;
}

function resolvePath(path: string) {
  return path.replace(/\{([^}]+)\}/g, (_, name: string) => encodeURIComponent(process.env[envNameForPathParam(name)] ?? defaultPathValues[name] ?? `${name}-e2e`));
}

function buildQuery(testCase: ApiContractCase) {
  const searchParams = new URLSearchParams();
  for (const rawName of testCase.query) {
    const required = rawName.endsWith('*');
    const name = rawName.replace(/\*$/, '');
    const value = defaultQueryValues[name];
    if (value !== undefined && (required || name === 'page' || name === 'pageSize' || testCase.path.includes('/auth/sso/'))) {
      searchParams.set(name, value);
    }
  }
  const query = searchParams.toString();
  return query ? `?${query}` : '';
}

function requestPath(testCase: ApiContractCase) {
  const path = `${resolvePath(testCase.path)}${buildQuery(testCase)}`;
  return testCase.path === '/health' ? path : `${API_PREFIX}${path}`;
}

function shouldRunCase(testCase: ApiContractCase) {
  if (!ENABLE_API_CONTRACT) return false;
  if (testCase.devOnly && !ENABLE_DEV) return false;
  if (testCase.download && !ENABLE_DOWNLOADS) return false;
  if (testCase.mutating && !ENABLE_MUTATING) return false;
  return testCase.method === 'GET' || ENABLE_MUTATING;
}

async function expectUnifiedJsonResponse(responseBody: unknown) {
  expect(responseBody).toEqual(
    expect.objectContaining({
      code: expect.any(Number),
    }),
  );
}

test.describe('后端接口契约', () => {
  test.skip(!ENABLE_API_CONTRACT, '设置 E2E_ENABLE_API_CONTRACT=1 后才会连接真实后端代理执行接口契约测试');

  for (const group of apiContractGroups) {
    test.describe(group.name, () => {
      for (const testCase of group.cases) {
        const runnable = shouldRunCase(testCase);
        const label = `${testCase.method} ${testCase.path} ${testCase.summary}`;

        test(label, async ({ request }) => {
          test.skip(!runnable, '该接口默认跳过：写操作、下载或开发辅助接口需要显式开启环境变量');

          const accessToken = await getAccessToken(request);
          const response = await request.fetch(requestPath(testCase), {
            method: testCase.method,
            headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : undefined,
            data: testCase.body ? {} : undefined,
          });

          expect(response.status(), `${label} 不应返回 5xx`).toBeLessThan(500);

          const contentType = response.headers()['content-type'] ?? '';
          if (contentType.includes('application/json') || contentType.includes('+json')) {
            await expectUnifiedJsonResponse(await response.json());
          }
        });
      }
    });
  }
});
