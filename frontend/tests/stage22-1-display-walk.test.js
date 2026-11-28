// Stage 22-1 前端显示走查：全页面渲染器用对抗数据（注入字符、超长无断行串、
// 缺失的可选字段）渲染，断言不抛错、不泄露 undefined/NaN、不输出未转义标记。
// 覆盖工作台、用户空间、训练详情、资源监控、评估对比、智能辅助、在线标注、
// 资产目录、训练向导、导入页、管理端与全部弹窗。
import test from "node:test";
import assert from "node:assert/strict";
import { renderHome, renderPending, renderSpace } from "../live/pages/overview.js";
import { renderAssets, renderAssetDetail } from "../live/pages/assets.js";
import { renderUsers, renderAudit } from "../live/pages/admin.js";
import { renderAssetCatalog, renderProjectCatalog } from "../live/catalog.js";
import { renderTrainingDetail } from "../live/job-detail.js";
import { renderCompute } from "../live/compute.js";
import { renderResults, renderCallHistory, renderEvaluationReport } from "../live/results.js";
import { renderAssistant } from "../live/assistant.js";
import { renderAnnotation } from "../live/annotation-view.js";
import { renderWorkflow, workflowDialog, metricChart } from "../live/workflows.js";
import { renderWizard, ensureDraft } from "../live/training-wizard.js";
import { renderDatasetImport } from "../live/dataset-import.js";
import { renderDataWorkflow } from "../live/data-workflows.js";
import { renderProjectDetail } from "../live/projects.js";
import { renderKeys } from "../live/key-management.js";
import { renderManagement } from "../live/administration.js";
import { renderDialog } from "../live/dialogs.js";
import { governanceDialog, historyHtml } from "../live/governance.js";

const XSS = '<script>alert("x")</script><img src=x onerror="alert(1)">';
const LONG = "a".repeat(200);
const workspace = { id: "wsp_1", name: `研发组${XSS}`, owner_id: "usr_1" };
const session = { user: { id: "usr_1", display_name: `管理${XSS}`, account: "admin", is_admin: true }, access: { actions: ["workspaces.create", "resources.manage"] } };
const base = { workspace, workspaces: [workspace], session, params: new URLSearchParams(), page: 1, q: "", groups: [],
  access: { actions: ["models.write", "datasets.write", "members.manage", "training.read", "training.write", "services.write", "assistants.use", "resources.manage"], quota: {}, role: "admin" },
  data: {}, templates: [{ id: "text-classifier-v1", task_type: "text_classification", name: "文本分类" }] };

// 渲染结果必须是不含未转义标记与 undefined/NaN 泄露的 HTML 字符串。
function check(html, label) {
  assert.equal(typeof html, "string", `${label} 未返回字符串`);
  assert.ok(!html.includes("<script>"), `${label} 输出未转义的 script`);
  assert.ok(!html.includes("<img src=x"), `${label} 输出未转义的 img`);
  assert.ok(!html.includes("undefined"), `${label} 泄露了 undefined`);
  assert.ok(!html.includes("NaN"), `${label} 泄露了 NaN`);
  return html;
}

test("工作台：对抗任务名、空统计与空活动均可渲染", () => {
  const html = check(renderHome({ ...base, data: { counts: { projects: null, active: 0, queued: null, succeeded: 3, datasets: null },
    recent_jobs: [{ id: "j1", name: XSS, task_type: "text_classification", status: "running", result: {}, model_name: LONG, created_at: "2026-11-27T00:00:00Z" }],
    activity: [{ action: "jobs.create", actor_name: XSS, created_at: "2026-11-27T00:00:00Z" }],
    pending_items: [{ href: "/runs?status=queued", label: XSS, count: 2 }] } }), "工作台");
  assert.ok(html.includes("&lt;script&gt;") && html.includes("最近训练"));
  check(renderHome({ ...base, data: {} }), "工作台空数据");
  assert.ok(renderPending("/runs").includes("训练执行待接入"));
});

