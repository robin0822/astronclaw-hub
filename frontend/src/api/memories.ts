import { request } from './request';
import type * as ApiTypes from './types';

/** 记忆接口：查询、创建、更新、删除和分享记忆。 */
export const memoriesApi = {
  /** 查询记忆记录列表。 */
  list(params: Record<string, ApiTypes.QueryValue> = {}) {
    return request<ApiTypes.PageResult<Record<string, unknown>>>('/memories', { query: params });
  },
  /** 创建记忆记录。 */
  create(payload: Record<string, unknown>) {
    return request<Record<string, unknown>>('/memories', { method: 'POST', body: JSON.stringify(payload) });
  },
  /** 更新记忆记录。 */
  update(memoryId: string, payload: Record<string, unknown>) {
    return request<Record<string, unknown>>(`/memories/${encodeURIComponent(memoryId)}`, { method: 'PUT', body: JSON.stringify(payload) });
  },
  /** 删除记忆记录。 */
  remove(memoryId: string) {
    return request<Record<string, unknown>>(`/memories/${encodeURIComponent(memoryId)}`, { method: 'DELETE' });
  },
  /** 分享记忆记录。 */
  share(memoryId: string, payload: Record<string, unknown> = {}) {
    return request<Record<string, unknown>>(`/memories/${encodeURIComponent(memoryId)}/share`, { method: 'POST', body: JSON.stringify(payload) });
  },
};
