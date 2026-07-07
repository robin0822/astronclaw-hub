import { http, HttpResponse, type HttpHandler } from 'msw';
import { setupServer } from 'msw/node';

export const apiUrl = (path: string) => `*/api/v1/astron-claw${path}`;

export function ok<T>(data: T) {
  return HttpResponse.json({ code: 0, message: 'success', data, requestId: 'test-request' });
}

export function fail(status: number, code: number, message: string) {
  return HttpResponse.json({ code, message, data: null, requestId: 'test-request' }, { status });
}

export const handlers: HttpHandler[] = [
  http.post(apiUrl('/auth/login'), async () => ok({ accessToken: 'test-access-token', user: { username: 'admin', name: '平台管理员' } })),
  http.post(apiUrl('/auth/logout'), () => ok({})),
  http.get(apiUrl('/me'), () => ok({ username: 'admin', name: '平台管理员' })),
  http.get(apiUrl('/agents'), () => ok({ items: [], page: 1, pageSize: 20, total: 0 })),
];

export const server = setupServer(...handlers);