test("用户空间：对抗成员、邀请码、会话与预算账单均可渲染", () => {
  const gov = { budget: { concurrent_jobs: 2, gpu_count: 1, storage_gib: 10, usage: { concurrent_jobs: 1, gpu_count: 0, storage_bytes: 2097152 } },
    members: [{ display_name: XSS, account: "member", role: "editor", quota: {}, storage_bytes: 1024, jobs: { total: 2, active: 1, succeeded: 1 }, gpu_seconds: 3600, assistant_tokens: 5 }] };
  const html = check(renderSpace({ ...base, data: {
    members: { data: [{ user_id: "u2", display_name: XSS, account: "m@t", role: "editor", quota: {} }], pagination: { total: 1, page: 1, page_size: 20 } },
    invites: [{ code_preview: LONG, role: "viewer", require_approval: false, used_count: 1, max_uses: null, expires_at: null, revoked_at: null, id: "inv1" }],
    joinRequests: [{ display_name: XSS, account: "a", requested_role: "viewer", status: "pending", id: "r1" }],
    sessions: [{ id: LONG, created_at: "2026-11-27T00:00:00Z", expires_at: null, current: true }],
    storage: { personal_bytes: 0, workspace_bytes: 0, categories: {}, unattributed_bytes: 0 },
    myJobs: [{ id: "j1", name: XSS, task_type: "text_classification", status: "failed", created_at: null }],
    governanceSummary: gov } }), "用户空间");
  assert.ok(html.includes("&lt;script&gt;") && html.includes("空间预算与成员账单"));
  check(renderSpace({ ...base, data: { members: { data: [] } } }), "用户空间无治理摘要");
});

test("训练详情：四页签、缺失模型/数据集、无标签混淆矩阵均可渲染", () => {
  const job = { id: "j1", name: XSS, kind: "train", status: "succeeded", task_type: "llm_sft",
    model_version_id: "missing", dataset_version_id: "missing", config: { epochs: 2, lora_rank: 4 },
    snapshot: { task_type: "llm_sft" }, result: { accuracy: 0.9, validation_loss: 1.23456, training_samples: 10, validation_samples: 2,
      confusion_matrix: [[5, 1], [0, 4]] }, // labels 缺失：旧产物可能只有矩阵
    queue_reason: XSS, error: null, execution: { finished_at: "2026-11-27T00:00:00Z" }, artifact_sha256: LONG, artifact_bytes: 2048,
    output_model_version_id: "mv1", created_at: "2026-11-27T00:00:00Z" };
  const ctx = { ...base, data: { item: job, events: [{ type: "metric", payload: { epoch: 1, loss: 1.2, val_loss: 1.1 } }], options: { models: [], datasets: [] } } };
  for (const tab of ["overview", "metrics", "logs", "outputs"]) {
    ctx.params = new URLSearchParams(`tab=${tab}`);
    const html = check(renderTrainingDetail(ctx, metricChart), `训练详情 ${tab}`);
    assert.ok(html.includes("&lt;script&gt;"));
  }
  const failed = { ...job, status: "failed", error: XSS, result: {} };
  check(renderTrainingDetail({ ...ctx, params: new URLSearchParams(), data: { ...ctx.data, item: failed } }, metricChart), "训练详情失败态");
});

