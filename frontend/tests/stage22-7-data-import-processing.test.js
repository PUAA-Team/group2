// Stage 22-7 数据导入、数据处理与标注批次列表视觉重做：导入向导步骤条与
// 校验统计条、样本预览悬停全文、字段映射计数；数据处理/标注列表名称省略与
// 进度条、区分空态；处理详情数字统计条；样本页统计条与文件名省略；
// 标注详情样本位置、队列悬停标签与图片文件名。
import test from "node:test";
import assert from "node:assert/strict";
import { renderDatasetImport } from "../live/dataset-import.js";
import { renderDataWorkflow } from "../live/data-workflows.js";
import { renderAnnotation } from "../live/annotation-view.js";

const workspace = { id: "w1", name: "研发组" };
const base = { workspace, workspaces: [workspace], params: new URLSearchParams(), page: 1, q: "",
  session: { user: { id: "u1", display_name: "管理", account: "admin", is_admin: true } },
  access: { actions: ["datasets.read", "datasets.write", "training.write", "assistants.use"], quota: {}, role: "admin" },
  templates: [], data: {} };
const LONG = "a".repeat(200);
const pagination = { total: 2, page: 1, page_size: 20 };

function check(html, label) {
  assert.equal(typeof html, "string", `${label} 未返回字符串`);
  assert.ok(!html.includes("undefined"), `${label} 泄露了 undefined`);
  assert.ok(!html.includes("NaN"), `${label} 泄露了 NaN`);
  return html;
}

function importCtx(draft) {
  return { ...base, data: {}, importDraft: { key: "new", workspaceId: "w1", name: "数据", task_type: "text_classification", file: null, preview: null, inspection: null, columnMapping: null, error: "", ...draft } };
}

test("导入向导：步骤条随草稿状态推进，校验结果改为数字统计条", () => {
  const fresh = check(renderDatasetImport(importCtx({})), "导入向导初始");
  assert.ok(fresh.includes('class="console-stepper"'), "向导应有步骤条");
  assert.ok(fresh.includes("基本信息") && fresh.includes("上传文件") && fresh.includes("字段映射") && fresh.includes("样本预览"), "步骤条应含四步");
  assert.ok(fresh.includes('aria-current="step"'), "当前步骤应标注 aria-current");
  assert.ok(!fresh.includes("live-stat-strip"), "无预览时不应渲染校验统计条");
  const file = { name: "data.csv", size: 2048 };
  const withFile = check(renderDatasetImport(importCtx({ file })), "导入向导已选文件");
  assert.ok(withFile.includes("✓") && withFile.includes("2.0 KiB"), "选文件后第一步应完成并显示文件大小");
  const preview = { status: "available", sample_count: 120, format: "csv", sha256: "ab".repeat(32), samples: [{ text: "你好", label: "正" }] };
  const done = check(renderDatasetImport(importCtx({ file, inspection: { columns: ["text", "label", "extra"], targets: [{ name: "text", required: true }, { name: "label", required: true }] }, columnMapping: { text: "text", label: "label" }, preview })), "导入向导已预览");
  assert.ok(done.includes('class="live-stat-strip"'), "校验结果应渲染为数字统计条");
  assert.ok(done.includes("样本数") && done.includes("<strong>120</strong>"), "统计条应有样本数");
  assert.ok(done.includes("<strong>CSV</strong>") && done.includes("<strong>1</strong>"), "统计条应有格式与预览条数");
  assert.ok(done.includes("ab".repeat(32)), "SHA256 仍应展示");
  assert.ok(done.includes("已映射 2/2"), "字段映射区应显示已映射计数");
  assert.ok(done.includes("未导入字段") && done.includes(">extra<"), "未映射的原字段应打标记");
});

