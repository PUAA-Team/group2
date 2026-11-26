import test from "node:test";
import assert from "node:assert/strict";
import { renderSpace } from "../live/pages/overview.js";
import { renderDialog } from "../live/dialogs.js";
import { governanceDialog } from "../live/governance.js";
import { renderCompute } from "../live/compute.js";

test("Stage 21A: 用户空间展示4级角色、子配额、所有权转让与空间预算账单", () => {
  const html = renderSpace({
    workspace: { id: "ws1", name: "算法一队", owner_id: "u1", revision: 1 },
    workspaces: [{ id: "ws1", name: "算法一队" }],
    session: { user: { id: "u1", display_name: "张队", is_admin: false }, access: { actions: ["workspaces.create"] } },
    access: { actions: ["members.manage", "training.read"], quota: { gpu_count: 2, concurrent_jobs: 4, storage_gib: 50 } },
    data: {
      members: {
        data: [
          { user_id: "u1", account: "zhang", display_name: "张队", role: "admin", quota: null },
          { user_id: "u2", account: "wang", display_name: "王同学", role: "annotator", quota: { concurrent_jobs: 1 } },
        ],
      },
      governanceSummary: {
        budget: { concurrent_jobs: 4, gpu_count: 2, storage_gib: 100, usage: { concurrent_jobs: 1, gpu_count: 0, storage_bytes: 1048576 } },
        members: [{ user_id: "u2", account: "wang", display_name: "王同学", role: "annotator", quota: { concurrent_jobs: 1 }, storage_bytes: 1048576, jobs: { total: 2, active: 0, succeeded: 2, failed: 0 }, gpu_seconds: 3600, assistant_tokens: 120 }],
      },
    },
  });
  assert.ok(html.includes("标注员"));
  assert.ok(html.includes("空间预算与成员账单"));
  assert.ok(html.includes('data-action="transfer-owner"'));
  assert.ok(html.includes("1.00 小时"));
});

test("Stage 21A: 成员配置弹窗、所有权转让弹窗与空间设备策略弹窗", () => {
  const memberModal = renderDialog({ kind: "member", item: { user_id: "u2", account: "wang", role: "annotator", quota: { concurrent_jobs: 1 } } }, { data: {} });
  assert.ok(memberModal.includes("空间管理员"));
  assert.ok(memberModal.includes("标注员"));
  assert.ok(memberModal.includes('name="quota_concurrent_jobs"'));

  const transferModal = renderDialog({ kind: "transfer-owner", item: { user_id: "u2", display_name: "王同学", account: "wang" } }, { data: {} });
  assert.ok(transferModal.includes("转让空间所有权"));

  const wsPol = governanceDialog({
    kind: "gov-device-policy",
    item: { workspaceScoped: true, policy: { enabled: true, purpose: "train", allow_users: [], allow_groups: [], deny_users: [], deny_groups: [] }, principals: { users: [{ id: "u2", name: "王同学" }], groups: [] } },
  });
  assert.ok(wsPol.fields.includes("允许用户"));
  assert.ok(!wsPol.fields.includes("允许用户组"));

  const wsBudgetHtml = renderDialog({
    kind: "gov-workspace-budget",
    item: { budget: { gpu_count: 2, concurrent_jobs: 4, storage_gib: 100, usage: { concurrent_jobs: 0, gpu_count: 0, storage_bytes: 0 } } },
  }, { data: {} });
  assert.ok(wsBudgetHtml.includes("工作空间总预算"));
  assert.ok(wsBudgetHtml.includes('name="storage_gib"'));

  const nodeHtml = renderCompute({
    path: "/monitor",
    params: new URLSearchParams({ node: "nod1" }),
    workspace: { id: "ws1" },
    workspaces: [{ id: "ws1", name: "算法一队" }],
    session: { user: { id: "u1", is_admin: false } },
    access: { actions: ["resources.read", "members.manage"] },
    data: {
      detail: {
        id: "nod1", workspace_id: "ws1", name: "本队机器", status: "在线", enabled: true, slots: 2,
        inventory: { hostname: "h1", platform: "linux", cpu_count: 4, memory_mb: 8192, runtime: { execution_contract_version: 1 } },
        devices: [{ id: "dev1", name: "RTX 4060", hardware_id: "nvidia:0", purpose: "train_eval", memory_mb: 8192, status: "空闲" }],
      },
      history: { device_id: "dev1", points: [] },
    },
  });
  assert.ok(nodeHtml.includes('data-action="gov-device-policy"'));
});
