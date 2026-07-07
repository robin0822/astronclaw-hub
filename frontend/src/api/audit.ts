import { request } from './request';
import type * as ApiTypes from './types';

/** 审计接口：操作日志、登录日志、模型调用日志和审计导出。 */
export const auditApi = {
  /** 查询操作审计日志。 */
  operationLogs(params: Record<string, ApiTypes.QueryValue> = {}) {
    return request<ApiTypes.PageResult<Record<string, unknown>>>('/audit/operation-logs', { query: params });
  },
  /** 查询登录审计日志。 */
  loginLogs(params: Record<string, ApiTypes.QueryValue> = {}) {
    return request<ApiTypes.PageResult<Record<string, unknown>>>('/audit/login-logs', { query: params });
  },
  /** 查询模型调用审计日志。 */
  modelCallLogs(params: Record<string, ApiTypes.QueryValue> = {}) {
    return request<ApiTypes.PageResult<Record<string, unknown>>>('/audit/model-call-logs', { query: params });
  },
  /** 导出审计日志。 */
  export(params: Record<string, ApiTypes.QueryValue> = {}) {
    return request<{ downloadUrl?: string } | Blob>('/audit/export', { query: params, responseType: 'blob' });
  },
};
