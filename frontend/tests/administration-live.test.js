import test from "node:test";
import assert from "node:assert/strict";
import { administrationAction, administrationDialog, isManagementPage, loadManagement, renderManagement, saveAdministration } from "../live/administration.js";
import { renderDialog } from "../live/dialogs.js";
import { renderAuth } from "../live/pages/auth.js";

function context(path) {
  return { path, params: new URLSearchParams(), page: 1, q: "", workspace: { id: "w1", name: "空间甲" }, workspaces: [{ id: "w1", name: "空间甲" }, { id: "w2", name: "空间乙" }], groups: [], session: { user: { id: "u1", display_name: "成员", account: "member", revision: 1 } }, access: { actions: [] }, data: {} };
}

test("管理员管理页面查询全局资源，跨空间详情保留归属", async () => {
  const ctx = context("/admin/data"), calls = [];
  await loadManagement({ async request(path) { calls.push(path); return { data: [] }; } }, ctx);
  assert.ok(calls[0].startsWith("/admin/asset-catalog/datasets?")); assert.ok(!calls[0].includes("workspaces/w1"));
  ctx.data = { data: [{ id: "d1", name: "空间乙的数据", workspace_id: "w2", workspace_name: "空间乙", task_type: "text_classification", latest_version: null }] };
  assert.ok(renderManagement(ctx).includes("/datasets/d1?workspace=w2"));
  for (const path of ["/admin/settings", "/admin/stats", "/admin/data", "/admin/models", "/admin/jobs", "/admin/audit"]) assert.ok(isManagementPage(path));
});

test("系统设置和模型连接在弹窗编辑，已有密钥不回填", () => {
  const ctx = context("/admin/settings"); ctx.data.settings = { platform_name: "研发中心", invitations_enabled: true, global_concurrent_jobs: 16, max_upload_mib: 10, max_samples: 10000 };
  ctx.data.connections = [{ id: "c1", name: "测试模型", endpoint: "https://example.com/v1", model: "model", capabilities: ["text"], credential_set: true, active: true, health: {} }];
  const page = renderManagement(ctx); assert.ok(page.includes("测试模型") && !page.includes('<form'));
  const settings = renderDialog({ kind: "settings-edit", item: {} }, ctx); assert.ok(settings.includes('role="dialog"') && settings.includes("研发中心"));
  const dialog = administrationDialog({ kind: "connection-edit", item: ctx.data.connections[0] }, ctx);
  assert.ok(dialog.fields.includes('name="secret" value=""'));
  assert.ok(!dialog.fields.includes('secret_ref'));
});

test("邀请注册需要邀请码，不接受从界面选择管理员", () => {
  const html = renderAuth({ initialized: true, registration: true, invitations_enabled: true, invitation: '<unsafe>' });
  assert.ok(html.includes('data-form="register"') && html.includes('name="invitation"'));
  assert.ok(html.includes("&lt;unsafe&gt;") && !html.includes('name="is_admin"'));
  assert.ok(!renderAuth({ initialized: true, registration: true, invitations_enabled: false }).includes('data-form="register"'));
});

test("密码确认失败不发送请求，读取有效权限的弹窗没有保存操作", async () => {
  const form = new FormData(); form.set("password", "new-password-2026"); form.set("confirm", "mismatch");
  let sent = false; await assert.rejects(saveAdministration({ async request() { sent = true; } }, { kind: "password-own", item: {} }, form, context("/space")));
  assert.equal(sent, false);
  const dialog = renderDialog({ kind: "user-access", item: { display_name: "成员", access: { actions: ["training.read"], quota: {} } } }, context("/admin/users"));
  assert.ok(dialog.includes("查看训练") && !dialog.includes('type="submit"'));
});

test("管理员签发重置码后只显示一次，可关闭", async () => {
  const ctx = context("/admin/users");
  ctx.data = { data: [{ id: "u2", account: "member", display_name: "成员", is_admin: false, group_id: null, active: true }] };
  const calls = [];
  const api = { async request(path, opts) { calls.push([path, opts]); return { data: { account: "member", code: "ABCDEFGH", expires_at: "2026-11-26T18:00:00+08:00" } }; } };
  let rendered = false;
  const helpers = { api, ctx, openModal() {}, render() { rendered = true; }, load() {}, toast() {} };
  await administrationAction("admin-issue-reset-code", "u2", helpers);
  assert.equal(calls[0][0], "/auth/password-reset-codes");
  assert.deepEqual(calls[0][1].body, { account: "member" });
  assert.equal(ctx.generatedResetCode.code, "ABCDEFGH");
  assert.ok(rendered);
  await administrationAction("admin-hide-reset-code", "u2", helpers);
  assert.equal(ctx.generatedResetCode, null);
});
