import assert from "node:assert/strict";
import test from "node:test";
import { governanceDialog, saveGovernance } from "../live/governance.js";
import { nodeOptions, syncResourceNodes } from "../live/resource-options.js";
import { workflowDialog } from "../live/workflows.js";

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
