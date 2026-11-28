// Stage 22-8 设置、密钥、审计与治理页面视觉收尾 + 全站空态与窄屏复核：
// 系统设置用量限制与连接统计条、密钥统计条、治理预算统计条；
// 各列表空态按页面区分，带筛选时显示“没有符合筛选条件…”；
// 表格横向滚动容器与三列统计条 700px 以下两列。
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { renderManagement } from "../live/administration.js";
import { renderKeys } from "../live/key-management.js";
import { renderUsers, renderAudit } from "../live/pages/admin.js";
import { renderHome, renderSpace } from "../live/pages/overview.js";
import { renderAssistant } from "../live/assistant.js";
import { renderCompute } from "../live/compute.js";
import { renderExtraJobs } from "../live/admin-workflows.js";
import { renderCallHistory } from "../live/results.js";
import { renderProjectDetail } from "../live/projects.js";
import { parameterTemplateDialog } from "../live/parameter-templates.js";
import { renderProjectCatalog, renderAssetCatalog } from "../live/catalog.js";

const workspace = { id: "w1", name: "研发组", owner_id: "u1" };
const base = { workspace, workspaces: [workspace], params: new URLSearchParams(), page: 1, q: "",
  session: { user: { id: "u1", display_name: "管理", account: "admin", is_admin: true },
    access: { actions: ["services.write", "members.manage", "training.read", "training.write", "resources.manage", "assistants.use", "datasets.read", "models.read"], quota: {}, role: "admin" } },
  access: { actions: ["services.write", "members.manage", "training.read", "training.write", "resources.manage", "assistants.use", "datasets.read", "models.read"], quota: {}, role: "admin" },
  templates: [], data: {} };
const pagination = { total: 0, page: 1, page_size: 20 };

function check(html, label) {
  assert.equal(typeof html, "string", `${label} 未返回字符串`);
  assert.ok(!html.includes("undefined"), `${label} 泄露了 undefined`);
  assert.ok(!html.includes("NaN"), `${label} 泄露了 NaN`);
  return html;
}
const withParams = (ctx, entries) => ({ ...ctx, params: new URLSearchParams(entries) });

test("系统设置：用量限制与大模型连接改为数字统计条，连接名省略悬停查看", () => {
  const settings = { platform_name: "模训平台", invitations_enabled: true, self_registration_enabled: false,
    default_group_id: "g1", global_concurrent_jobs: 4, max_upload_mib: 10, max_samples: 5000 };
  const connections = [
    { id: "c1", name: "主连接", endpoint: "https://api.example.com/v1", model: "qwen-max", capabilities: ["text"], credential_set: true, active: true, health: { status: "available" } },
    { id: "c2", name: "超长名称的备用连接".repeat(8), endpoint: "https://backup.example.com/v1", model: "qwen-plus", capabilities: ["text", "vision"], credential_set: false, active: true, health: { status: "failed" } },
    { id: "c3", name: "已停用", endpoint: "https://old.example.com/v1", model: "qwen-turbo", capabilities: ["text"], credential_set: true, active: false, health: { status: "available" } },
  ];
  const ctx = { ...base, path: "/admin/settings", groups: [{ id: "g1", name: "研发组" }], data: { settings, connections } };
  const html = check(renderManagement(ctx), "系统设置");
  assert.ok(html.includes("用量限制"), "应有用量限制统计条标题");
  assert.ok(html.includes("全局并发上限") && html.includes("<strong>4</strong>"), "统计条应有全局并发上限");
  assert.ok(html.includes("单文件上限") && html.includes("<strong>10 MiB</strong>"), "统计条应有单文件上限");
  assert.ok(html.includes("样本数上限") && html.includes("<strong>5000</strong>"), "统计条应有样本数上限");
  assert.ok(html.includes("连接总数") && html.includes("<strong>3</strong>"), "连接统计条应有总数");
  assert.ok(html.includes("连接成功") && html.includes("连接失败"), "连接统计条应区分成功与失败");
  assert.ok(html.includes(`class="live-source" title="${"超长名称的备用连接".repeat(8)}"`), "超长连接名应省略悬停查看");
  assert.ok(html.includes("研发组"), "默认注册用户组应显示组名");
  const empty = check(renderManagement({ ...ctx, data: { settings, connections: [] } }), "系统设置无连接");
  assert.ok(empty.includes("暂无大模型连接"), "无连接时应显示区分空态");
  assert.ok(empty.includes("<strong>0</strong>"), "无连接时统计条应为 0");
});

