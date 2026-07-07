import { request } from './request';
/** 公开分享接口：使用分享 ID 和 token 读取内容，不触发登录跳转。 */
export const shareLinksApi = {
  /** 使用分享 token 查询公开分享内容。 */
  get(shareId: string, token: string) {
    return request<Record<string, unknown>>(`/share/${encodeURIComponent(shareId)}`, { query: { token }, skipAuthRedirect: true });
  },
};
