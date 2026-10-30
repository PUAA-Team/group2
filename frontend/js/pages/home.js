import { taskById } from "../data.js?v=console-4";
import { badge, card, escapeHtml as e, icon, linkButton, pageHeader } from "../ui.js?v=console-4";

export function renderHome(state, user, permissions) {
  const active = state.runs.filter(run => ["排队中", "运行中"].includes(run.status)).length;
  const completed = state.runs.filter(run => run.status === "已完成").length;
  const available = state.datasets.filter(dataset => dataset.status === "可训练").length;
  const metrics = [
    ["训练项目", state.projects.length],
    ["运行中任务", active, "blue"],
    ["已完成任务", completed, "green"],
    ["可用数据集", available, "amber"]
  ];
  const metricCards = metrics.map(([label, value, color]) => card(`<div class="metric-label">${label}</div><div class="metric-value ${color || ""}">${value}</div>`, "metric-card")).join("");
  const runRows = state.runs.slice(0, 5).map(run => `<tr><td><a class="row-link" href="#/runs/${e(run.id)}">${e(run.name)}</a></td><td>${e(taskById(run.taskId)?.name || "—")}</td><td>${badge(run.status)}</td><td>${e(run.metric)} <strong>${e(run.score)}</strong></td><td class="nowrap">${e(run.started)}</td></tr>`).join("");
  const quickLinks = [
    ["新建训练", "#/train/new", "training", "train.submit"], ["导入数据集", "#/datasets/new", "data", "datasets.write"], ["查看模型仓库", "#/models", "models", "models.manage"]
  ].filter(([, , , permission]) => !permissions || permissions.has(permission)).map(([label, href, symbol]) => `<a class="quick-link" href="${href}"><span class="quick-icon">${icon(symbol, 17)}</span>${label}${icon("chevron", 15)}</a>`).join("");
  const activity = state.audit.slice(0, 4).map(item => `<div class="activity-item"><span class="activity-dot"></span><div><strong>${e(item.action)} · ${e(item.target)}</strong></div><time class="activity-time">${e(item.time)}</time></div>`).join("");
  return `${pageHeader("工作台", "训练、数据和模型的当前状态", !permissions || permissions.has("train.submit") ? linkButton("新建训练", "#/train/new", "primary", "plus") : "")}
    <div class="grid-4">${metricCards}</div>
    <div class="section-heading"><h2>最近训练</h2><a class="card-link" href="#/runs">查看全部</a></div>
    ${card(`<div class="table-scroll"><table class="table"><thead><tr><th>任务</th><th>任务类型</th><th>状态</th><th>主要指标</th><th>开始时间</th></tr></thead><tbody>${runRows}</tbody></table></div>`)}
    <div class="section-heading"><h2>继续操作</h2></div>
    <div class="overview-grid"><div class="overview-quick">${quickLinks || `<a class="quick-link" href="#/space">查看我的空间${icon("chevron", 15)}</a>`}</div>${card(`<div class="card-header"><h2>近期操作</h2><a class="card-link" href="${user?.role === "管理员" ? "#/admin/audit" : "#/space"}">全部记录</a></div><div class="activity-list">${activity}</div>`)}</div>`;
}
