import test from "node:test";
import assert from "node:assert/strict";
import { loadResults, renderResults, renderCallHistory } from "../live/results.js";
import { renderWorkflow, saveWorkflow, workflowDialog } from "../live/workflows.js";

const context = path => ({ path, page: 1, params: new URLSearchParams(), workspace: { id: "w1" },
  access: { actions: ["training.read", "services.write"] }, data: {} });

test("评估对比保留全部所选ID，缺失指标不补零", async () => {
  const ctx = context("/evaluation/compare"); ctx.params.append("ids", "one"); ctx.params.append("ids", "two");
  let endpoint;
  await loadResults({ async request(path) { endpoint = path; return { data: {} }; } }, ctx);
  const query = new URLSearchParams(endpoint.split("?")[1]); assert.deepEqual(query.getAll("ids"), ["one", "two"]);
  ctx.data = { dataset: { id: "d1", name: "固定数据", number: 1 }, task_type: "text_classification", config: {},
    items: [{ id: "one", name: "<img>", metrics: { accuracy: 0 }, model_name: "分类" }, { id: "two", metrics: { loss: 0.5 }, model_name: "分类" }] };
  const html = renderResults(ctx); assert.ok(html.includes("0.00%") && html.includes("—"));
  assert.ok(html.includes("&lt;img&gt;") && !html.includes("<img>"));
});

test("只有已完成评估可选择，对比操作使用独立页面", () => {
  const ctx = context("/evaluation"); ctx.data = { data: [{ id: "one", name: "运行中", kind: "evaluate", status: "running", result: {} }] };
  const html = renderWorkflow(ctx); assert.match(html, /name="ids"[^>]*disabled/);
  assert.ok(html.includes('data-form="evaluation-compare"'));
});

test("调用历史不渲染请求正文，未知耗时显示缺失", () => {
  const ctx = context("/runs/s1"); ctx.data.callHistory = { data: [{ id: "c1", status: "failed", input: { text: "private-input" }, result: { text: "private-output" } }] };
  const html = renderCallHistory(ctx);
  assert.ok(!html.includes("private-") && html.includes("—"));
});

test("运行中的评估不提供错误样本入口", () => {
  const ctx = context('/runs/e1');
  ctx.data.item = { id: 'e1', name: '评估', kind: 'evaluate', status: 'running', config: {}, snapshot: {}, result: {} };
  assert.ok(!renderWorkflow(ctx).includes('/evaluation/errors/'));
});

test("密钥轮换经过确认弹窗，新值仅留内存", async () => {
  const ctx = context("/api-keys");
  const modal = { kind: "key-rotate", workspaceId: "w1", item: { id: "k1", name: "内部服务" } };
  assert.equal(workflowDialog(modal, ctx).submit, "确认轮换");
  let endpoint;
  await saveWorkflow({ async request(path) { endpoint = path; return { data: { key: "one-time-value" } }; } }, modal, new FormData(), ctx);
  assert.ok(endpoint.endsWith("/k1/rotate")); assert.equal(ctx.generatedKey, "one-time-value");
});