test("资源监控：未上报指标的设备与未探测的节点不使页面崩溃", () => {
  const node = { id: "n1", name: XSS, status: "在线", workspace_id: "wsp_1", last_seen_at: "2026-11-27T00:00:00Z",
    inventory: { hostname: "host", platform: "Linux", cpu_count: 4, memory_mb: 8192 }, // runtime 缺失：未完成探测
    devices: [{ id: "d1", name: "GPU-0", kind: "cuda", present: true, memory_mb: 8192, metrics: null, status: "空闲", purpose: "shared", hardware_id: LONG },
      { id: "d2", name: "CPU", kind: "cpu", present: false, reserved_execution_id: "e1", memory_mb: null, metrics: {}, status: "失联占用", purpose: "shared", hardware_id: "cpu:x" }] };
  const ctx = { ...base, path: "/monitor", data: { data: [node], summary: { nodes: { online: 1, total: 1 }, cpu: { total: 1, occupied: 0, disconnected_occupied: 0 }, cuda: { total: 1, occupied: 0, disconnected_occupied: 0 } }, pagination: { total: 1, page: 1, page_size: 20 } } };
  const html = check(renderCompute(ctx), "资源设备页");
  assert.ok(html.includes("&lt;script&gt;"));
  const detail = check(renderCompute({ ...ctx, data: { ...ctx.data, detail: node, history: null } }), "节点详情");
  assert.ok(detail.includes("未安装") && detail.includes("需升级"));
  check(renderCompute({ ...ctx, data: { data: [], pagination: { total: 0, page: 1, page_size: 20 } } }), "资源空列表");
  assert.ok(historyHtml(null).includes("暂无历史采样"));
  assert.ok(historyHtml({ points: [{ at: "2026-11-27T00:00:00Z", utilization: 50 }], sampling_seconds: 60 }).includes("<svg"));
});

test("评估对比与调用记录：空指标、缺失画像与错误样本均可渲染", () => {
  const compare = { task_type: "text_classification", dataset: { id: "d1", name: XSS, number: 2 },
    config: { epochs: 2 }, items: [
      { id: "j1", name: XSS, model_id: "m1", model_name: "模型A", model_version: "v1", created_at: "2026-11-27T00:00:00Z", metrics: {}, labels: null, confusion_matrix: null, errors_available: true },
      { id: "j2", name: "模型B", model_id: "m1", model_name: "模型B", model_version: "v2", created_at: "2026-11-27T00:00:00Z", metrics: { accuracy: 0.8 }, labels: ["正", "负"], confusion_matrix: [[8, 2], [1, 9]], errors_available: false }] };
  const html = check(renderResults({ ...base, path: "/evaluation/compare", data: compare }), "评估对比");
  assert.ok(html.includes("&lt;script&gt;") && html.includes("评估对比"));
  const errors = { job_id: "j1", supported: true, error_sample_count: 1, reported_count: 1, task_type: "image_classification", version_id: "v1",
    samples: [{ index: 0, actual: XSS, predicted: "负", source: { text: XSS } }] };
  check(renderResults({ ...base, path: "/evaluation/errors/j1", data: errors }), "错误样本图像任务");
  check(renderCallHistory({ ...base, data: { callStatistics: {}, callHistory: { data: [{ id: LONG, actor_name: XSS, status: "failed", created_at: null, completed_at: null, elapsed_ms: null }], pagination: { total: 1, page: 1, page_size: 20 } } } }), "调用记录");
  check(renderEvaluationReport({ ...base, data: { evaluationSummary: { job_id: "j1", per_class: [{ label: XSS, precision: 0.5, recall: null, f1: 0.5, support: 3 }] } } }), "评估报告");
  check(renderEvaluationReport({ ...base, data: {} }), "评估报告缺失");
});

test("智能辅助：日志原因缺失字段与预览缺失上限不泄露 undefined", () => {
  const list = { ...base, path: "/assistants", data: { data: [{ id: "r1", purpose: "logs", status: "succeeded", created_by: "u1", preview: { connection: { name: XSS } }, created_at: null }], pagination: { total: 1, page: 1, page_size: 20 } } };
  check(renderAssistant(list), "智能辅助列表");
  const detail = { ...base, path: "/assistants/r1", data: { id: "r1", purpose: "logs", status: "succeeded", created_by: "usr_1",
    preview: { text: XSS, connection: { name: "连", model: "m" } }, // max_tokens 缺失
    result: { summary: XSS, causes: [{ reason: XSS }] } } }; // evidence/steps 缺失
  const html = check(renderAssistant(detail), "智能辅助日志详情");
  assert.ok(html.includes("&lt;script&gt;") && !html.includes("undefined Token"));
});

