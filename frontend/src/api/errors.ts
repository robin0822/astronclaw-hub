export class AstronClawApiError extends Error {
  /** 后端返回的原始错误文案，不带 requestId，便于日志或后续埋点使用。 */
  rawMessage: string;
  code?: number;
  httpStatus?: number;
  requestId?: string;

  constructor(message: string, options: { code?: number; httpStatus?: number; requestId?: string } = {}) {
    super(options.requestId ? `${message}（requestId: ${options.requestId}）` : message);
    this.name = 'AstronClawApiError';
    this.rawMessage = message;
    this.code = options.code;
    this.httpStatus = options.httpStatus;
    this.requestId = options.requestId;
  }
}

/**
 * 兜底错误文案格式化。
 *
 * request 响应拦截器已经会把后端错误转换成可直接展示的 Error.message；
 * 这个函数主要保留给测试、非请求层错误或少量历史代码使用。
 */
export function getAstronClawErrorMessage(error: unknown) {
  if (error instanceof Error) return error.message;
  return '业务后端调用失败';
}
