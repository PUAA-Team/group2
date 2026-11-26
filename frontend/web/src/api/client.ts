import type { ApiEnvelope } from "@/types/platform";

export interface ApiRequestOptions {
  method?: string;
  body?: unknown;
  revision?: number;
  signal?: AbortSignal;
  quietAuth?: boolean;
}

export class ApiError extends Error {
  status: number;
  code: string;
  requestId: string;
  details: unknown[];

  constructor(status: number, code: string, message: string, requestId = "", details: unknown[] = []) {
    super(message);
    this.status = status;
    this.code = code;
    this.requestId = requestId;
    this.details = details;
  }
}

export function errorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) {
    return error instanceof Error ? error.message : "操作失败，请稍后重试";
  }
  const byCode: Record<string, string> = {
    UNAUTHENTICATED: "登录已过期，请重新登录",
    FORBIDDEN: "当前账号无权执行此操作",
    CSRF_FAILED: "页面校验已失效，请刷新后重试",
    REVISION_MISMATCH: "内容已被其他人更新，请刷新后重试",
    CONFLICT: error.message || "记录已存在或状态冲突",
    VALIDATION_ERROR: error.message || "输入内容不符合要求",
    FILE_TOO_LARGE: "上传文件超过平台限制",
    UNSUPPORTED_FORMAT: error.message || "文件格式不受支持",
    RATE_LIMITED: "操作过于频繁，请稍后重试",
  };
  const text = byCode[error.code] || error.message || "请求失败";
  return error.requestId ? `${text}（编号 ${error.requestId.slice(0, 8)}）` : text;
}

export class ApiClient {
  base: string;
  fetchImpl: typeof fetch;
  csrf = "";
  onExpired: (() => void) | null = null;

  constructor(base = "/api/v1", fetchImpl: typeof fetch = (...args) => fetch(...args)) {
    this.base = base;
    this.fetchImpl = fetchImpl;
  }

  async request<T = any>(path: string, opts: ApiRequestOptions = {}): Promise<ApiEnvelope<T>> {
    const { method = "GET", body, revision, signal, quietAuth = false } = opts;
    const headers: Record<string, string> = {};
    const form = typeof FormData !== "undefined" && body instanceof FormData;
    if (body !== undefined && !form) headers["Content-Type"] = "application/json";
    if (!["GET", "HEAD", "OPTIONS"].includes(method) && this.csrf) headers["X-CSRF-Token"] = this.csrf;
    if (revision !== undefined) headers["If-Match"] = `"${revision}"`;

    let response: Response;
    try {
      response = await this.fetchImpl(`${this.base}${path}`, {
        method,
        credentials: "same-origin",
        headers,
        signal,
        body: body === undefined ? undefined : form ? (body as FormData) : JSON.stringify(body),
      });
    } catch (error: any) {
      if (error?.name === "AbortError") throw error;
      throw new ApiError(0, "NETWORK_ERROR", "无法连接平台服务，请确认后端已启动");
    }

    let payload: any = {};
    try {
      payload = await response.json();
    } catch {
      payload = {};
    }

    if (response.ok) {
      if (payload.data?.csrf_token) this.csrf = payload.data.csrf_token;
      return payload as ApiEnvelope<T>;
    }

    const detail = payload.error || {};
    const error = new ApiError(
      response.status,
      detail.code || "REQUEST_FAILED",
      detail.message || `请求失败（${response.status}）`,
      payload.request_id || "",
      detail.details || []
    );
    if (response.status === 401 && !quietAuth) {
      this.csrf = "";
      this.onExpired?.();
    }
    throw error;
  }

  async all<T = any>(path: string, signal?: AbortSignal): Promise<T[]> {
    const items: T[] = [];
    for (let page = 1; page <= 50; page += 1) {
      const separator = path.includes("?") ? "&" : "?";
      const result = await this.request<T[]>(`${path}${separator}page=${page}&page_size=100`, { signal });
      items.push(...(result.data || []));
      if (!result.pagination || items.length >= result.pagination.total) break;
    }
    return items;
  }
}
