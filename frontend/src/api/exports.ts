import { request } from './request';
import type * as ApiTypes from './types';

/** 导出任务接口：查询导出任务、元信息和下载内容。 */
export const exportsApi = {
  /** 查询导出任务列表。 */
  list(params: Record<string, ApiTypes.QueryValue> = {}) {
    return request<ApiTypes.PageResult<Record<string, unknown>>>('/exports', { query: params });
  },
  /** 查询导出任务详情。 */
  detail(exportKey: string) {
    return request<Record<string, unknown>>(`/exports/${encodeURIComponent(exportKey)}`);
  },
  /** 下载导出结果。 */
  download(exportKey: string) {
    return request<{ downloadUrl?: string } | Blob>(`/exports/${encodeURIComponent(exportKey)}/download`, { responseType: 'blob' });
  },
};
