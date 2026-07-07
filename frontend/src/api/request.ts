/**
 * AstronClaw 业务接口请求层。
 *
 * 所有业务 API 文件都应该通过这里发请求，避免每个页面或模块各自处理：
 * - 后端 API 根路径
 * - 后端会话 cookie 携带
 * - query 参数序列化
 * - 统一响应结构拆包
 * - 业务错误与 HTTP 错误转换
 * - 401/登录失效跳转
 * - Blob、ArrayBuffer 等文件类响应
 * - Bearer Token 注入
 */
import axios, { AxiosHeaders, type AxiosRequestConfig, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios';
import { AstronClawApiError } from './errors';
import type { ApiResponse, AstronClawRequestConfig } from './types';

// VITE_ASTRONCLAW_API_BASE_URL 用于覆盖默认后端地址，末尾斜杠会去掉，避免拼接出双斜杠。
const rawApiBase = (import.meta.env.VITE_ASTRONCLAW_API_BASE_URL as string | undefined)?.replace(/\/+$/, '');

// 默认请求超时 60s；少数长耗时接口在调用时通过 timeoutMs 单独覆盖。
const DEFAULT_API_TIMEOUT_MS = 60_000;

// 后端统一响应里表示未登录或登录失效的业务码。
const UNAUTHORIZED_CODE = 401001;

// accessToken 只用于请求认证；用户资料和权限仍以后端接口返回为准，不在前端自行判权。
const ACCESS_TOKEN_STORAGE_KEY = 'astronclaw.accessToken';

let memoryAccessToken: string | undefined;

function getTokenStorage() {
  try {
    return typeof window === 'undefined' ? undefined : window.localStorage;
  } catch {
    return undefined;
  }
}

/** 保存登录后拿到的 accessToken，后续请求会由请求拦截器自动写入 Authorization。 */
export function setAstronClawAccessToken(token?: string | null) {
  const normalizedToken = token?.trim() || undefined;
  memoryAccessToken = normalizedToken;

  const storage = getTokenStorage();
  if (!storage) return;
  if (normalizedToken) storage.setItem(ACCESS_TOKEN_STORAGE_KEY, normalizedToken);
  else storage.removeItem(ACCESS_TOKEN_STORAGE_KEY);
}

/** 读取当前可用 accessToken，优先使用内存值，刷新页面后从 localStorage 恢复。 */
export function getAstronClawAccessToken() {
  if (memoryAccessToken) return memoryAccessToken;

  const storedToken = getTokenStorage()?.getItem(ACCESS_TOKEN_STORAGE_KEY)?.trim() || undefined;
  memoryAccessToken = storedToken;
  return storedToken;
}

/** 登录失效、退出登录或测试清理时调用，避免继续携带过期 token。 */
export function clearAstronClawAccessToken() {
  setAstronClawAccessToken(undefined);
}

/** 业务后端 API 根路径，默认走 Vite 的 /api 代理。 */
export const ASTRON_CLAW_API_BASE = rawApiBase || '/api/v1/astron-claw';

export type AuthRedirectHandler = (url: string) => void;

let authRedirectHandler: AuthRedirectHandler | undefined;

/** 自定义登录失效跳转处理，主要用于自动化测试或宿主壳集成。 */
export function setAuthRedirectHandler(handler?: AuthRedirectHandler) {
  authRedirectHandler = handler;
}

/** 根据当前地址生成登录页 redirect URL。 */
export function createLoginRedirectUrl(pathname: string, search = '', hash = '') {
  const redirect = `${pathname}${search}${hash}`;
  return `/login?redirect=${encodeURIComponent(redirect)}`;
}

/**
 * 登录失效后的统一跳转。
 *
 * - 已在登录页时不重复跳转。
 * - 公开分享页不强制跳登录，避免分享链接被拦截。
 * - 其他页面会带上 redirect 参数，登录成功后可以回到原页面。
 */
function redirectToLogin() {
  clearAstronClawAccessToken();
  if (typeof window === 'undefined') return;
  const { pathname, search, hash } = window.location;
  if (pathname === '/login' || pathname.startsWith('/share/')) return;

  const target = createLoginRedirectUrl(pathname, search, hash);
  if (authRedirectHandler) authRedirectHandler(target);
  else window.location.assign(target);
}

/**
 * query 参数序列化规则。
 *
 * - undefined、null、空字符串不传给后端。
 * - 数组会展开成同名多值，例如 ids=1&ids=2。
 * - 其他值统一转成字符串。
 */
function serializeQuery(params: Record<string, unknown>) {
  const searchParams = new URLSearchParams();

  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') return;
    if (Array.isArray(value)) value.forEach((item) => searchParams.append(key, String(item)));
    else searchParams.set(key, String(value));
  });

  return searchParams.toString();
}

