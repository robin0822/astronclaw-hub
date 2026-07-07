import { request } from './request';
import type * as ApiTypes from './types';

/** 告警接口：查询运行告警和处理告警动作。 */
export const alertsApi = {
  /** 查询运行告警列表。 */
  list(params: Record<string, ApiTypes.QueryValue> = {}) {
    return request<ApiTypes.PageResult<Record<string, unknown>>>('/alerts', { query: params });
  },
  /** 查询告警详情。 */
  detail(alertId: string) {
    return request<Record<string, unknown>>(`/alerts/${encodeURIComponent(alertId)}`);
  },
  /** 认领告警。 */
  claim(alertId: string, payload: Record<string, unknown> = {}) {
    return request<Record<string, unknown>>(`/alerts/${encodeURIComponent(alertId)}/claim`, { method: 'POST', body: JSON.stringify(payload) });
  },
  /** 处理告警。 */
  process(alertId: string, payload: Record<string, unknown> = {}) {
    return request<Record<string, unknown>>(`/alerts/${encodeURIComponent(alertId)}/process`, { method: 'POST', body: JSON.stringify(payload) });
  },
  /** 转派告警。 */
  transfer(alertId: string, payload: Record<string, unknown>) {
    return request<Record<string, unknown>>(`/alerts/${encodeURIComponent(alertId)}/transfer`, { method: 'POST', body: JSON.stringify(payload) });
  },
  /** 挂起告警。 */
  suspend(alertId: string, payload: Record<string, unknown> = {}) {
    return request<Record<string, unknown>>(`/alerts/${encodeURIComponent(alertId)}/suspend`, { method: 'POST', body: JSON.stringify(payload) });
  },
  /** 关闭告警。 */
  close(alertId: string, payload: Record<string, unknown> = {}) {
    return request<Record<string, unknown>>(`/alerts/${encodeURIComponent(alertId)}/close`, { method: 'POST', body: JSON.stringify(payload) });
  },
};
