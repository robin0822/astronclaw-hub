import { request } from './request';
import type * as ApiTypes from './types';

/** 诊断知识库接口：知识条目和诊断决策树。 */
export const diagnosisKbApi = {
  /** 查询诊断知识条目列表。 */
  list(params: Record<string, ApiTypes.QueryValue> = {}) {
    return request<ApiTypes.PageResult<Record<string, unknown>>>('/diagnosis-kb', { query: params });
  },
  /** 创建诊断知识条目。 */
  create(payload: Record<string, unknown>) {
    return request<Record<string, unknown>>('/diagnosis-kb', { method: 'POST', body: JSON.stringify(payload) });
  },
  /** 更新诊断知识条目。 */
  update(entryId: string, payload: Record<string, unknown>) {
    return request<Record<string, unknown>>(`/diagnosis-kb/${encodeURIComponent(entryId)}`, { method: 'PUT', body: JSON.stringify(payload) });
  },
  /** 删除诊断知识条目。 */
  remove(entryId: string) {
    return request<Record<string, unknown>>(`/diagnosis-kb/${encodeURIComponent(entryId)}`, { method: 'DELETE' });
  },
  /** 从诊断记录生成知识条目。 */
  createFromDiagnosis(diagnosisId: string, payload: Record<string, unknown> = {}) {
    return request<Record<string, unknown>>(`/diagnosis-kb/from-diagnosis/${encodeURIComponent(diagnosisId)}`, { method: 'POST', body: JSON.stringify(payload) });
  },
  /** 查询诊断决策树列表。 */
  decisionTrees() {
    return request<ApiTypes.PageResult<Record<string, unknown>> | Record<string, unknown>[]>('/diagnosis-decision-trees');
  },
  /** 创建诊断决策树。 */
  createDecisionTree(payload: Record<string, unknown>) {
    return request<Record<string, unknown>>('/diagnosis-decision-trees', { method: 'POST', body: JSON.stringify(payload) });
  },
  /** 更新诊断决策树。 */
  updateDecisionTree(treeId: string, payload: Record<string, unknown>) {
    return request<Record<string, unknown>>(`/diagnosis-decision-trees/${encodeURIComponent(treeId)}`, { method: 'PUT', body: JSON.stringify(payload) });
  },
};