// 下面几类请求体不能手动设置 application/json。
// FormData 需要浏览器自动生成 multipart boundary，Blob/ArrayBuffer 通常用于文件，URLSearchParams 有自己的表单编码。
function isFormDataPayload(value: unknown): value is FormData {
  return typeof FormData !== 'undefined' && value instanceof FormData;
}

function isBlobPayload(value: unknown): value is Blob {
  return typeof Blob !== 'undefined' && value instanceof Blob;
}

function isArrayBufferPayload(value: unknown): value is ArrayBuffer {
  return typeof ArrayBuffer !== 'undefined' && value instanceof ArrayBuffer;
}

function isUrlSearchParamsPayload(value: unknown): value is URLSearchParams {
  return typeof URLSearchParams !== 'undefined' && value instanceof URLSearchParams;
}

/**
 * 判断当前请求体是否应该补 Content-Type: application/json。
 *
 * 业务接口大多传 JSON.stringify(payload) 或普通 JSON 数据，需要明确告诉后端按 JSON 解析。
 * 文件上传、二进制下载、表单编码这几类请求体由浏览器或 axios 自己处理 Content-Type。
 */
function shouldSetJsonContentType(data: unknown) {
  return data !== undefined && data !== null && !isFormDataPayload(data) && !isBlobPayload(data) && !isArrayBufferPayload(data) && !isUrlSearchParamsPayload(data);
}

/**
 * 判断后端是否返回了统一响应结构。
 *
 * 当前业务约定为类似：
 * {
 *   code: 0,
 *   message: 'success',
 *   data: ...,
 *   requestId: '...'
 * }
 */
function isApiResponse<T>(value: unknown): value is ApiResponse<T> {
  return typeof value === 'object' && value !== null && typeof (value as { code?: unknown }).code === 'number';
}

/**
 * 兼容 axios 不同 headers 形态读取响应头。
 *
 * axios v1 可能返回 AxiosHeaders，也可能在部分场景下是普通对象；
 * 这里统一处理大小写，避免 content-type 读取不到。
 */
function getResponseHeader(headers: AxiosResponse['headers'], name: string) {
  const headerBag = headers as { get?: (headerName: string) => unknown; [key: string]: unknown };
  const value = typeof headerBag.get === 'function' ? headerBag.get(name) : (headerBag[name] ?? headerBag[name.toLowerCase()]);
  if (Array.isArray(value)) return value.join(', ');
  return value === undefined || value === null ? '' : String(value);
}

/** 读取单次请求上的 skipAuthRedirect，公开分享等接口会用它关闭 401 自动跳登录。 */
function getSkipAuthRedirect(response: AxiosResponse<unknown>) {
  return Boolean((response.config as AxiosRequestConfig & { skipAuthRedirect?: boolean }).skipAuthRedirect);
}

/** 判断响应是否是 JSON，兼容 application/json 和 application/problem+json 等 +json 类型。 */
function isJsonContentType(contentType: string) {
  return contentType.toLowerCase().includes('application/json') || contentType.toLowerCase().includes('+json');
}

/**
 * 按响应头解析响应体。
 *
 * axios 默认会解析普通 JSON，但以下场景还需要兜底：
 * - 文件下载接口返回 Blob，同时后端可能用 JSON 返回错误信息。
 * - 某些代理或后端把 JSON 当字符串返回。
 * - 非 JSON 响应必须保持原样，否则文件流会被破坏。
 */
async function parseResponseData(data: unknown, headers: AxiosResponse['headers']) {
  if (!isJsonContentType(getResponseHeader(headers, 'content-type'))) return data;

  if (isBlobPayload(data)) {
    const text = await data.text();
    try {
      return text ? JSON.parse(text) : null;
    } catch {
      return data;
    }
  }

  if (typeof data === 'string') {
    try {
      return data ? JSON.parse(data) : null;
    } catch {
      return data;
    }
  }

  return data;
}

/**
 * 把后端 code != 0 的业务错误转换成 AstronClawApiError。
 *
 * 这样页面层只需要 catch 一个统一错误类型，就能拿到 message、code、httpStatus、requestId。
 */
function buildBusinessError(body: ApiResponse<unknown>, httpStatus?: number, skipAuthRedirect = false) {
  if (!skipAuthRedirect && body.code === UNAUTHORIZED_CODE) redirectToLogin();
  return new AstronClawApiError(body.message || `业务后端业务错误 ${body.code}`, {
    code: body.code,
    httpStatus,
    requestId: body.requestId,
  });
}

/**
 * 把非 2xx HTTP 响应转换成 AstronClawApiError。
 *
 * 优先解析后端统一响应里的 message/requestId；
 * 如果 HTTP 401 或业务码 401001，会按统一规则跳转登录页。
 */
async function buildHttpError(response: AxiosResponse<unknown>) {
  const body = await parseResponseData(response.data, response.headers);
  const skipAuthRedirect = getSkipAuthRedirect(response);
  if (!skipAuthRedirect && (response.status === 401 || (isApiResponse(body) && body.code === UNAUTHORIZED_CODE))) redirectToLogin();

  return new AstronClawApiError(isApiResponse(body) ? body.message || `业务后端 HTTP ${response.status}` : `业务后端 HTTP ${response.status}`, {
    code: isApiResponse(body) ? body.code : undefined,
    httpStatus: response.status,
    requestId: isApiResponse(body) ? body.requestId : undefined,
  });
}

