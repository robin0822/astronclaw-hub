import { request } from './request';
import type * as ApiTypes from './types';

/** 审批接口：创建、查询、通过和驳回审批单。 */
export const approvalsApi = {
  /** 创建审批单。 */
  create(payload: ApiTypes.ApprovalPayload) {
    return request<Record<string, unknown>>('/approvals', { method: 'POST', body: JSON.stringify(payload) });
  },
  /** 查询审批单列表。 */
  list(params: Record<string, ApiTypes.QueryValue> = {}) {
    return request<ApiTypes.PageResult<Record<string, unknown>>>('/approvals', { query: params });
  },
  /** 查询审批单详情。 */
  detail(approvalId: string) {
    return request<Record<string, unknown>>(`/approvals/${encodeURIComponent(approvalId)}`);
  },
  /** 通过审批单。 */
  approve(approvalId: string, payload: Record<string, unknown> = {}) {
    return request<Record<string, unknown>>(`/approvals/${encodeURIComponent(approvalId)}/approve`, { method: 'POST', body: JSON.stringify(payload) });
  },
  /** 驳回审批单。 */
  reject(approvalId: string, payload: Record<string, unknown> = {}) {
    return request<Record<string, unknown>>(`/approvals/${encodeURIComponent(approvalId)}/reject`, { method: 'POST', body: JSON.stringify(payload) });
  },
};
