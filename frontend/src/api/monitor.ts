import { request } from './request';
import type * as ApiTypes from './types';

/** 监控接口：查询运行总览、指标和告警规则。 */
export const monitorApi = {
  /** 查询监控总览。 */
  overview(params: Record<string, ApiTypes.QueryValue> = {}) {
    return request<Record<string, unknown>>('/monitor/overview', { query: params });
  },
  /** 查询监控指标。 */
  metrics(params: Record<string, ApiTypes.QueryValue> = {}) {
    return request<ApiTypes.PageResult<Record<string, unknown>>>('/monitor/metrics', { query: params });
  },
  /** 写入监控指标。 */
  createMetric(payload: Record<string, unknown>) {
    return request<Record<string, unknown>>('/monitor/metrics', { method: 'POST', body: JSON.stringify(payload) });
  },
  /** 查询告警规则。 */
  alertRules(params: Record<string, ApiTypes.QueryValue> = {}) {
    return request<ApiTypes.PageResult<Record<string, unknown>>>('/alert-rules', { query: params });
  },
  /** 创建告警规则。 */
  createAlertRule(payload: Record<string, unknown>) {
    return request<Record<string, unknown>>('/alert-rules', { method: 'POST', body: JSON.stringify(payload) });
  },
  /** 更新告警规则。 */
  updateAlertRule(ruleId: string, payload: Record<string, unknown>) {
    return request<Record<string, unknown>>(`/alert-rules/${encodeURIComponent(ruleId)}`, { method: 'PUT', body: JSON.stringify(payload) });
  },
};
