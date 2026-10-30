import test from "node:test";
import assert from "node:assert/strict";
import { computeDialog, renderCompute } from "../live/compute.js";

const node = { id: "nod_1", name: "GPU 开发机", workspace_id: "wsp_1", status: "在线", slots: 2,
  inventory: { hostname: "host", platform: "Windows", cpu_count: 8, memory_mb: 16000, runtime: { cuda_available: true, torch_version: "2.5" } },
  devices: [{ name: "RTX 4060", kind: "cuda", present: true, memory_mb: 8188, metrics: { utilization: null }, status: "空闲" }] };
const ctx = { path: "/admin/resources", params: new URLSearchParams(), q: "", workspace: { id: "wsp_1" }, workspaces: [{ id: "wsp_1", name: "研发" }],
  session: { user: { is_admin: true }, access: { actions: ["resources.read", "resources.manage"] } }, access: { actions: ["resources.read", "resources.manage"] },
  data: { data: [node], runtime: { local_enabled: true, runtimes: [{ id: "llm", configured: true, name: "Qwen" }] } } };

test("资源页显示真实硬件，未知利用率不冒充零", () => {
  const html = renderCompute(ctx);
  assert.ok(html.includes("RTX 4060") && html.includes("8188 MiB"));
  assert.ok(html.includes("CUDA 就绪") && !html.includes("0%"));
  assert.ok(html.includes("接入本机") && html.includes("生成接入命令"));
});
test("查看者资源页没有接入或变更操作", () => {
  const html = renderCompute({ ...ctx, path: "/monitor", session: { user: { is_admin: false }, access: { actions: ["resources.read", "resources.manage"] } }, access: { actions: ["resources.read"] } });
  assert.ok(!html.includes("生成接入命令") && !html.includes("接入本机"));
});
test("接入命令显示遮蔽版本，复制内容保留在受控状态", () => {
  const html = renderCompute({ ...ctx, params: new URLSearchParams("tab=connect"), resourceConnection: { command: "do secret-code", display_command: "do <一次性接入码>" }, data: { ...ctx.data, connectionReceipt: { status: "等待连接" } } });
  assert.ok(!html.includes("secret-code") && html.includes("&lt;一次性接入码&gt;"));
  assert.ok(html.includes("复制完整命令"));
});
test("资源新增和节点修改提供完整弹窗字段", () => {
  const definition = computeDialog({ kind: "enroll-new" }, ctx);
  assert.ok(definition.fields.includes('name="controller_url"') && definition.fields.includes('name="workspace_id"'));
  const edit = computeDialog({ kind: "node-edit", item: node }, ctx);
  assert.ok(edit.fields.includes("审核准入"));
  assert.ok(computeDialog({ kind: "local-worker" }, ctx).fields.includes("Qwen"));
});
