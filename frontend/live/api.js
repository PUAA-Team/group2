export class ApiError extends Error {
  constructor(message, status = 0, code = "NETWORK_ERROR", details = []) {
    super(message); this.name = "ApiError"; this.status = status; this.code = code; this.details = details;
  }
}

const labels = { account: "账号", password: "密码", name: "名称", display_name: "姓名", source_ref: "模型来源", trainer_id: "训练模板", version: "版本", quota: "资源配额", file: "文件" };
export function errorMessage(error) {
  if (error.code === "REVISION_MISMATCH") return "内容已更新，请关闭弹窗并刷新后重试";
  if (error.status === 422 && error.details?.length) {
    const field = error.details[0].loc?.findLast(part => typeof part === "string" && labels[part]);
    return field ? `请检查${labels[field]}的内容或格式` : "请检查填写内容和文件格式";
  }
  return error.message || "操作失败，请重试";
}

export class ApiClient {
  constructor(fetcher = globalThis.fetch.bind(globalThis)) { this.fetcher = fetcher; this.csrf = ""; this.onExpired = null; }
  async request(path, { method = "GET", body, revision, signal, quietAuth = false } = {}) {
    const headers = { Accept: "application/json" };
    const isFile = body instanceof FormData;
    if (body !== undefined && !isFile) headers["Content-Type"] = "application/json";
    if (!["GET", "HEAD"].includes(method) && this.csrf) headers["X-CSRF-Token"] = this.csrf;
    if (revision !== undefined) headers["If-Match"] = `"${revision}"`;
    let result;
    try {
      result = await this.fetcher(`/api/v1${path}`, { method, headers, credentials: "same-origin", signal,
        body: body === undefined ? undefined : isFile ? body : JSON.stringify(body) });
    } catch (error) {
      if (error.name === "AbortError") throw error;
      throw new ApiError("无法连接服务，请检查服务是否已启动");
    }
    let payload;
    try { payload = await result.json(); } catch { throw new ApiError("服务响应异常，请重试", result.status, "INVALID_RESPONSE"); }
    if (!result.ok) {
      if (result.status === 401 && !quietAuth) { this.csrf = ""; this.onExpired?.(); }
      throw new ApiError(payload.error?.message || "操作失败", result.status, payload.error?.code, payload.error?.details);
    }
    if (payload.data?.csrf_token) this.csrf = payload.data.csrf_token;
    return payload;
  }
  async all(path, signal) {
    let page = 1, items = [];
    while (true) {
      const result = await this.request(`${path}${path.includes("?") ? "&" : "?"}page=${page}&page_size=100`, { signal });
      items.push(...result.data);
      if (items.length >= result.pagination.total || !result.data.length) return items;
      page += 1;
    }
  }
}
