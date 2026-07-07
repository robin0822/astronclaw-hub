import { request } from './request';
import type * as ApiTypes from './types';

/** 分享授权接口：创建、查询和移除智能体分享授权。 */
export const shareGrantsApi = {
  /** 创建智能体分享授权。 */
  create(agentId: string, payload: ApiTypes.ShareGrantPayload) {
    return request<Record<string, unknown>>(`/agents/${encodeURIComponent(agentId)}/share-grants`, { method: 'POST', body: JSON.stringify(payload) });
  },
  /** 查询智能体分享授权列表。 */
  list(agentId: string) {
    return request<ApiTypes.PageResult<Record<string, unknown>> | Record<string, unknown>>(`/agents/${encodeURIComponent(agentId)}/share-grants`);
  },
  /** 移除智能体分享授权。 */
  remove(agentId: string, grantId: string) {
    return request<Record<string, unknown>>(`/agents/${encodeURIComponent(agentId)}/share-grants/${encodeURIComponent(grantId)}`, { method: 'DELETE' });
  },
};
