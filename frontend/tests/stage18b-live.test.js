import test from "node:test";
import assert from "node:assert/strict";
import { renderSpace } from "../live/pages/overview.js";
import { renderManagement } from "../live/administration.js";

test("Stage 18B: 用户空间展示多端登录会话与踢出按钮", () => {
  const html = renderSpace({
    workspace: { id: "ws1", name: "测试空间", owner_id: "u1" },
    workspaces: [{ id: "ws1", name: "测试空间" }],
    session: { user: { id: "u1", display_name: "李工" }, access: { actions: ["workspaces.create"] } },
    access: { actions: ["training.read"], quota: { gpu_count: 1, concurrent_jobs: 2, storage_gib: 10 } },
    data: {
      sessions: [
        { id: "ses_1", created_at: "2026-11-26T00:00:00Z", expires_at: "2026-11-27T00:00:00Z", current: true },
        { id: "ses_2", created_at: "2026-11-26T01:00:00Z", expires_at: "2026-11-27T01:00:00Z", current: false },
      ],
    },
  });
  assert.ok(html.includes("登录会话管理"));
  assert.ok(html.includes('data-action="session-revoke-others"'));
  assert.ok(html.includes('data-action="session-revoke"'));
  assert.ok(html.includes("ses_2"));
});

test("Stage 18B: 管理端作业列表提供行内停止与重跑按钮", () => {
  const html = renderManagement({
    path: "/admin/jobs",
    params: new URLSearchParams(),
    workspaces: [{ id: "ws1", name: "默认空间" }],
    data: {
      data: [
        { id: "j1", workspace_id: "ws1", workspace_name: "默认空间", name: "运行作业", kind: "train", actor_name: "李工", status: "running", device_kind: "cpu", created_at: "2026-11-26T00:00:00Z" },
        { id: "j2", workspace_id: "ws1", workspace_name: "默认空间", name: "完成作业", kind: "train", actor_name: "李工", status: "succeeded", device_kind: "cpu", created_at: "2026-11-26T00:00:00Z" },
      ],
    },
  });
  assert.ok(html.includes('data-action="admin-job-stop"'));
  assert.ok(html.includes('data-action="admin-job-retry"'));
});
