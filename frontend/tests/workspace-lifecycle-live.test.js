import assert from "node:assert/strict";
import test from "node:test";
import { administrationDialog, saveAdministration } from "../live/administration.js";
import { renderAuth } from "../live/pages/auth.js";
import { renderSpace } from "../live/pages/overview.js";

test("开放注册开启时注册页允许不填邀请码", () => {
  const html = renderAuth({ initialized: true, registration: true, invitations_enabled: true, self_registration_enabled: true });
  assert.match(html, /注册账号/);
  assert.match(html, /邀请码（选填）/);
  assert.doesNotMatch(html, /name="invitation"[^>]*required/);

  const inviteOnly = renderAuth({ initialized: true, registration: true, invitations_enabled: true, self_registration_enabled: false });
  assert.match(inviteOnly, /邀请注册/);
  assert.match(inviteOnly, /name="invitation"[^>]*required/);
});

test("系统设置与用户空间弹窗支持开放注册、空间邀请与空间删除", async () => {
  const settingsDialog = administrationDialog({ kind: "settings-edit" }, {
    groups: [{ id: "grp_1", name: "默认组" }],
    data: { settings: { platform_name: "模训平台", invitations_enabled: true, self_registration_enabled: false, default_group_id: "grp_1", global_concurrent_jobs: 8, max_upload_mib: 10, max_samples: 5000, revision: 2 } },
  });
  assert.match(settingsDialog.fields, /name="self_registration_enabled"/);
  assert.match(settingsDialog.fields, /name="default_group_id"/);

  const calls = [];
  const api = { request: async (path, options) => { calls.push({ path, ...options }); return { data: { code: "inv_secret_123456", status: "joined", workspace_id: "ws_1" } }; } };
  const ctx = { origin: "https://example.test", workspace: { id: "ws_1", name: "研发空间", revision: 3 }, ui: {} };

  const invForm = new FormData();
  invForm.set("role", "viewer"); invForm.set("days", "7"); invForm.set("require_approval", "on");
  await saveAdministration(api, { kind: "workspace-invite", workspaceId: "ws_1" }, invForm, ctx);
  assert.equal(calls[0].path, "/workspaces/ws_1/invites");
  assert.equal(calls[0].body.require_approval, true);
  assert.match(ctx.generatedSpaceInvite.url, /#\/join\?code=inv_secret_123456/);

  const delForm = new FormData();
  delForm.set("confirm_name", "研发空间");
  const delRes = await saveAdministration(api, { kind: "workspace-delete", workspaceId: "ws_1" }, delForm, ctx);
  assert.equal(calls[1].method, "DELETE");
  assert.match(calls[1].path, /\/workspaces\/ws_1\?confirm_name=/);
  assert.equal(delRes.destination, "/space");
});

test("用户空间页面渲染空间邀请码与待审批加入申请", () => {
  const html = renderSpace({
    workspaces: [{ id: "ws_1", name: "研发空间" }],
    workspace: { id: "ws_1", name: "研发空间", owner_id: "usr_1" },
    session: { access: { actions: ["workspaces.create"] } },
    access: { actions: ["members.manage"], quota: {} },
    data: {
      members: { data: [] },
      invites: [{ id: "win_1", code_preview: "abcd1234…", role: "editor", require_approval: true, max_uses: 5, used_count: 1, expires_at: "2026-12-01T00:00:00Z", revoked_at: null }],
      joinRequests: [{ id: "wjr_1", display_name: "李四", account: "lisi", requested_role: "editor", status: "pending" }],
    },
  });
  assert.match(html, /生成空间邀请/);
  assert.match(html, /删除空间/);
  assert.match(html, /abcd1234…/);
  assert.match(html, /admin-approve-join/);
});
