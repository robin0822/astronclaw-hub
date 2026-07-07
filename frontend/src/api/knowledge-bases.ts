import { request } from './request';
import type * as ApiTypes from './types';

/** 知识库接口：知识库、文件，以及与智能体绑定或解绑。 */
export const knowledgeBasesApi = {
  /** 查询知识库列表。 */
  list(params: Record<string, ApiTypes.QueryValue> = {}) {
    return request<ApiTypes.PageResult<Record<string, unknown>>>('/knowledge-bases', { query: params });
  },
  /** 创建知识库。 */
  create(payload: Record<string, unknown>) {
    return request<Record<string, unknown>>('/knowledge-bases', { method: 'POST', body: JSON.stringify(payload) });
  },
  /** 查询知识库文件列表。 */
  files(knowledgeBaseId: string, params: Record<string, ApiTypes.QueryValue> = {}) {
    return request<ApiTypes.PageResult<Record<string, unknown>> | Record<string, unknown>[]>(`/knowledge-bases/${encodeURIComponent(knowledgeBaseId)}/files`, { query: params });
  },
  /** 上传知识库文件。 */
  uploadFile(knowledgeBaseId: string, payload: FormData | Record<string, unknown>) {
    return request<Record<string, unknown>>(`/knowledge-bases/${encodeURIComponent(knowledgeBaseId)}/files`, {
      method: 'POST',
      body: payload instanceof FormData ? payload : JSON.stringify(payload),
    });
  },
  /** 删除知识库文件。 */
  deleteFile(fileId: string) {
    return request<Record<string, unknown>>(`/knowledge-files/${encodeURIComponent(fileId)}`, { method: 'DELETE' });
  },
  /** 重建知识库文件索引。 */
  reindexFile(fileId: string) {
    return request<Record<string, unknown>>(`/knowledge-files/${encodeURIComponent(fileId)}/reindex`, { method: 'POST' });
  },
  /** 将知识库绑定到智能体。 */
  bind(agentId: string, knowledgeBaseId: string) {
    return request<ApiTypes.TaskResult>(`/agents/${encodeURIComponent(agentId)}/knowledge-bases/${encodeURIComponent(knowledgeBaseId)}/bind`, { method: 'POST' });
  },
  /** 将知识库从智能体解绑。 */
  unbind(agentId: string, knowledgeBaseId: string) {
    return request<ApiTypes.TaskResult>(`/agents/${encodeURIComponent(agentId)}/knowledge-bases/${encodeURIComponent(knowledgeBaseId)}/bind`, { method: 'DELETE' });
  },
};