test("统计面板：作业状态为空时给提示，工作空间表空态区分", () => {
  const ctx = { ...base, path: "/admin/stats", data: { counts: { users: 2, datasets: 1, models: 1, jobs: 0, active: 0, failed: 0 },
    trend: [{ date: "2026-11-27", train: 0, evaluate: 0, service: 0 }], states: {}, resources: null, workspaces: [] } };
  const html = check(renderManagement(ctx), "统计面板空态");
  assert.ok(html.includes("暂无作业状态统计"), "无作业状态时应提示");
  assert.ok(html.includes("暂无工作空间"), "无工作空间时应显示区分空态");
  const withStates = check(renderManagement({ ...ctx, data: { ...ctx.data, states: { succeeded: 2 }, workspaces: [{ name: "研发组", jobs: 3 }] } }), "统计面板有数据");
  assert.ok(!withStates.includes("暂无作业状态统计") && !withStates.includes("暂无工作空间"), "有数据时不应显示空态");
  assert.ok(withStates.includes("已完成") && withStates.includes(">2<"), "作业状态应显示中文标签与数量");
});

test("审计日志：空态与筛选空态区分，目标与请求编号悬停查看", () => {
  const row = { created_at: "2026-11-27T08:00:00Z", action: "workspaces.create", actor_name: "管理", workspace_name: "研发组",
    target_id: "w".repeat(60), result: "success", error_code: null, request_id: "req-abc123" };
  const ctx = { ...base, path: "/admin/audit", data: { data: [], pagination } };
  assert.ok(check(renderManagement(ctx), "审计空").includes("暂无操作记录"), "无记录时应显示区分空态");
  assert.ok(check(renderManagement(withParams(ctx, [["status", "failure"]])), "审计筛选空").includes("没有符合筛选条件的操作记录"), "带筛选无结果时应提示");
  const withRow = check(renderManagement({ ...ctx, data: { data: [row], pagination: { ...pagination, total: 1 } } }), "审计有记录");
  assert.ok(withRow.includes("创建空间"), "操作应显示中文标签");
  assert.ok(withRow.includes(`title="${"w".repeat(60)}"`), "超长目标应悬停查看全文");
  assert.ok(withRow.includes("req-abc123"), "请求编号应展示");
  assert.ok(check(renderAudit({ ...base, data: { data: [], pagination } }), "审计旧入口空").includes("暂无操作记录"), "旧审计入口空态也应区分");
});

test("API 密钥：统计条按状态计数，标识与未关联服务省略悬停查看", () => {
  const keys = [
    { id: "key-00000001", name: "线上服务", masked_identifier: "mt-••••0001", job_id: "job1", revoked_at: null, expires_at: "2999-01-01T00:00:00Z", recorded_calls: 5, last_called_at: "2026-11-27T00:00:00Z" },
    { id: "key-00000002", name: "已过期", masked_identifier: "mt-••••0002", job_id: "job-missing", revoked_at: null, expires_at: "2020-01-01T00:00:00Z", recorded_calls: 0, last_called_at: null },
    { id: "key-00000003", name: "已撤销", masked_identifier: "mt-••••0003", job_id: "job1", revoked_at: "2026-11-01T00:00:00Z", expires_at: "2999-01-01T00:00:00Z", recorded_calls: 2, last_called_at: null },
  ];
  const ctx = { ...base, path: "/api-keys", data: { data: keys, services: [{ id: "job1", name: "服务A" }] } };
  const html = check(renderKeys(ctx), "密钥列表");
  assert.ok(html.includes("密钥总数") && html.includes("<strong>3</strong>"), "统计条应有密钥总数");
  assert.ok(html.includes("启用中") && html.includes("已过期") && html.includes("已撤销"), "统计条应按状态分组");
  assert.ok(html.includes("服务A"), "已关联服务应显示名称");
  assert.ok(html.includes(`class="live-source" title="job-missing"`), "未关联服务应显示服务 ID 且可悬停查看");
  assert.ok(html.includes("已过期") && html.includes("停用"), "过期与撤销应打不同状态徽标");
  assert.ok(check(renderKeys({ ...ctx, data: { data: [], services: [] } }), "密钥空").includes("暂无 API 密钥"), "无密钥时应显示区分空态");
  assert.ok(check(renderKeys(withParams({ ...ctx, data: { data: [], services: [] } }, [["key_status", "expired"]])), "密钥筛选空").includes("没有符合筛选条件的密钥"), "带筛选无结果时应提示");
});

