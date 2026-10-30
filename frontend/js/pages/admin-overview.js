import { TASKS, modelById, taskById } from "../data.js?v=console-4";
import { badge, card, escapeHtml as e, lineChart, pageHeader } from "../ui.js?v=console-4";

export function renderStats(state) {
  const completed = state.runs.filter(item => item.status === "已完成").length;
  const active = state.runs.filter(item => ["运行中", "排队中"].includes(item.status)).length;
  return `${pageHeader("统计面板")}<div class="grid-4">${[["用户", state.users.length], ["数据集", state.datasets.length], ["活跃作业", active], ["已完成训练", completed]].map(([label, value]) => card(`<div class="metric-label">${label}</div><div class="metric-value">${value}</div>`, "metric-card")).join("")}</div><div class="grid-2" style="margin-top:16px">${card(`<div class="card-header"><h2>作业趋势</h2></div>${lineChart([2,3,2,4,4,5,6,6,7,8],["起始","最近 7 天","当前"],"#315e72")}`)}${card(`<div class="card-header"><h2>任务分布</h2></div>${["图像", "文本", "表格", "大语言模型"].map(group => `<div class="callout-row"><span class="label">${group}</span><span class="value">${state.runs.filter(run => taskById(run.taskId)?.group === group).length} 个作业</span></div>`).join("")}`)}</div>`;
}

export function renderAdminData(state) {
  const rows = state.datasets.map(item => `<tr><td><a class="row-link" href="#/datasets/${e(item.id)}">${e(item.name)}</a></td><td>${e(item.type)}</td><td>${e(taskById(item.taskId)?.name || "—")}</td><td>${item.count}</td><td>v${item.version}</td><td>${badge(item.status)}</td><td>${e(item.updated)}</td></tr>`).join("");
  return `${pageHeader("数据管理", "全平台数据资产与版本")}${card(`<div class="grid-3 compact-metrics"><div><span>数据集</span><strong>${state.datasets.length}</strong></div><div><span>可训练</span><strong>${state.datasets.filter(item => item.status === "可训练").length}</strong></div><div><span>待处理</span><strong>${state.datasets.filter(item => item.status === "待处理").length}</strong></div></div>`)}<div class="section-heading"><h2>数据资产</h2></div>${card(`<div class="table-scroll"><table class="table"><thead><tr><th>名称</th><th>类别</th><th>任务</th><th>样本</th><th>版本</th><th>状态</th><th>更新</th></tr></thead><tbody>${rows}</tbody></table></div>`)}`;
}

export function renderAdminModels(state) {
  const completed = state.runs.filter(item => item.status === "已完成");
  return `${pageHeader("模型管理", "模型目录、训练产物与发布来源")}<div class="grid-3">${card(`<div class="metric-label">预置模型</div><div class="metric-value">${TASKS.flatMap(item => item.models).filter(item => item.kind === "预置模型").length}</div>`, "metric-card")}${card(`<div class="metric-label">网络结构</div><div class="metric-value">${TASKS.flatMap(item => item.models).filter(item => item.kind === "网络训练").length}</div>`, "metric-card")}${card(`<div class="metric-label">训练产物</div><div class="metric-value">${completed.length}</div>`, "metric-card")}</div><div class="section-heading"><h2>模型产物</h2></div>${card(`<div class="table-scroll"><table class="table"><thead><tr><th>任务</th><th>模型</th><th>类型</th><th>评估指标</th><th>来源</th></tr></thead><tbody>${completed.map(run => `<tr><td><a class="row-link" href="#/runs/${e(run.id)}?tab=outputs">${e(run.name)}</a></td><td>${e(modelById(run.modelId)?.name || "—")}</td><td>${e(taskById(run.taskId)?.name || "—")}</td><td>${e(run.metric)} ${e(run.score)}</td><td>${e(run.started)}</td></tr>`).join("")}</tbody></table></div>`)}`;
}

export function renderAdminJobs(state) {
  const rows = state.runs.map(run => `<tr><td><a class="row-link" href="#/runs/${e(run.id)}">${e(run.name)}</a></td><td>${e(taskById(run.taskId)?.name || "—")}</td><td>${badge(run.status)}</td><td>${e(run.gpu)}</td><td>${e(run.duration)}</td><td>${e(run.started)}</td></tr>`).join("");
  return `${pageHeader("作业管理", "训练队列、运行状态与资源占用")}${card(`<div class="grid-3 compact-metrics"><div><span>全部作业</span><strong>${state.runs.length}</strong></div><div><span>运行中</span><strong>${state.runs.filter(item => item.status === "运行中").length}</strong></div><div><span>失败</span><strong>${state.runs.filter(item => item.status === "失败").length}</strong></div></div>`)}<div class="section-heading"><h2>训练作业</h2></div>${card(`<div class="table-scroll"><table class="table"><thead><tr><th>作业</th><th>任务类型</th><th>状态</th><th>资源</th><th>时长</th><th>开始时间</th></tr></thead><tbody>${rows}</tbody></table></div>`)}`;
}

export function renderSettings(state) {
  const settings = state.settings;
  return `${pageHeader("系统设置", "", '<button class="btn btn-primary" data-action="open-modal" data-modal="settings">修改设置</button>')}${card(`<div class="card-header"><h2>用户与任务策略</h2></div><dl class="info-list"><div><dt>自主注册</dt><dd>${settings.registration ? "允许" : "关闭"}</dd></div><div><dt>注册默认用户组</dt><dd>${e(state.groups.find(group => group.id === settings.defaultGroupId)?.name || "—")}</dd></div><div><dt>全局并发任务上限</dt><dd>${e(settings.jobLimit)}</dd></div><div><dt>默认存储配额</dt><dd>${e(settings.storageLimit)} GB</dd></div></dl>`)}`;
}
