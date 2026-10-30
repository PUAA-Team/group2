import test from "node:test";
import assert from "node:assert/strict";
import { ApiClient, ApiError, errorMessage } from "../live/api.js";

const result = (payload, status = 200) => new Response(JSON.stringify(payload), { status, headers: { "Content-Type": "application/json" } });

test("真实请求携带 Cookie、CSRF 和版本，上传交由浏览器设置边界", async () => {
  const calls = [];
  const api = new ApiClient(async (url, options) => { calls.push([url, options]); return result({ data: { csrf_token: "in-memory" } }); });
  await api.request("/auth/login", { method: "POST", body: { account: "owner", password: "test" } });
  await api.request("/models/x", { method: "PATCH", revision: 2, body: { name: "new" } });
  assert.equal(calls[1][1].credentials, "same-origin");
  assert.equal(calls[1][1].headers["X-CSRF-Token"], "in-memory");
  assert.equal(calls[1][1].headers["If-Match"], '"2"');
  const upload = new FormData(); upload.append("file", new Blob(["text,label\na,b"]), "train.csv");
  await api.request("/datasets/x/versions", { method: "POST", body: upload });
  assert.equal(calls[2][1].headers["Content-Type"], undefined);
  assert.equal(calls[2][1].body, upload);
});

test("过期会话清除内存凭据，错误登录不触发页面跳转", async () => {
  const api = new ApiClient(async () => result({ error: { code: "UNAUTHENTICATED", message: "请重新登录" } }, 401));
  let expired = 0; api.csrf = "old"; api.onExpired = () => expired++;
  await assert.rejects(api.request("/auth/session"), { status: 401 });
  assert.equal(expired, 1); assert.equal(api.csrf, "");
  await assert.rejects(api.request("/auth/login", { method: "POST", quietAuth: true }), { status: 401 });
  assert.equal(expired, 1);
});

test("请求失败明确报错，既不生成数据也不使用模拟结果", async () => {
  const api = new ApiClient(async () => { throw new TypeError("private network info"); });
  await assert.rejects(api.request("/models"), error => error instanceof ApiError && !error.message.includes("private"));
  const invalid = new ApiClient(async () => new Response("<html>bad</html>", { status: 500 }));
  await assert.rejects(invalid.request("/models"), { code: "INVALID_RESPONSE" });
  const abort = new DOMException("cancelled", "AbortError");
  await assert.rejects(new ApiClient(async () => { throw abort; }).request("/models"), error => error === abort);
  assert.match(errorMessage(new ApiError("conflict", 412, "REVISION_MISMATCH")), /刷新/);
});

test("获取完整可选列表时按服务端分页读取，保留查询范围", async () => {
  const paths = [];
  const api = new ApiClient(async path => {
    paths.push(path); const page = Number(new URL(`http://test${path}`).searchParams.get("page"));
    return result({ data: page === 1 ? [{ id: 1 }] : [{ id: 2 }], pagination: { total: 2 } });
  });
  assert.deepEqual(await api.all("/workspaces?q=team"), [{ id: 1 }, { id: 2 }]);
  assert.equal(paths.length, 2); assert.match(paths[1], /q=team&page=2/);
});
