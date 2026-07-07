import { request } from './request';
import type * as ApiTypes from './types';

/** 席位接口：席位套餐、分配、删除和转移。 */
export const seatsApi = {
  /** 查询席位套餐列表。 */
  packages() {
    return request<ApiTypes.PageResult<Record<string, unknown>> | Record<string, unknown>[]>('/seat-packages');
  },
  /** 创建席位套餐。 */
  createPackage(payload: Record<string, unknown>) {
    return request<Record<string, unknown>>('/seat-packages', { method: 'POST', body: JSON.stringify(payload) });
  },
  /** 查询席位分配列表。 */
  assignments(params: Record<string, ApiTypes.QueryValue> = {}) {
    return request<ApiTypes.PageResult<Record<string, unknown>>>('/seat-assignments', { query: params });
  },
  /** 查询席位事件。 */
  events(params: Record<string, ApiTypes.QueryValue> = {}) {
    return request<ApiTypes.PageResult<Record<string, unknown>>>('/seat-events', { query: params });
  },
  /** 创建席位分配。 */
  createAssignment(payload: Record<string, unknown>) {
    return request<Record<string, unknown>>('/seat-assignments', { method: 'POST', body: JSON.stringify(payload) });
  },
  /** 删除席位分配。 */
  deleteAssignment(assignmentId: string) {
    return request<Record<string, unknown>>(`/seat-assignments/${encodeURIComponent(assignmentId)}`, { method: 'DELETE' });
  },
  /** 转移席位分配。 */
  transferAssignment(assignmentId: string, payload: Record<string, unknown>) {
    return request<Record<string, unknown>>(`/seat-assignments/${encodeURIComponent(assignmentId)}/transfer`, { method: 'POST', body: JSON.stringify(payload) });
  },
};
