import { request } from './request';
import type * as ApiTypes from './types';

/** 同步任务接口：实例同步任务创建与进度查询。 */
export const syncJobsApi = {
  /** 创建同步任务。 */
  create(payload: Record<string, unknown>) {
    return request<Record<string, unknown>>('/sync-jobs', { method: 'POST', body: JSON.stringify(payload) });
  },
  /** 查询同步任务列表。 */
  list(params: Record<string, ApiTypes.QueryValue> = {}) {
    return request<ApiTypes.PageResult<Record<string, unknown>>>('/sync-jobs', { query: params });
  },
  /** 查询同步任务详情。 */
  detail(jobId: string) {
    return request<Record<string, unknown>>(`/sync-jobs/${encodeURIComponent(jobId)}`);
  },
};