test("用户管理：用户与用户组空态区分，带筛选时提示", () => {
  const ctx = { ...base, path: "/admin/users", groups: [], data: { data: [], pagination } };
  assert.ok(check(renderUsers(ctx), "用户空").includes("暂无用户"), "无用户时应显示区分空态");
  assert.ok(check(renderUsers({ ...ctx, q: "x" }), "用户筛选空").includes("没有符合筛选条件的用户"), "带搜索无结果时应提示");
  const groups = check(renderUsers({ ...ctx, tab: "groups" }), "用户组空");
  assert.ok(groups.includes("暂无用户组"), "无用户组时应显示区分空态");
  assert.ok(check(renderUsers({ ...ctx, tab: "groups", q: "x" }), "用户组筛选空").includes("没有符合筛选条件的用户组"), "带搜索无用户组时应提示");
});

test("工作台最近训练与治理：预算改为数字统计条，成员账单省略悬停查看", () => {
  const home = check(renderHome({ ...base, path: "/home", data: { counts: { projects: 1, active: 0, queued: 0, succeeded: 0, datasets: 1 }, recent_jobs: [], activity: [], pending_items: [] } }), "工作台");
  assert.ok(home.includes("暂无训练任务"), "无最近训练时应显示区分空态");
  const gov = { budget: { usage: { concurrent_jobs: 2, gpu_count: 1, storage_bytes: 10485760 }, concurrent_jobs: 4, gpu_count: 2, storage_gib: 10 },
    members: [{ display_name: "张".repeat(30), account: "very-long-account-name@example.com", role: "editor", quota: {}, storage_bytes: 0, jobs: { total: 1, active: 0, succeeded: 1 }, gpu_seconds: 3600, assistant_tokens: 100 }] };
  const space = check(renderSpace({ ...base, path: "/space", data: { members: { data: [], pagination }, invites: [], joinRequests: [], governanceSummary: gov } }), "用户空间治理");
  assert.ok(space.includes("空间预算与成员账单"), "应有治理区标题");
  assert.ok(space.includes("并发预算") && space.includes("<strong>2 / 4</strong>"), "预算统计条应显示并发已用/上限");
  assert.ok(space.includes("GPU 预算") && space.includes("<strong>1 / 2</strong>"), "预算统计条应显示 GPU 已用/上限");
  assert.ok(space.includes("存储预算") && space.includes("10.00 MiB / 10 GiB"), "预算统计条应显示存储已用/上限");
  assert.ok(space.includes(`title="${"张".repeat(30)} (very-long-account-name@example.com)"`), "超长成员名与账号应省略悬停查看");
  assert.ok(space.includes("暂无空间成员"), "无空间成员时应显示区分空态");
  const emptyGov = check(renderSpace({ ...base, path: "/space", data: { members: { data: [], pagination }, invites: [], joinRequests: [], governanceSummary: { ...gov, members: [] } } }), "用户空间治理空账单");
  assert.ok(emptyGov.includes("暂无成员账单"), "无成员账单时应显示区分空态");
});

