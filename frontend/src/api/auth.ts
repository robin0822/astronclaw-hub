import { clearAstronClawAccessToken, getAstronClawAccessToken, request, setAstronClawAccessToken } from './request';
import type * as ApiTypes from './types';

const AUTH_PROFILE_CACHE_TTL_MS = 60_000;

type AuthProfile = Record<string, unknown>;

let cachedProfile: { tokenKey: string; value: AuthProfile; expiresAt: number } | undefined;
let profileRequest: { tokenKey: string; promise: Promise<AuthProfile> } | undefined;

function currentTokenKey() {
  return getAstronClawAccessToken() || 'cookie-session';
}

function clearProfileCache() {
  cachedProfile = undefined;
  profileRequest = undefined;
}

function rememberProfile(value?: AuthProfile) {
  if (!value) return;
  cachedProfile = {
    tokenKey: currentTokenKey(),
    value,
    expiresAt: Date.now() + AUTH_PROFILE_CACHE_TTL_MS,
  };
}

/** 认证接口：登录、刷新后端会话、退出和当前用户。 */
export const authApi = {
  /** 使用用户名和密码登录；如果后端返回 accessToken，会保存给请求拦截器自动携带。 */
  async login(payload: ApiTypes.AuthLoginPayload) {
    clearProfileCache();
    const result = await request<ApiTypes.AuthLoginResult>('/auth/login', { method: 'POST', body: JSON.stringify(payload) });
    setAstronClawAccessToken(result.accessToken ?? result.token ?? null);
    if (result.user && typeof result.user === 'object') rememberProfile(result.user as AuthProfile);
    return result;
  },
  /** 刷新当前后端会话；如果返回新 token，同步更新本地认证态。 */
  async refresh() {
    clearProfileCache();
    const result = await request<ApiTypes.AuthLoginResult>('/auth/refresh', { method: 'POST' });
    setAstronClawAccessToken(result.accessToken ?? result.token ?? null);
    if (result.user && typeof result.user === 'object') rememberProfile(result.user as AuthProfile);
    return result;
  },
  /** 退出当前后端会话，并清理本地 accessToken。 */
  async logout() {
    try {
      return await request<Record<string, unknown>>('/auth/logout', { method: 'POST' });
    } finally {
      clearProfileCache();
      clearAstronClawAccessToken();
    }
  },
  /** 查询当前用户基础信息；同一 token 下短时间内复用结果，避免刷新或路由切换重复请求。 */
  me() {
    const tokenKey = currentTokenKey();
    if (cachedProfile?.tokenKey === tokenKey && cachedProfile.expiresAt > Date.now()) return Promise.resolve(cachedProfile.value);
    if (profileRequest?.tokenKey === tokenKey) return profileRequest.promise;

    const promise = request<AuthProfile>('/me')
      .then((profile) => {
        cachedProfile = { tokenKey, value: profile, expiresAt: Date.now() + AUTH_PROFILE_CACHE_TTL_MS };
        return profile;
      })
      .finally(() => {
        if (profileRequest?.tokenKey === tokenKey) profileRequest = undefined;
      });
    profileRequest = { tokenKey, promise };
    return promise;
  },
  /** 查询当前用户角色和权限。 */
  mePermissions() {
    return request<Record<string, unknown>>('/me/permissions');
  },
  /** 查询可用 SSO Provider。 */
  ssoProviders() {
    return request<ApiTypes.PageResult<Record<string, unknown>> | Record<string, unknown>[]>('/sso/providers');
  },
  /** 新建 SSO Provider。 */
  createSsoProvider(payload: Record<string, unknown>) {
    return request<Record<string, unknown>>('/sso/providers', { method: 'POST', body: JSON.stringify(payload) });
  },
  /** 更新 SSO Provider。 */
  updateSsoProvider(providerId: string, payload: Record<string, unknown>) {
    return request<Record<string, unknown>>(`/sso/providers/${encodeURIComponent(providerId)}`, { method: 'PUT', body: JSON.stringify(payload) });
  },
  /** 获取客户侧 SSO 登录地址或触发 SSO 登录。 */
  ssoLogin(provider = 'customer') {
    return request<Record<string, unknown>>('/auth/sso/login', { query: { provider } });
  },
  /** 处理客户侧 SSO 回调。 */
  ssoCallback(provider = 'customer') {
    return request<Record<string, unknown>>('/auth/sso/callback', { query: { provider } });
  },
  /** 退出客户侧 SSO 会话。 */
  ssoLogout() {
    return request<Record<string, unknown>>('/auth/sso/logout', { method: 'POST' });
  },
};
