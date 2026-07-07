import { request } from './request';
import type * as ApiTypes from './types';

/** 通知接口：通知列表、未读摘要、已读和到期席位扫描。 */
export const notificationsApi = {
  /** 查询通知列表。 */
  list(params: Record<string, ApiTypes.QueryValue> = {}) {
    return request<ApiTypes.PageResult<Record<string, unknown>>>('/notifications', { query: params });
  },
  /** 查询未读通知摘要。 */
  summary() {
    return request<{ unreadCount?: number; byType?: Record<string, number> }>('/notifications/summary');
  },
  /** 标记通知已读。 */
  read(notificationId: string) {
    return request<Record<string, unknown>>(`/notifications/${encodeURIComponent(notificationId)}/read`, { method: 'POST' });
  },
  /** 扫描席位到期并生成通知。 */
  scanSeatExpirations() {
    return request<Record<string, unknown>>('/notifications/scan-seat-expirations', { method: 'POST' });
  },
};
