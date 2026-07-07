import { request } from './request';
import type * as ApiTypes from './types';

/** 组织权限接口：部门、岗位、用户、角色、权限和组织同步。 */
export const orgApi = {
  /** 查询组织部门树。 */
  departmentsTree() {
    return request<Record<string, unknown>[]>('/org/departments/tree');
  },
  /** 查询组织用户列表。 */
  users(params: Record<string, ApiTypes.QueryValue> = {}) {
    return request<ApiTypes.PageResult<Record<string, unknown>>>('/org/users', { query: params });
  },
  /** 更新用户状态。 */
  updateUserStatus(userId: string, payload: Record<string, unknown>) {
    return request<Record<string, unknown>>(`/org/users/${encodeURIComponent(userId)}/status`, { method: 'PUT', body: JSON.stringify(payload) });
  },
  /** 重置用户密码。 */
  resetUserPassword(userId: string, payload: { newPassword: string; reason?: string }) {
    return request<Record<string, unknown>>(`/org/users/${encodeURIComponent(userId)}/password-reset`, { method: 'POST', body: JSON.stringify(payload) });
  },
  /** 查询岗位。 */
  positions(params: Record<string, ApiTypes.QueryValue> = {}) {
    return request<ApiTypes.PageResult<Record<string, unknown>> | Record<string, unknown>[]>('/org/positions', { query: params });
  },
  /** 新建岗位。 */
  createPosition(payload: Record<string, unknown>) {
    return request<Record<string, unknown>>('/org/positions', { method: 'POST', body: JSON.stringify(payload) });
  },
  /** 更新岗位。 */
  updatePosition(positionId: string, payload: Record<string, unknown>) {
    return request<Record<string, unknown>>(`/org/positions/${encodeURIComponent(positionId)}`, { method: 'PUT', body: JSON.stringify(payload) });
  },
  /** 创建组织同步任务。 */
  createOrgSyncJob(payload: Record<string, unknown> = {}) {
    return request<Record<string, unknown>>('/org/sync-jobs', { method: 'POST', body: JSON.stringify(payload) });
  },
  /** 查询组织同步任务。 */
  orgSyncJobs(params: Record<string, ApiTypes.QueryValue> = {}) {
    return request<ApiTypes.PageResult<Record<string, unknown>>>('/org/sync-jobs', { query: params });
  },
  /** 查询组织同步任务详情。 */
  orgSyncJob(jobId: string) {
    return request<Record<string, unknown>>(`/org/sync-jobs/${encodeURIComponent(jobId)}`);
  },
  /** 查询角色列表。 */
  roles() {
    return request<Record<string, unknown>[]>('/roles');
  },
  /** 创建角色。 */
  createRole(payload: Record<string, unknown>) {
    return request<Record<string, unknown>>('/roles', { method: 'POST', body: JSON.stringify(payload) });
  },
  /** 更新角色。 */
  updateRole(roleId: string, payload: Record<string, unknown>) {
    return request<Record<string, unknown>>(`/roles/${encodeURIComponent(roleId)}`, { method: 'PUT', body: JSON.stringify(payload) });
  },
  /** 删除角色。 */
  deleteRole(roleId: string) {
    return request<Record<string, unknown>>(`/roles/${encodeURIComponent(roleId)}`, { method: 'DELETE' });
  },
  /** 查询权限点列表。 */
  permissions() {
    return request<Record<string, unknown>[]>('/permissions');
  },
  /** 查询权限矩阵。 */
  permissionMatrix(params: Record<string, ApiTypes.QueryValue> = {}) {
    return request<Record<string, unknown>>('/permission-matrix', { query: params });
  },
  /** 更新角色权限。 */
  updateRolePermissions(roleId: string, payload: Record<string, unknown>) {
    return request<Record<string, unknown>>(`/roles/${encodeURIComponent(roleId)}/permissions`, { method: 'PUT', body: JSON.stringify(payload) });
  },
  /** 查询当前用户权限。 */
  mePermissions() {
    return request<Record<string, unknown>>('/me/permissions');
  },
};