test("在线标注：对抗样本文字、指令样本与空样本页均可渲染", () => {
  const ctx = { ...base, path: "/annotation/a1", data: { id: "a1", name: XSS, version_id: "v1", status: "open", counts: { approved: 0, total: 1 }, can_edit: true, can_review: true,
    dataset: { id: "d1", name: XSS, task_type: "text_classification" }, source_version: { number: 1 }, labels: ["正", "负"],
    samples: [{ index: 0, source: { text: XSS, label: "" } }], pagination: { page: 1, page_size: 20, total: 1 } } };
  const html = check(renderAnnotation(ctx), "在线标注");
  assert.ok(html.includes("&lt;script&gt;"));
  const sft = { ...ctx, data: { ...ctx.data, dataset: { id: "d1", name: "数据", task_type: "llm_sft" },
    samples: [{ index: 0, source: { instruction: XSS, input: "", output: XSS }, result: { edits: { input: XSS } } }] } };
  check(renderAnnotation(sft), "在线标注指令样本");
  check(renderAnnotation({ ...ctx, data: { ...ctx.data, samples: [] } }), "在线标注空样本");
});

test("资产目录与详情：无最新版本、格式缺失的版本均可渲染", () => {
  const models = [{ id: "m1", name: XSS, task_type: "text_classification", trainer_id: "text-classifier-v1", source_ref: LONG, category: "trained", latest_version: null, archived: false }];
  const html = check(renderAssetCatalog("models", { ...base, data: { data: models, pagination: { total: 1, page: 1, page_size: 20 } } }), "模型目录卡片");
  assert.ok(html.includes("&lt;script&gt;") && html.includes("未登记"));
  const datasets = [{ id: "d1", name: XSS, task_type: "text_classification", latest_version: { number: 1, sample_count: 0, format: null, status: "available", created_at: null }, created_at: "2026-11-27T00:00:00Z" }];
  check(renderAssetCatalog("datasets", { ...base, params: new URLSearchParams("view=list"), data: { data: datasets, pagination: { total: 1, page: 1, page_size: 20 } } }), "数据集目录列表");
  check(renderProjectCatalog({ ...base, data: { data: [{ id: "p1", name: XSS, job_count: 1, active_count: 0, latest_job: null, best_accuracy: null, created_at: null }], pagination: { total: 1, page: 1, page_size: 20 } } }), "项目目录");
  check(renderAssets("models", { ...base, data: { data: models } }), "模型管理列表");
  const detail = { item: { id: "d1", name: XSS, task_type: "text_classification" },
    versions: { data: [{ id: "v1", number: 1, filename: LONG, format: "csv", sample_count: 1, size_bytes: 10, status: "available" }] },
    preview: { total: 1, samples: [{ text: XSS, label: "" }] } };
  check(renderAssetDetail("datasets", { ...base, data: detail }), "数据集详情");
});

test("训练列表、向导、导入与数据处理：对抗名称与缺失选项均可渲染", () => {
  const list = check(renderWorkflow({ ...base, path: "/runs", data: { data: [{ id: "j1", name: XSS, status: "running", device_kind: "cuda", result: {}, created_at: null }], options: { models: [], datasets: [] }, projects: [], nodes: [] } }), "训练列表");
  assert.ok(list.includes("&lt;script&gt;"));
  const ctx = { ...base, workspace: { id: "w1" }, data: { options: { models: [{ id: "m1", name: XSS, version: "v1", task_type: "text_classification", trainer_id: "text-classifier-v1" }], datasets: [{ id: "d1", dataset_id: "data1", name: XSS, task_type: "text_classification", number: 1, sample_count: 20 }] }, projects: [], nodes: [] } };
  const draft = ensureDraft(ctx); draft.values.name = XSS;
  for (let step = 0; step < 4; step++) { draft.step = step; check(renderWizard(ctx), `训练向导第${step + 1}步`); }
  const dialog = workflowDialog({ kind: "job-new", item: { kind: "train" } }, ctx);
  assert.ok(dialog.fields.includes("&lt;script&gt;") && !dialog.fields.includes("<script>"));
  check(renderDatasetImport({ ...base, importDraft: { key: "new", workspaceId: "w1", name: XSS, task_type: "text_classification", file: null, preview: null } }), "数据集导入");
  const ops = { ...base, path: "/data-operations", data: { data: [{ id: "o1", name: XSS, kind: "augment", status: "review", dataset_name: XSS, version_number: 1, created_at: null, progress: { total: 0, done: 0 } }], pagination: { total: 1, page: 1, page_size: 20 } } };
  check(renderDataWorkflow(ops), "数据处理列表");
  const opDetail = { ...base, path: "/data-operations/o1", data: { item: { id: "o1", name: XSS, kind: "augment", status: "review", dataset_name: XSS, dataset_id: "d1", version_number: 1, version_id: "v1", task_type: "text_classification", options: { seed: 7 }, progress: { phase: "处理中", total: 10, done: 3 }, created_at: null, candidates: [{ partition: "train", sample_count: 8 }], error: null }, preview: null, candidate: 0 } };
  check(renderDataWorkflow(opDetail), "数据处理详情");
  check(renderProjectDetail({ ...base, data: { project: { id: "p1", name: XSS, description: XSS, created_at: null, job_count: 0 } } }), "项目详情");
});

