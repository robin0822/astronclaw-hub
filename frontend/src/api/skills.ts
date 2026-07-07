import { request } from './request';
import type * as ApiTypes from './types';

/** 技能接口：Skill 管理，以及为智能体安装或卸载 Skill。 */
export const skillsApi = {
  /** 查询 Skill 列表。 */
  list(params: Record<string, ApiTypes.QueryValue> = {}) {
    return request<ApiTypes.PageResult<Record<string, unknown>>>('/skills', { query: params });
  },
  /** 创建 Skill。 */
  create(payload: Record<string, unknown>) {
    return request<Record<string, unknown>>('/skills', { method: 'POST', body: JSON.stringify(payload) });
  },
  /** 导入 Skill，支持 FormData 或 JSON 元数据。 */
  import(payload: FormData | Record<string, unknown>) {
    return request<Record<string, unknown>>('/skills/import', { method: 'POST', body: payload instanceof FormData ? payload : JSON.stringify(payload) });
  },
  /** 查询 Skill 详情。 */
  detail(skillId: string) {
    return request<Record<string, unknown>>(`/skills/${encodeURIComponent(skillId)}`);
  },
  /** 更新 Skill。 */
  update(skillId: string, payload: Record<string, unknown>) {
    return request<Record<string, unknown>>(`/skills/${encodeURIComponent(skillId)}`, { method: 'PUT', body: JSON.stringify(payload) });
  },
  /** 提交或处理 Skill 审核。 */
  review(skillId: string, payload: Record<string, unknown>) {
    return request<Record<string, unknown>>(`/skills/${encodeURIComponent(skillId)}/review`, { method: 'POST', body: JSON.stringify(payload) });
  },
  /** 为智能体安装 Skill。 */
  install(agentId: string, skillId: string) {
    return request<ApiTypes.TaskResult>(`/agents/${encodeURIComponent(agentId)}/skills/${encodeURIComponent(skillId)}/install`, { method: 'POST' });
  },
  /** 从智能体卸载 Skill。 */
  uninstall(agentId: string, skillId: string) {
    return request<ApiTypes.TaskResult>(`/agents/${encodeURIComponent(agentId)}/skills/${encodeURIComponent(skillId)}/uninstall`, { method: 'POST' });
  },
};
