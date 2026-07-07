import { request } from './request';
import type * as ApiTypes from './types';

/** 模型接口：模型管理、启停探测和调用日志。 */
export const modelsApi = {
  /** 查询模型列表。 */
  list(params: Record<string, ApiTypes.QueryValue> = {}) {
    return request<ApiTypes.PageResult<Record<string, unknown>>>('/models', { query: params });
  },
  /** 创建模型。 */
  create(payload: Record<string, unknown>) {
    return request<Record<string, unknown>>('/models', { method: 'POST', body: JSON.stringify(payload) });
  },
  /** 更新模型。 */
  update(modelId: string, payload: Record<string, unknown>) {
    return request<Record<string, unknown>>(`/models/${encodeURIComponent(modelId)}`, { method: 'PUT', body: JSON.stringify(payload) });
  },
  /** 启用模型。 */
  enable(modelId: string) {
    return request<Record<string, unknown>>(`/models/${encodeURIComponent(modelId)}/enable`, { method: 'POST' });
  },
  /** 禁用模型。 */
  disable(modelId: string) {
    return request<Record<string, unknown>>(`/models/${encodeURIComponent(modelId)}/disable`, { method: 'POST' });
  },
  /** 探测模型连接或可用性。 */
  probe(modelId: string) {
    return request<Record<string, unknown>>(`/models/${encodeURIComponent(modelId)}/probe`, { method: 'POST' });
  },
  /** 查询模型调用日志。 */
  callLogs(params: Record<string, ApiTypes.QueryValue> = {}) {
    return request<ApiTypes.PageResult<Record<string, unknown>>>('/model-call-logs', { query: params });
  },
};
