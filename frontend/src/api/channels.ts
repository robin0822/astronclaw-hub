import { request } from './request';
import type * as ApiTypes from './types';

/** 消息渠道接口：渠道管理、连接测试、重连、停用、绑定智能体和审计日志。 */
export const channelsApi = {
  /** 查询消息渠道列表。 */
  list() {
    return request<ApiTypes.PageResult<Record<string, unknown>> | Record<string, unknown>[]>('/channels');
  },
  /** 创建消息渠道。 */
  create(payload: Record<string, unknown>) {
    return request<Record<string, unknown>>('/channels', { method: 'POST', body: JSON.stringify(payload) });
  },
  /** 更新消息渠道配置。 */
  update(channelId: string, payload: Record<string, unknown>) {
    return request<Record<string, unknown>>(`/channels/${encodeURIComponent(channelId)}`, { method: 'PUT', body: JSON.stringify(payload) });
  },
  /** 测试消息渠道连接。 */
  test(channelId: string) {
    return request<Record<string, unknown>>(`/channels/${encodeURIComponent(channelId)}/test`, { method: 'POST' });
  },
  /** 重连消息渠道。 */
  reconnect(channelId: string) {
    return request<Record<string, unknown>>(`/channels/${encodeURIComponent(channelId)}/reconnect`, { method: 'POST' });
  },
  /** 停用消息渠道。 */
  disable(channelId: string) {
    return request<Record<string, unknown>>(`/channels/${encodeURIComponent(channelId)}/disable`, { method: 'POST' });
  },
  /** 查询渠道绑定智能体。 */
  agents(channelId: string, params: Record<string, ApiTypes.QueryValue> = {}) {
    return request<ApiTypes.PageResult<Record<string, unknown>> | Record<string, unknown>[]>(`/channels/${encodeURIComponent(channelId)}/agents`, { query: params });
  },
  /** 更新渠道绑定智能体。 */
  updateAgents(channelId: string, payload: Record<string, unknown>) {
    return request<Record<string, unknown>>(`/channels/${encodeURIComponent(channelId)}/agents`, { method: 'PUT', body: JSON.stringify(payload) });
  },
  /** 发送渠道消息。 */
  sendMessage(channelId: string, payload: Record<string, unknown>) {
    return request<Record<string, unknown>>(`/channels/${encodeURIComponent(channelId)}/messages`, { method: 'POST', body: JSON.stringify(payload) });
  },
  /** 查询渠道消息日志。 */
  messageLogs(params: Record<string, ApiTypes.QueryValue> = {}) {
    return request<ApiTypes.PageResult<Record<string, unknown>>>('/channel-message-logs', { query: params });
  },
  /** 查询渠道审计日志。 */
  auditLogs(params: Record<string, ApiTypes.QueryValue> = {}) {
    return request<ApiTypes.PageResult<Record<string, unknown>>>('/channel-audit-logs', { query: params });
  },
};
