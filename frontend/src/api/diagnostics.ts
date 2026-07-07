import { request } from './request';
import type * as ApiTypes from './types';

/** 诊断接口：诊断记录、修复、巡检任务和巡检运行。 */
export const diagnosticsApi = {
  /** 查询诊断记录列表。 */
  list(params: Record<string, ApiTypes.QueryValue> = {}) {
    return request<ApiTypes.PageResult<Record<string, unknown>>>('/diagnostics', { query: params });
  },
  /** 查询诊断详情。 */
  detail(diagnosisId: string) {
    return request<Record<string, unknown>>(`/diagnostics/${encodeURIComponent(diagnosisId)}`);
  },
  /** 触发自动诊断修复。 */
  fix(diagnosisId: string) {
    return request<{ status?: string; output?: string; taskId?: string; fixTaskId?: string }>(`/diagnostics/${encodeURIComponent(diagnosisId)}/fix`, { method: 'POST' });
  },
  /** 查询巡检任务。 */
  inspectionTasks(params: Record<string, ApiTypes.QueryValue> = {}) {
    return request<ApiTypes.PageResult<Record<string, unknown>> | Record<string, unknown>[]>('/inspection-tasks', { query: params });
  },
  /** 创建巡检任务。 */
  createInspectionTask(payload: Record<string, unknown>) {
    return request<Record<string, unknown>>('/inspection-tasks', { method: 'POST', body: JSON.stringify(payload) });
  },
  /** 运行巡检任务。 */
  runInspectionTask(taskId: string, payload: Record<string, unknown> = {}) {
    return request<Record<string, unknown>>(`/inspection-tasks/${encodeURIComponent(taskId)}/run`, { method: 'POST', body: JSON.stringify(payload) });
  },
  /** 查询巡检运行详情。 */
  inspectionRun(runId: string) {
    return request<Record<string, unknown>>(`/inspection-runs/${encodeURIComponent(runId)}`);
  },
  /** 导出巡检运行结果。 */
  exportInspectionRun(runId: string) {
    return request<{ downloadUrl?: string } | Blob>(`/inspection-runs/${encodeURIComponent(runId)}/export`, { responseType: 'blob' });
  },
};
