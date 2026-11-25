import assert from "node:assert/strict";
import test from "node:test";
import { computeDialog, loadCompute, renderCompute } from "../live/compute.js";
import { governanceDialog, saveGovernance } from "../live/governance.js";
import { nodeOptions, syncResourceNodes } from "../live/resource-options.js";
import { saveWorkflow, workflowDialog } from "../live/workflows.js";

const node = (id, kind, purpose, selectable = true) => ({ id, name: id, devices: [{ kind, purpose, selectable }] });
const nodes = [
  node("trainer", "cpu", "train_eval"), node("server", "cpu", "inference"),
  node("shared", "cpu", "shared"), node("gpu", "cuda", "inference"), node("denied", "cpu", "shared", false),
];

test("训练、评估和部署按设备用途过滤，仍可选共享设备", () => {
  for (const kind of ["train", "evaluate"]) {
    const choices = nodeOptions(nodes, kind, "cpu");
    assert.match(choices, /trainer/);
    assert.match(choices, /shared/);
    assert.doesNotMatch(choices, /server|gpu|denied/);
  }
  const dialog = workflowDialog({ kind: "job-new", item: { kind: "service" } }, { data: { nodes } });
  assert.match(dialog.fields, /data-resource-kind="service"/);
  assert.match(dialog.fields, /value="server"/);
  assert.doesNotMatch(dialog.fields, /value="trainer"|value="denied"/);
  assert.match(nodeOptions(nodes, "train", "cpu", "server"), /server（不可选）/);
});

test("切换到 GPU 刷新节点选项，移除旧的 CPU 节点", () => {
  const select = { value: "server", innerHTML: "" };
  syncResourceNodes({ value: "cuda", dataset: { resourceKind: "service" },
    form: { elements: { namedItem: name => name === "node_id" ? select : null } } }, nodes);
  assert.match(select.innerHTML, /value="gpu"/);
  assert.doesNotMatch(select.innerHTML, /server/);
});

test("设备策略保留版本与授权并提交明确的用途", async () => {
  const modal = { kind: "gov-device-policy", item: {
    id: "device", policy: { revision: 2, enabled: true, purpose: "train_eval",
      allow_users: ["operator"], allow_groups: [], deny_users: [], deny_groups: [] },
    principals: { users: [{ id: "operator", name: "值班员" }], groups: [] },
  } };
  assert.match(governanceDialog(modal).fields, /train_eval" selected/);
  const form = new FormData();
  form.set("purpose", "inference"); form.set("enabled", "on"); form.set("allow_users", "operator");
  let request;
  await saveGovernance({ request: async (path, options) => { request = { path, ...options }; } }, modal, form);
  assert.equal(request.path, "/resources/devices/device/policy");
  assert.equal(request.body.revision, 2);
  assert.equal(request.body.purpose, "inference");
  assert.deepEqual(request.body.allow_users, ["operator"]);
});

test("排队中任务支持调整优先级并按修订号提交", async () => {
  const modal = { kind: "job-priority", workspaceId: "ws-1", item: { id: "job-1", name: "文本训练", priority: 2, revision: 4 } };
  const dialog = workflowDialog(modal, { data: {} });
  assert.equal(dialog.title, "调整排队优先级");
  assert.match(dialog.fields, /name="priority"[^>]*value="2"/);
  const form = new FormData();
  form.set("priority", "8");
  let request;
  await saveWorkflow({ request: async (path, options) => { request = { path, ...options }; } }, modal, form, {});
  assert.equal(request.path, "/workspaces/ws-1/jobs/job-1/priority");
  assert.equal(request.method, "PATCH");
  assert.equal(request.revision, 4);
  assert.deepEqual(request.body, { priority: 8 });
});

test("资源页支持设备类型与用途筛选并透传查询参数", async () => {
  const calls = [];
  const params = new URLSearchParams("device_kind=cuda&purpose=inference");
  const ctx = {
    path: "/admin/resources", page: 1, q: "", params,
    workspace: { id: "ws-1" }, workspaces: [{ id: "ws-1", name: "默认空间" }],
    session: { user: { is_admin: true }, access: { actions: ["resources.read"] } },
    access: { actions: ["resources.read"] },
    data: { data: [], pagination: { page: 1, page_size: 20, total: 0 } },
  };
  await loadCompute({ request: async path => { calls.push(path); return { data: [], pagination: { page: 1, page_size: 20, total: 0 } }; } }, ctx);
  assert.match(calls[0], /\/admin\/nodes\?.*device_kind=cuda.*purpose=inference/);
  const html = renderCompute(ctx);
  assert.match(html, /data-query-filter="device_kind"/);
  assert.match(html, /data-query-filter="purpose"/);
});
