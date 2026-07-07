import { request } from './request';
import type * as ApiTypes from './types';

/** 业务系统接口：业务系统及其关联智能体范围。 */
export const businessSystemsApi = {
  /** 查询业务系统列表。 */
  list() {
    return request<ApiTypes.PageResult<Record<string, unknown>> | Record<string, unknown>[]>('/business-systems');
  },
  /** 创建业务系统。 */
  create(payload: Record<string, unknown>) {
    return request<Record<string, unknown>>('/business-systems', { method: 'POST', body: JSON.stringify(payload) });
  },
  /** 更新业务系统关联的智能体。 */
  updateAgents(systemId: string, payload: Record<string, unknown>) {
    return request<Record<string, unknown>>(`/business-systems/${encodeURIComponent(systemId)}/agents`, { method: 'PUT', body: JSON.stringify(payload) });
  },
};
