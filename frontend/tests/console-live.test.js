import test from "node:test";
import assert from "node:assert/strict";
import { captureDraft, ensureDraft, initialDraft, persistTraining, renderWizard, updateTask } from "../live/training-wizard.js";
import { persistImport, renderDatasetImport } from "../live/dataset-import.js";
import { renderTrainingDetail } from "../live/job-detail.js";
import { pageChanged } from "../live/page-events.js";

function context(query = "") {
  return { workspace: { id: "w1" }, params: new URLSearchParams(query), access: { actions: ["training.write", "datasets.write"] }, data: {
    options: { models: [{ id: "m1", name: "文本模型", version: "v1", task_type: "text_classification", trainer_id: "text-classifier-v1" }, { id: "q1", name: "Qwen", version: "base-v1", task_type: "llm_sft", trainer_id: "qwen-lora-v1" }],
      datasets: [{ id: "d1", dataset_id: "data1", name: "文本数据", task_type: "text_classification", number: 1, sample_count: 20 }] }, projects: [], nodes: [] } };
}

test("四步训练使用各自字段，切步和重绘保留配置", () => {
  const ctx = context();
  const draft = ensureDraft(ctx); draft.values.name = "真实任务"; draft.values.dataset_version_id = "d1";
  const captions = ["任务与模型", "数据集", "参数与资源", "核对提交"];
  for (let step = 0; step < 4; step++) {
    draft.step = step;
    const html = renderWizard(ctx);
    assert.ok(html.includes(captions[step]) && html.includes('data-form="training-wizard"'));
    assert.equal(ensureDraft(ctx).values.name, "真实任务");
  }
  const fields = new FormData(); fields.set("learning_rate", "0.002");
  captureDraft(draft, fields); assert.equal(draft.values.learning_rate, 0.002);
  ctx.workspace = { id: "w2" }; assert.equal(ensureDraft(ctx).values.name, "");
});

test("更换任务切换兼容模型和默认参数，复制任务不修改原记录", () => {
  const ctx = context(), draft = initialDraft(ctx);
  updateTask(draft, ctx.data.options, "llm_sft", "q1");
  assert.equal(draft.values.device_kind, "cuda"); assert.equal(draft.values.batch_size, 1); assert.equal(draft.values.dataset_version_id, "");
  const source = { id: "job1", name: "原实验", model_version_id: "q1", dataset_version_id: "sft1", config: { epochs: 3 } };
  const copy = initialDraft(context("copy=job1"), source);
  assert.equal(copy.editId, null); assert.equal(copy.values.name, "原实验 · 副本"); assert.equal(copy.values.epochs, 3); assert.equal(source.name, "原实验");
});

test("数据版本选择后立即更新预览按钮并清除旧样本", t => {
  const ctx = context(); ensureDraft(ctx).step = 1; ctx.wizard.preview = { samples: [{ text: "旧样本" }] };
  const values = new FormData(); values.set("dataset_version_id", "d1");
  t.mock.method(globalThis, "FormData", function(form) { return form.values; });
  let renders = 0;
  const target = { form: { dataset: { form: "training-wizard" }, values }, matches(selector) { return selector === "[data-wizard-dataset]"; } };
  pageChanged(target, ctx, () => { renders++; });
  assert.equal(renders, 1); assert.equal(ctx.wizard.values.dataset_version_id, "d1"); assert.equal(ctx.wizard.preview, null);
});

test("训练提交失败重试沿用已创建草稿，不重复创建任务", async () => {
  const ctx = context(); ctx.wizard = initialDraft(ctx); Object.assign(ctx.wizard.values, { name: "实验", dataset_version_id: "d1" });
  let creates = 0, submits = 0;
  const api = { async request(path, options = {}) {
    if (options.method === "POST" && path.endsWith("/jobs")) { creates++; return { data: { id: "j1", revision: 1, status: "draft" } }; }
    if (path.endsWith("/submit")) { submits++; if (submits === 1) throw new Error("暂时失败"); return { data: { id: "j1", revision: 2, status: "queued" } }; }
    return { data: { id: "j1", revision: 1, status: "draft" } };
  } };
  await assert.rejects(persistTraining(api, ctx, true));
  assert.equal(await persistTraining(api, ctx, true), "/runs/j1"); assert.equal(creates, 1); assert.equal(submits, 2);
});

test("上传失败重试保留资产ID，文件内容和预览不会持久化到浏览器", async () => {
  const file = new File(["text,label\na,x\nb,y\n"], "sample.csv", { type: "text/csv" });
  const draft = { workspaceId: "w1", name: "样本", task_type: "text_classification", file, preview: { samples: [] } };
  let creates = 0, uploads = 0;
  const api = { async request(path) {
    if (path.endsWith("/datasets")) { creates++; return { data: { id: "d1" } }; }
    uploads++; if (uploads === 1) throw new Error("网络失败"); return { data: { id: "v1" } };
  } };
  await assert.rejects(persistImport(api, draft));
  assert.equal(await persistImport(api, draft), "/datasets/d1"); assert.equal(creates, 1); assert.equal(uploads, 2);
});

test("独立导入页和任务日志转义正文，指标来自传入真实事件", () => {
  const ctx = context();
  ctx.importDraft = { key: "new", workspaceId: "w1", name: "<b>数据</b>", task_type: "text_classification", file: null, preview: null };
  const html = renderDatasetImport(ctx); assert.ok(html.includes("&lt;b&gt;数据&lt;/b&gt;") && html.includes('data-form="dataset-import"'));
  ctx.params = new URLSearchParams("tab=logs&log_q=ERROR");
  ctx.data.item = { id: "j1", name: "训练", kind: "train", status: "running", config: {}, result: {} };
  ctx.data.events = [{ type: "log", payload: { message: "INFO 开始" } }, { type: "log", payload: { message: "ERROR <script>" } }];
  const logs = renderTrainingDetail(ctx, () => { throw new Error("日志页不渲染图表"); });
  assert.ok(logs.includes("ERROR &lt;script&gt;") && !logs.includes("INFO 开始") && logs.includes("下载完整日志"));
});
