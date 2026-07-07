import { http } from 'msw';
import { describe, expect, it } from 'vitest';
import { agentsApi } from '../agents';
import { astronClawHttp, createLoginRedirectUrl, setAstronClawAccessToken, setAuthRedirectHandler } from '../request';
import { apiUrl, fail, ok, server } from '../../test/server';

const emptyPage = { items: [], page: 1, pageSize: 20, total: 0 };

describe('AstronClaw request', () => {
  it('默认保留 cookie 能力，并在存在 accessToken 时注入 Authorization', async () => {
    setAstronClawAccessToken('unit-access-token');
    let authorization: string | null = 'unset';
    server.use(
      http.get(apiUrl('/agents'), ({ request }) => {
        authorization = request.headers.get('authorization');
        return ok(emptyPage);
      }),
    );

    await agentsApi.list({ page: 1, pageSize: 20 });

    expect(astronClawHttp.defaults.withCredentials).toBe(true);
    expect(authorization).toBe('Bearer unit-access-token');
  });

  it('401 响应会交给统一登录跳转处理', async () => {
    const redirects: string[] = [];
    window.history.pushState(null, '', '/agents?status=running#detail');
    setAuthRedirectHandler((url) => redirects.push(url));
    server.use(http.get(apiUrl('/agents'), () => fail(401, 401001, '登录已失效')));

    await expect(agentsApi.list({ page: 1 })).rejects.toMatchObject({ code: 401001, httpStatus: 401 });

    expect(redirects).toEqual([createLoginRedirectUrl('/agents', '?status=running', '#detail')]);
  });
});
