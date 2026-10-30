import test from "node:test";
import assert from "node:assert/strict";
import { dataDialog, isDataPage, loadDataWorkflow, renderDataWorkflow } from "../live/data-workflows.js";
import { renderAnnotation } from "../live/annotation-view.js";
import { saveDataWorkflow } from "../live/data-actions.js";
import { ensureDraft, renderWizard } from "../live/training-wizard.js";

function context(path = "/annotation") {
  return { path, page: 1, q: "", params: new URLSearchParams(), workspace: { id: "w1" }, access: { actions: ["datasets.read", "datasets.write", "training.write"] }, data: {} };
}

test("标注和数据处理独立加载真实接口，候选预览保留分区及分页", async () => {
  for (const path of ["/annotation", "/annotation/a1", "/augmentation", "/data-operations", "/data-operations/o1", "/datasets/d1/samples"]) assert.ok(isDataPage(path));
  const ctx = context("/data-operations/o1"); ctx.params.set("candidate", "2"); ctx.page = 3;
  const paths = [];
  const result = await loadDataWorkflow({ async request(path) { paths.push(path); return { data: paths.length === 1 ? { id: "o1", status: "review", candidates: [1, 2, 3] } : { samples: [], page: 3 } }; } }, ctx);
  assert.equal(result.candidate, 2); assert.ok(paths[1].includes("candidate=2&page=3"));
  const calls = []; await loadDataWorkflow({ async request(path) { calls.push(path); return { data: [] }; } }, context("/augmentation"));
  assert.ok(calls[0].includes("kind=augment"));
});

test("标注工作区转义样本文字，未审核完成不能发布，查看者不能写入", () => {
  const ctx = context("/annotation/a1");
  ctx.data = { id: "a1", name: "标注任务", version_id: "v1", status: "open", counts: { approved: 0, total: 1 }, can_edit: true, can_review: true,
    dataset: { id: "d1", name: "样本", task_type: "text_classification" }, source_version: { number: 1 }, labels: ["正", "负"], samples: [{ index: 0, source: { text: '<img src=x onerror="alert(1)">', label: "" } }], pagination: { page: 1, page_size: 20, total: 1 } };
  let html = renderAnnotation(ctx);
  assert.ok(html.includes("&lt;img") && !html.includes('<img src=x'));
  assert.match(html, /data-action="annotation-confirm-publish"[^>]*disabled/);
  assert.ok(html.includes('value="submit"') && html.includes('data-form="annotation-result"'));
  ctx.access.actions = ["datasets.read"]; html = renderAnnotation(ctx);
  assert.ok(!html.includes('value="submit"') && !html.includes('data-action="annotation-confirm-publish"'));
});

test("发布和取消使用确认弹窗；标注和增强配置提交真实业务字段", async () => {
  const ctx = context(), calls = [];
  ctx.dataChoices = { versions: [{ id: "v1", name: "图片", number: 1, task_type: "image_classification" }], members: [] };
  assert.ok(dataDialog({ kind: "data-annotation-new", item: {} }, ctx).fields.includes('name="assigned_to"'));
  const form = new FormData();
  for (const [key, value] of Object.entries({ name: "增强", version_id: "v1", kind: "augment", seed: "7", train_ratio: "0.8", validation_ratio: "0.1" })) form.set(key, value);
  form.append("methods", "flip");
  const destination = await saveDataWorkflow({ async request(path, input) { calls.push({ path, input }); return { data: { id: "op1" } }; } }, { kind: "data-operation-new", workspaceId: "w1" }, form, ctx);
  assert.equal(destination.destination, "/data-operations/op1");
  assert.deepEqual(calls[0].input.body.options.methods, ["flip"]); assert.equal(calls[0].input.body.options.seed, 7);
  assert.equal(dataDialog({ kind: "data-publish", item: { name: "增强", status: "review" } }, ctx).submit, "确认发布");
});

test("图像样本读取受控端点，版本可追溯且候选不会提前成为正式版本", () => {
  const ctx = context("/datasets/d1/samples");
  ctx.data = { item: { id: "d1", name: "图像数据", task_type: "image_classification" }, version: { id: "v1", provenance: { partition: "test" } }, versions: [{ id: "v1", number: 1, filename: "images.zip" }],
    samples: { page: 1, page_size: 20, total: 1, labels: { yes: 1 }, samples: [{ index: 0, filename: "images/a.png", label: "yes" }] } };
  const html = renderDataWorkflow(ctx);
  assert.ok(html.includes("/api/v1/workspaces/w1/dataset-versions/v1/images/0") && html.includes("测试集"));
  assert.ok(!html.includes("storage_key") && html.includes("/download"));
});

test("训练向导只提供训练与普通版本，排除独立验证和测试数据", () => {
  const ctx = context("/train/new");
  ctx.data.options = { models: [{ id: "m1", name: "模型", task_type: "text_classification" }], datasets: [
    { id: "v1", name: "训练版本", task_type: "text_classification", number: 1, sample_count: 10, provenance: { partition: "train" } },
    { id: "v2", name: "验证版本", task_type: "text_classification", number: 2, sample_count: 2, provenance: { partition: "validation" } },
    { id: "v3", name: "测试版本", task_type: "text_classification", number: 3, sample_count: 2, provenance: { partition: "test" } }] };
  ensureDraft(ctx).step = 1;
  const html = renderWizard(ctx);
  assert.ok(html.includes('value="v1"') && !html.includes('value="v2"') && !html.includes('value="v3"'));
});