test("导入样本预览：超长单元格悬停查看全文，列名转义", () => {
  const preview = { status: "available", sample_count: 1, format: "csv", sha256: "x".repeat(64),
    samples: [{ text: `超长文本${LONG}`, label: "正" }] };
  const html = check(renderDatasetImport(importCtx({ file: { name: "d.csv", size: 10 }, preview })), "导入样本预览");
  assert.ok(html.includes(`class="live-sample" title="超长文本${LONG}"`), "超长样本值应悬停查看全文");
  const xss = { status: "available", sample_count: 1, format: "csv", sha256: "x".repeat(64), samples: [{ "<b>注入</b>": "<script>alert(1)</script>" }] };
  const safe = check(renderDatasetImport(importCtx({ file: { name: "d.csv", size: 10 }, preview: xss })), "导入样本预览注入");
  assert.ok(safe.includes("&lt;b&gt;注入&lt;/b&gt;") && !safe.includes("<script>alert"), "列名与样本值均应转义");
});

test("数据处理列表：名称超长省略、进度条带百分比、空态按类型区分", () => {
  const rows = [
    { id: "o1", name: `超长处理任务${LONG}`, kind: "clean", dataset_name: "数据", version_number: 1, status: "running", progress: { done: 30, total: 40 }, created_at: "2026-11-27T00:00:00Z" },
    { id: "o2", name: "未开始", kind: "augment", dataset_name: "数据", version_number: 2, status: "queued", progress: {}, created_at: "2026-11-27T00:00:00Z" },
  ];
  const ctx = { ...base, path: "/data-operations", data: { data: rows, pagination } };
  const html = check(renderDataWorkflow(ctx), "数据处理列表");
  assert.ok(html.includes(`class="live-source" title="超长处理任务${LONG}"`), "超长任务名应省略并悬停查看");
  assert.ok(html.includes('class="data-progress"') && html.includes('data-progress="75"') && html.includes("30/40"), "已处理应为进度条加数值");
  assert.ok(html.includes("<td>—</td>"), "无总数的任务已处理应显示缺失占位");
  const emptyOps = check(renderDataWorkflow({ ...base, path: "/data-operations", data: { data: [], pagination } }), "数据处理空列表");
  assert.ok(emptyOps.includes("暂无数据处理任务"), "数据处理空态应区分文案");
  const emptyAug = check(renderDataWorkflow({ ...base, path: "/augmentation", data: { data: [], pagination } }), "数据增强空列表");
  assert.ok(emptyAug.includes("暂无数据增强任务"), "数据增强空态应区分文案");
  const filtered = check(renderDataWorkflow({ ...base, path: "/data-operations", q: "不存在", data: { data: [], pagination } }), "数据处理带筛选空列表");
  assert.ok(filtered.includes("没有符合筛选条件的任务"), "带筛选条件时空态应说明无匹配结果");
});

test("标注批次列表：已审核改为进度条，空态区分", () => {
  const ctx = { ...base, path: "/annotation", data: { data: [
    { id: "a1", name: "标注批次", dataset_name: "数据", version_number: 1, task_type: "text_classification", status: "open", counts: { approved: 5, total: 20 }, created_at: "2026-11-27T00:00:00Z" },
  ], pagination } };
  const html = check(renderDataWorkflow(ctx), "标注批次列表");
  assert.ok(html.includes('class="data-progress"') && html.includes('data-progress="25"') && html.includes("5/20"), "已审核应为进度条加数值");
  const empty = check(renderDataWorkflow({ ...base, path: "/annotation", data: { data: [], pagination } }), "标注批次空列表");
  assert.ok(empty.includes("暂无标注批次"), "标注批次空态应区分文案");
});

test("数据处理详情：已处理/候选分区/已发布版本统计条，进度带百分比", () => {
  const item = { id: "o1", name: "清洗", kind: "clean", status: "review", dataset_name: "数据", dataset_id: "d1", version_number: 1, version_id: "v1",
    options: { seed: 42 }, progress: { phase: "处理中", done: 30, total: 40 }, created_at: "2026-11-27T00:00:00Z",
    candidates: [{ partition: "train", sample_count: 30 }, { partition: "validation", sample_count: 10 }], output_version_ids: [], task_type: "text_classification" };
  const preview = { page: 1, page_size: 20, total: 30, labels: {}, samples: [{ index: 0, text: "样本", label: "正" }] };
  const ctx = { ...base, path: "/data-operations/o1", data: { item, preview, candidate: 0 } };
  const html = check(renderDataWorkflow(ctx), "数据处理详情");
  assert.ok(html.includes('class="live-stat-strip"'), "详情应有数字统计条");
  assert.ok(html.includes("已处理") && html.includes("<strong>30/40</strong>"), "统计条应有已处理数值");
  assert.ok(html.includes('data-progress="75"'), "统计条内应有进度条");
  assert.ok(html.includes("候选分区") && html.includes("<strong>2</strong>"), "统计条应有候选分区数");
  assert.ok(html.includes("75%"), "处理进度字段应带百分比");
  assert.ok(html.includes("处理中 · 75%"), "处理进度应保留阶段文字并追加百分比");
  const failed = check(renderDataWorkflow({ ...base, path: "/data-operations/o1", data: { item: { ...item, status: "failed", error: "磁盘已满", candidates: [], output_version_ids: [] }, preview: null, candidate: 0 } }), "数据处理失败详情");
  assert.ok(failed.includes("磁盘已满") && failed.includes("notice-danger"), "失败任务应显示错误提示");
  assert.ok(failed.includes("<strong>—</strong>"), "无总数的失败任务已处理应显示缺失占位");
});

