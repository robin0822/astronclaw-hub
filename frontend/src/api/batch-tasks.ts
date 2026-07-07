import { request } from './request';
import type * as ApiTypes from './types';

/** 批量任务接口：创建、查询和导出批量操作任务。 */
export const batchTasksApi = {
  /** 创建批量操作任务。 */
  create(payload: ApiTypes.BatchTaskPayload) {
    return request<ApiTypes.BatchTask>('/batch-tasks', { method: 'POST', body: JSON.stringify(payload) });
  },
  /** 查询批量任务汇总状态。 */
  detail(batchTaskId: string) {
    return request<ApiTypes.BatchTask>(`/batch-tasks/${encodeURIComponent(batchTaskId)}`);
  },
  /** 查询批量任务明细结果。 */
  items(batchTaskId: string, params: { page?: number; pageSize?: number } = {}) {
    return request<ApiTypes.PageResult<Record<string, unknown>>>(`/batch-tasks/${encodeURIComponent(batchTaskId)}/items`, { query: params });
  },
  /** 导出批量任务结果文件。 */
  exportResult(batchTaskId: string) {
    return request<{ downloadUrl?: string } | Blob>(`/batch-tasks/${encodeURIComponent(batchTaskId)}/export`, { responseType: 'blob' });
  },
};