test("其余列表空态：智能辅助、计算节点、作业管理扩展视图、调用记录、项目实验、模板、项目目录", () => {
  const assistantCtx = { ...base, path: "/assistants", data: { data: [], pagination } };
  assert.ok(check(renderAssistant(assistantCtx), "智能辅助空").includes("暂无智能辅助请求"), "无智能辅助请求时应显示区分空态");
  assert.ok(check(renderAssistant(withParams(assistantCtx, [["status", "failed"]])), "智能辅助筛选空").includes("没有符合筛选条件的智能辅助请求"), "带筛选无结果时应提示");
  const computeCtx = { ...base, path: "/monitor", data: { data: [], summary: null }, params: new URLSearchParams([["tab", "nodes"]]) };
  assert.ok(check(renderCompute(computeCtx), "计算节点空").includes("暂无计算节点"), "无计算节点时应显示区分空态");
  assert.ok(check(renderCompute({ ...computeCtx, q: "x" }), "计算节点筛选空").includes("没有符合筛选条件的计算节点"), "带搜索无结果时应提示");
  const extraCtx = { ...base, path: "/admin/jobs", params: new URLSearchParams([["job_view", "operations"]]), data: { data: [], pagination } };
  assert.ok(check(renderExtraJobs(extraCtx, ""), "数据处理作业空").includes("暂无数据处理任务"), "无数据处理任务时应显示区分空态");
  assert.ok(check(renderExtraJobs({ ...extraCtx, params: new URLSearchParams([["job_view", "assistants"]]) }, ""), "智能请求作业空").includes("暂无智能请求"), "无智能请求时应显示区分空态");
  assert.ok(check(renderExtraJobs({ ...extraCtx, q: "x" }, ""), "作业筛选空").includes("没有符合筛选条件的作业"), "带搜索无结果时应提示");
  const historyCtx = { ...base, data: { callStatistics: { total: 0, succeeded: 0, failed: 0, pending: 0, measured_calls: 0, mean_ms: null }, callHistory: { data: [], pagination } } };
  assert.ok(check(renderCallHistory(historyCtx), "调用记录空").includes("暂无调用记录"), "无调用记录时应显示区分空态");
  assert.ok(check(renderCallHistory(withParams(historyCtx, [["call_status", "failed"]])), "调用记录筛选空").includes("没有符合筛选条件的调用记录"), "带筛选无结果时应提示");
  const project = { id: "p1", name: "项目A", archived: false, description: "", job_count: 0, active_count: 0, best_accuracy: null, created_at: "2026-11-27T00:00:00Z", recent_jobs: [] };
  assert.ok(check(renderProjectDetail({ ...base, data: { project } }), "项目实验空").includes("暂无训练任务"), "项目无实验时应显示区分空态");
  assert.ok(parameterTemplateDialog({ kind: "parameter-template-list", item: { rows: [] } }).fields.includes("暂无模板"), "无参数模板时应显示区分空态");
  const catalogCtx = { ...base, path: "/projects", data: { data: [], pagination } };
  assert.ok(check(renderProjectCatalog(catalogCtx), "训练项目空").includes("暂无训练项目"), "无训练项目时应显示区分空态");
  assert.ok(check(renderProjectCatalog({ ...catalogCtx, q: "x" }), "训练项目筛选空").includes("没有符合筛选条件的训练项目"), "带搜索无结果时应提示");
  const assetCtx = { ...base, path: "/datasets", data: { data: [], pagination } };
  assert.ok(check(renderAssetCatalog("datasets", assetCtx), "数据集空").includes("暂无数据集"), "无数据集时应显示区分空态");
  assert.ok(check(renderAssetCatalog("datasets", { ...assetCtx, q: "x" }), "数据集筛选空").includes("没有符合筛选条件的数据集"), "带搜索无结果时应提示");
});

test("窄屏复核：表格容器可横向滚动，三列统计条 700px 以下改两列", () => {
  const liveCss = readFileSync(join(dirname(fileURLToPath(import.meta.url)), "..", "live", "live.css"), "utf8");
  assert.ok(liveCss.includes(".table-scroll{overflow-x:auto}"), "表格滚动容器应有横向滚动规则，否则窄屏下多列表格会撑出视口");
  const consoleCss = readFileSync(join(dirname(fileURLToPath(import.meta.url)), "..", "live", "console.css"), "utf8");
  assert.ok(consoleCss.includes(".console-summary-three{grid-template-columns:repeat(2,minmax(0,1fr))"), "三列统计条在 700px 以下应改两列，不再三列挤压");
  assert.ok(consoleCss.includes(".console-summary-three strong{font-size:21px}"), "三列统计条窄屏数字应缩小到 21px");
});