test("样本浏览页：统计条含样本总数与标签种类，图片文件名省略悬停", () => {
  const ctx = { ...base, path: "/datasets/d1/samples", data: { item: { id: "d1", name: "图像数据", task_type: "image_classification" },
    version: { id: "v1", provenance: { partition: "test" } }, versions: [{ id: "v1", number: 1, filename: "images.zip" }],
    samples: { page: 1, page_size: 20, total: 3, labels: { yes: 2, no: 1 }, samples: [{ index: 0, filename: `images/${LONG}.png`, label: "yes" }] } } };
  const html = check(renderDataWorkflow(ctx), "样本浏览页");
  assert.ok(html.includes('class="live-stat-strip"'), "样本页应有数字统计条");
  assert.ok(html.includes("样本总数") && html.includes("<strong>3</strong>"), "统计条应有样本总数");
  assert.ok(html.includes("标签种类") && html.includes("<strong>2</strong>"), "统计条应有标签种类");
  assert.ok(html.includes("当前页样本") && html.includes("<strong>1</strong>"), "统计条应有当前页样本数");
  assert.ok(html.includes(`class="live-source" title="images/${LONG}.png"`), "超长文件名应省略并悬停查看");
  const textCtx = { ...base, path: "/datasets/d1/samples", data: { item: { id: "d1", name: "文本数据", task_type: "text_classification" },
    version: { id: "v1", provenance: {} }, versions: [{ id: "v1", number: 1, filename: "data.csv" }],
    samples: { page: 1, page_size: 20, total: 1, labels: {}, samples: [{ index: 0, text: `长文本${LONG}`, label: "" }] } } };
  const textHtml = check(renderDataWorkflow(textCtx), "文本样本浏览页");
  assert.ok(textHtml.includes(`title="长文本${LONG}"`), "文本样本应悬停查看全文");
  assert.ok(textHtml.includes("标签种类") && textHtml.includes("<strong>0</strong>"), "无标签时标签种类应为 0 而非缺失");
});

test("标注详情：样本位置、队列悬停标签、图片文件名", () => {
  const ctx = { ...base, path: "/annotation/a1", data: { id: "a1", name: "标注任务", version_id: "v1", status: "open", counts: { approved: 1, total: 3 }, can_edit: true, can_review: true,
    dataset: { id: "d1", name: "图像", task_type: "image_classification" }, source_version: { number: 1 }, labels: ["猫", "狗"],
    samples: [
      { index: 0, source: { filename: `images/${LONG}.png`, label: "猫" }, result: { state: "approved", value: "猫", revision: 1 } },
      { index: 1, source: { filename: "images/b.png", label: "" } },
    ], pagination: { page: 1, page_size: 20, total: 3 } } };
  const html = check(renderAnnotation(ctx), "标注详情图片样本");
  assert.ok(html.includes("样本 1 / 共 3 个"), "内容标题应给出样本位置与总数");
  assert.ok(html.includes('title="已通过 · 猫"'), "队列项悬停应显示状态与当前标签");
  assert.ok(html.includes('title="草稿 · 未标注"'), "未标注样本队列项应有悬停说明");
  assert.ok(html.includes(`class="annotation-file live-source" title="images/${LONG}.png"`), "图片样本应显示文件名且超长省略");
});
