import { request } from './request';
import type * as ApiTypes from './types';

/** 安全策略接口：访问控制、安全基线与策略状态管理。 */
export const securityApi = {
  /** 查询安全策略列表。 */
  policies(params: Record<string, ApiTypes.QueryValue> = {}) {
    return request<ApiTypes.PageResult<Record<string, unknown>> | Record<string, unknown>[]>('/security-policies', { query: params });
  },
  /** 查询安全策略详情。 */
  policy(policyId: string) {
    return request<Record<string, unknown>>(`/security-policies/${encodeURIComponent(policyId)}`);
  },
  /** 更新安全策略。 */
  updatePolicy(policyId: string, payload: Record<string, unknown>) {
    return request<Record<string, unknown>>(`/security-policies/${encodeURIComponent(policyId)}`, { method: 'PUT', body: JSON.stringify(payload) });
  },
};
