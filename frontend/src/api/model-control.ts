import { request } from './request';
import type * as ApiTypes from './types';

/** 模型治理接口：额度、路由策略和策略命中记录。 */
export const modelControlApi = {
  /** 查询模型额度规则列表。 */
  quotas() {
    return request<ApiTypes.PageResult<Record<string, unknown>> | Record<string, unknown>[]>('/model-quotas');
  },
  /** 创建模型额度规则。 */
  createQuota(payload: Record<string, unknown>) {
    return request<Record<string, unknown>>('/model-quotas', { method: 'POST', body: JSON.stringify(payload) });
  },
  /** 更新模型额度规则。 */
  updateQuota(quotaId: string, payload: Record<string, unknown>) {
    return request<Record<string, unknown>>(`/model-quotas/${encodeURIComponent(quotaId)}`, { method: 'PUT', body: JSON.stringify(payload) });
  },
  /** 删除模型额度规则。 */
  deleteQuota(quotaId: string) {
    return request<Record<string, unknown>>(`/model-quotas/${encodeURIComponent(quotaId)}`, { method: 'DELETE' });
  },
  /** 查询模型路由策略列表。 */
  routePolicies() {
    return request<ApiTypes.PageResult<Record<string, unknown>> | Record<string, unknown>[]>('/model-route-policies');
  },
  /** 创建模型路由策略。 */
  createRoutePolicy(payload: Record<string, unknown>) {
    return request<Record<string, unknown>>('/model-route-policies', { method: 'POST', body: JSON.stringify(payload) });
  },
  /** 更新模型路由策略。 */
  updateRoutePolicy(policyId: string, payload: Record<string, unknown>) {
    return request<Record<string, unknown>>(`/model-route-policies/${encodeURIComponent(policyId)}`, { method: 'PUT', body: JSON.stringify(payload) });
  },
  /** 删除模型路由策略。 */
  deleteRoutePolicy(policyId: string) {
    return request<Record<string, unknown>>(`/model-route-policies/${encodeURIComponent(policyId)}`, { method: 'DELETE' });
  },
  /** 查询路由策略命中记录。 */
  policyHits(params: Record<string, ApiTypes.QueryValue> = {}) {
    return request<ApiTypes.PageResult<Record<string, unknown>>>('/model-policy-hits', { query: params });
  },
};