/**
 * 响应成功时的统一拆包逻辑。
 *
 * - Blob/ArrayBuffer 直接返回，主要用于下载类接口。
 * - 普通业务接口必须返回统一 ApiResponse。
 * - code 为 0 时只把 data 返回给业务模块，页面不用再写 response.data.data。
 * - code 非 0 时抛出统一业务错误。
 */
async function unwrapApiResponse<T>(response: AxiosResponse<unknown>): Promise<T> {
  const body = await parseResponseData(response.data, response.headers);

  if (isBlobPayload(body) || isArrayBufferPayload(body)) return body as T;

  if (!isApiResponse<T>(body)) {
    throw new AstronClawApiError('业务后端未返回统一响应结构，请检查 /api/v1/astron-claw 代理或服务', {
      httpStatus: response.status,
    });
  }

  if (body.code !== 0) throw buildBusinessError(body, response.status, getSkipAuthRedirect(response));

  return body.data;
}

/**
 * 统一整理请求异常。
 *
 * axios 会把 HTTP 错误、超时、断网、取消等情况都包装成 AxiosError；
 * 这里转换成项目自己的 AstronClawApiError，避免页面层判断过多 axios 细节。
 */
async function normalizeRequestError(error: unknown) {
  if (error instanceof AstronClawApiError) return error;

  if (axios.isAxiosError(error)) {
    if (error.response) return buildHttpError(error.response);
    if (error.code === 'ECONNABORTED' || error.code === 'ETIMEDOUT') return new AstronClawApiError('业务后端请求超时');
    return new AstronClawApiError('业务后端网络不可用或请求超时');
  }

  if (error instanceof Error) return new AstronClawApiError(error.message);
  return new AstronClawApiError('业务后端调用失败');
}

/**
 * 全局共享的 axios 实例，所有 AstronClaw 业务接口都从这里发出。
 *
 * - baseURL：统一业务后端前缀。
 * - timeout：默认 60s，长耗时接口可通过 timeoutMs 单独覆盖。
 * - withCredentials：保留 cookie 携带能力，兼容后端混合部署。
 * - Authorization：如果登录接口返回 accessToken，请求拦截器会自动补 Bearer Token。
 * - paramsSerializer：保证 query 参数按本文件约定序列化。
 */
export const astronClawHttp = axios.create({
  baseURL: ASTRON_CLAW_API_BASE,
  timeout: DEFAULT_API_TIMEOUT_MS,
  withCredentials: true,
  paramsSerializer: {
    serialize: serializeQuery,
  },
});

// 请求拦截：在所有请求发出前补齐通用请求头和认证信息。
astronClawHttp.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const headers = AxiosHeaders.from(config.headers);
  // 只有 JSON 请求体才补 Content-Type，避免破坏上传文件时的 multipart boundary。
  if (shouldSetJsonContentType(config.data) && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');

  // 后端接口文档要求登录后统一携带 Authorization: Bearer <accessToken>。
  const accessToken = getAstronClawAccessToken();
  if (accessToken && !headers.has('Authorization')) headers.set('Authorization', `Bearer ${accessToken}`);

  config.headers = headers;
  return config;
});

// 响应拦截：2xx 响应走统一拆包，非 2xx 或网络异常走统一错误转换。
astronClawHttp.interceptors.response.use(
  (response) => unwrapApiResponse(response),
  async (error: unknown) => Promise.reject(await normalizeRequestError(error)),
);

/**
 * 功能 API 文件统一使用的请求入口。
 *
 * 参数约定：
 * - path：相对于 ASTRON_CLAW_API_BASE 的接口路径，例如 /agents。
 * - query：GET 查询参数，会映射到 axios params。
 * - body：兼容旧 fetch 写法，会映射到 axios data。
 * - data：axios 标准请求体字段，优先级高于 body。
 * - timeoutMs：单个接口覆盖默认超时时间。
 * - skipAuthRedirect：跳过 401 自动跳登录，公开分享接口等无需登录页面会用到。
 */
export async function request<T>(path: string, init: AstronClawRequestConfig = {}): Promise<T> {
  const { query, body, data, timeoutMs, skipAuthRedirect, ...axiosInit } = init;
  const axiosConfig: AxiosRequestConfig & { skipAuthRedirect?: boolean } = {
    ...axiosInit,
    url: path,
    params: query,
    data: data ?? body,
  };

  if (timeoutMs !== undefined) axiosConfig.timeout = timeoutMs;
  if (skipAuthRedirect !== undefined) axiosConfig.skipAuthRedirect = skipAuthRedirect;

  return astronClawHttp.request<unknown, T>(axiosConfig);
}
