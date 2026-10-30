import test from "node:test";
import assert from "node:assert/strict";
import { isWorkflowPage, metricChart, renderWorkflow, workflowDialog, saveWorkflow, workflowAction } from "../live/workflows.js";

const workspace = { id: "wsp-test" };
const ctx = { path: "/runs", workspace, params: new URLSearchParams(), access: { actions: ["training.read", "training.write", "services.write"], quota: { concurrent_jobs: 2 } }, data: { data: [], options: { models: [], datasets: [] }, projects: [], nodes: [] } };

test("训练列表状态只显示统一符号，名称转义并可进入详情", () => {
  const html = renderWorkflow({ ...ctx, data: { data: [{ id: "j1", name: "<危险>", status: "running", device_kind: "cuda", result: {}, created_at: "2026-10-29T00:00:00Z" }] } });
  assert.ok(html.includes("&lt;危险&gt;") && !html.includes("<危险>"));
  assert.ok(html.includes('href="#/runs/j1"') && html.includes('data-status="运行中"'));
  assert.ok(html.includes('data-action="workflow-new"'));
  assert.ok(!renderWorkflow({ ...ctx, access: { actions: ["training.read"] } }).includes('data-action="workflow-new"'));
});

test("Qwen 新建表单选择 GPU 和微调参数，筛选数据类型", () => {
  const data = { ...ctx.data, options: { models: [{ id: "qwen", name: "Qwen", version: "base-v1", task_type: "llm_sft" }], datasets: [{ id: "sft", name: "指令", number: 1, task_type: "llm_sft" }, { id: "text", name: "文本", number: 1, task_type: "text_classification" }] } };
  const dialog = workflowDialog({ kind: "job-new", item: { kind: "train" } }, { ...ctx, data });
  assert.ok(dialog.fields.includes('value="cuda" selected'));
  assert.ok(dialog.fields.includes('value="0.0002"'));
  assert.ok(dialog.fields.includes('value="sft"') && !dialog.fields.includes('value="text"'));
});

test("提交使用服务端草稿 revision，草稿保存不提交", async () => {
  const calls = [];
  const api = { async request(path, options) { calls.push([path, options]); return { data: { id: "job-created", revision: 3 } }; } };
  const form = new FormData();
  for (const [key, value] of Object.entries({ name: "测试", model_version_id: "m1", dataset_version_id: "d1", device_kind: "cpu", epochs: 2, batch_size: 4, learning_rate: 0.01, validation_ratio: 0.2, seed: 42, max_length: 128, lora_rank: 4, submit_now: "on" })) form.set(key, value);
  const result = await saveWorkflow(api, { kind: "job-new", item: { kind: "train" }, workspaceId: "w1" }, form, ctx);
  assert.equal(result.destination, "/runs/job-created"); assert.equal(calls[1][1].revision, 3);
  calls.length = 0; form.delete("submit_now");
  await saveWorkflow(api, { kind: "job-new", item: { kind: "train" }, workspaceId: "w1" }, form, ctx);
  assert.equal(calls.length, 1);
});

test("真实曲线区分缺失指标和零，路由完整", () => {
  assert.ok(metricChart([], ["loss", "val_loss"], "Loss").includes("暂无指标"));
  assert.ok(metricChart([{ type: "metric", payload: { epoch: 1, loss: 0 } }], ["loss", "val_loss"], "Loss").includes("<circle"));
  for (const path of ["/projects", "/runs", "/evaluation", "/services", "/api-keys", "/runs/job-1", "/admin/jobs"]) assert.ok(isWorkflowPage(path));
});

test("Qwen 训练不显示无数据的分类准确率图", () => {
  const html = renderWorkflow({ ...ctx, path: "/runs/j1", params: new URLSearchParams("tab=metrics"), data: { item: { id: "j1", kind: "train", status: "running", name: "Qwen", config: {}, snapshot: { task_type: "llm_sft", trainer_id: "qwen-lora-v1" } }, events: [] } });
  assert.ok(html.includes("execution-single-chart"));
  assert.ok(!html.includes("<h2>准确率</h2>"));
});

test("部署Qwen可确认任务指令和标签，调用表单只填写正文", () => {
  const profile = { mode: "label", instruction: "Classify the SMS.", labels: ["ham", "spam"] };
  const model = { id: "q", trainer_id: "qwen-lora-v1", name: "Qwen", version: "v1", status: "available", task_type: "llm_sft", inference_suggestion: profile };
  const dialog = workflowDialog({ kind: "job-new", item: { kind: "service" } }, { ...ctx, data: { ...ctx.data, options: { models: [model], datasets: [] } } });
  assert.ok(dialog.fields.includes('value="label" selected') && dialog.fields.includes("Classify the SMS."));
  assert.ok(dialog.fields.includes("ham\nspam"));
  const call = workflowDialog({ kind: "service-invoke", item: { config: { inference: profile }, snapshot: { task_type: "llm_sft" } } }, ctx);
  assert.ok(call.fields.includes("ham") && !call.fields.includes("Classify the SMS."));
});

test("分类部署显式保存契约，服务结果显示标签", async () => {
  const calls = [], form = new FormData();
  for (const [key, value] of Object.entries({ name: "短信分类", model_version_id: "m1", device_kind: "cuda", inference_mode: "label", inference_instruction: "Classify.", inference_labels: "ham\nspam" })) form.set(key, value);
  await saveWorkflow({ async request(path, options) { calls.push(options.body); return { data: { id: "s1", revision: 1 } }; } }, { kind: "job-new", item: { kind: "service" }, workspaceId: "w1" }, form, ctx);
  assert.deepEqual(calls[0].config.inference, { mode: "label", instruction: "Classify.", labels: ["ham", "spam"] });
  const html = renderWorkflow({ ...ctx, path: "/runs/s1", access: { actions: ["services.invoke"] }, callResult: { job_id: "s1", result: { label: "spam", text: "spam" } }, data: { item: { id: "s1", name: "短信", kind: "service", status: "ready", config: { inference: calls[0].config.inference }, snapshot: { task_type: "llm_sft" } }, events: [] } });
  assert.ok(html.includes("分类结果") && html.includes('class="chip">spam'));
});

test("旧Qwen服务重跑提交前先确认推理配置", async () => {
  let requests = 0, opened;
  const job = { id: "s1", kind: "service", config: {}, snapshot: {}, model_version_id: "q1", revision: 1 };
  const data = { ...ctx.data, item: job, options: { models: [{ id: "q1", trainer_id: "qwen-lora-v1" }], datasets: [] } };
  await workflowAction("workflow-submit", "s1", { ctx: { ...ctx, data }, api: { async request() { requests++; return {}; } }, openModal(kind) { opened = kind; }, load: async () => {} });
  assert.equal(opened, "job-edit"); assert.equal(requests, 0);
});