test("管理端与弹窗：对抗名称、空统计与全部弹窗种类均可渲染", () => {
  const stats = { ...base, path: "/admin/stats", data: { counts: { users: 1, datasets: 0, models: 0, jobs: 1, active: 0, failed: 0 }, trend: [], states: {}, resources: { storage_bytes: 0, gpu_reserved_seconds: 0, confirmed_assistant_requests: 0, reported_assistant_tokens: null }, failure_stages: {}, workspaces: [{ id: "w1", name: XSS, jobs: 1 }] } };
  check(renderManagement(stats), "管理端统计面板");
  check(renderUsers({ ...base, data: { data: [{ id: "u2", account: XSS, display_name: XSS, is_admin: false, group_id: null, active: true }] } }), "用户管理");
  check(renderAudit({ ...base, data: { data: [{ id: "e1", action: XSS, actor_name: XSS, created_at: null }] } }), "操作记录");
  check(renderKeys({ ...base, data: { data: [{ id: "k1", name: XSS, job_id: "s1", status: "active", created_at: null, expires_at: "2027-01-01T00:00:00Z", last_called_at: null, recorded_calls: null }], services: [{ id: "s1", name: "服务" }] } }), "密钥管理");
  for (const kind of ["workspace-new", "model-new", "dataset-new", "user-new", "user-edit", "group-new", "group-edit", "member", "toggle-user", "examples", "password-own", "password-reset", "workspace-delete", "user-access", "settings-edit", "connection-edit", "gov-workspace-budget", "gov-review", "gov-archive", "gov-delete", "node-edit", "enroll-new", "assistant-annotation-new"]) {
    const item = { display_name: XSS, name: XSS, account: XSS, access: { actions: ["training.read"], quota: {} }, budget: { usage: { concurrent_jobs: 0, gpu_count: 0, storage_bytes: 0 } }, job: { name: XSS }, node: { name: XSS, last_seen_at: null, enabled: false, active_executions: [] }, execution: { id: "e1", finished_at: null } };
    check(renderDialog({ kind, item }, { ...base, groups: [], data: { settings: { platform_name: XSS, invitations_enabled: true, self_registration_enabled: false, global_concurrent_jobs: 8, max_upload_mib: 10, max_samples: 1000, default_group_id: null } }, assistantOptions: { policy: { enabled: false }, connections: [] } }), `弹窗 ${kind}`);
  }
  const budget = governanceDialog({ kind: "gov-workspace-budget", item: { id: "w1", budget: { gpu_count: null, concurrent_jobs: null, storage_gib: null, usage: { concurrent_jobs: 0, gpu_count: 0, storage_bytes: 0 } } } });
  assert.ok(budget && budget.fields.includes("GPU 数量"));
  const review = governanceDialog({ kind: "gov-review", item: { job: { name: XSS, revision: 1 }, node: { name: XSS, last_seen_at: null, enabled: true, active_executions: [] }, execution: { id: "e1", finished_at: null } } });
  assert.ok(review && review.fields.includes("&lt;script&gt;"));
});
