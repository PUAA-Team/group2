import { effectiveAccess, PERMISSIONS } from "../state.js?v=console-4";
import { badge, card, escapeHtml as e, icon, linkButton, pageHeader } from "../ui.js?v=console-4";
import { taskById } from "../data.js?v=console-4";

export function renderSpace(state, user) {
  const access = effectiveAccess(user, state);
  const ownedRuns = state.runs.filter(run => run.ownerId === user.id || (!run.ownerId && user.id === "user-lin"));
  const recent = state.audit.filter(item => item.actor === user.name).slice(0, 5);
  return `${pageHeader("用户空间", "", `<span class="chip">${e(user.role)}</span>`)}
    <div class="grid-3">${card(`<div class="metric-label">用户组</div><div class="metric-value compact">${e(access.group?.name || "未分组")}</div>`, "metric-card")}${card(`<div class="metric-label">可用 GPU 数</div><div class="metric-value blue">${access.quota.gpu}</div>`, "metric-card")}${card(`<div class="metric-label">并发任务上限</div><div class="metric-value">${access.quota.jobs}</div>`, "metric-card")}</div>
    <div class="section-heading"><h2>我的权限</h2></div>${card(`<div class="permission-grid">${PERMISSIONS.map(([key, label]) => `<div class="permission-line"><span>${e(label)}</span>${access.permissions.has(key) ? badge("启用") : badge("停用")}</div>`).join("")}</div>`)}
    <div class="section-heading"><h2>最近任务</h2>${linkButton("全部任务", "#/runs", "secondary")}</div>${card(ownedRuns.length ? `<div class="table-scroll"><table class="table"><thead><tr><th>任务</th><th>类型</th><th>状态</th><th>指标</th></tr></thead><tbody>${ownedRuns.slice(0, 5).map(run => `<tr><td><a class="row-link" href="#/runs/${e(run.id)}">${e(run.name)}</a></td><td>${e(taskById(run.taskId)?.name || "—")}</td><td>${badge(run.status)}</td><td>${e(run.metric)} ${e(run.score)}</td></tr>`).join("")}</tbody></table></div>` : `<div class="empty-state"><h3>暂无任务</h3>${linkButton("新建训练", "#/train/new", "primary")}</div>`)}
    <div class="section-heading"><h2>我的操作</h2></div>${card(recent.length ? recent.map(item => `<div class="callout-row"><span class="label">${e(item.time)}</span><span class="value">${e(item.action)} · ${e(item.target)}</span></div>`).join("") : `<span class="subtle">暂无操作记录</span>`)}`;
}

export function renderMonitor(state) {
  const busy = state.resources.filter(item => item.status === "使用中").length;
  const active = state.runs.filter(item => ["排队中", "运行中"].includes(item.status)).length;
  return `${pageHeader("资源监控", "计算资源、任务队列与使用情况")}
    <div class="grid-3">${card(`<div class="metric-label">GPU 总数</div><div class="metric-value">${state.resources.length}</div>`, "metric-card")}${card(`<div class="metric-label">使用中</div><div class="metric-value blue">${busy}</div>`, "metric-card")}${card(`<div class="metric-label">活跃任务</div><div class="metric-value">${active}</div>`, "metric-card")}</div>
    <div class="section-heading"><h2>设备状态</h2></div><div class="grid-3">${state.resources.map(item => card(`<div class="card-header"><h2>${e(item.name)}</h2>${badge(item.status)}</div><div class="project-meta"><span class="chip">${e(item.model)}</span><span class="chip">${e(item.memory)}</span></div><div class="resource-meter"><div class="progress"><span style="width:${Number(item.util)}%"></span></div><span class="subtle">${Number(item.util)}%</span></div><div class="callout-row"><span class="label">当前任务</span><span class="value">${e(item.owner)}</span></div>`, "resource-card")).join("")}</div>
    <div class="section-heading"><h2>任务队列</h2></div>${card(`<div class="table-scroll"><table class="table"><thead><tr><th>任务</th><th>状态</th><th>资源</th><th>开始时间</th></tr></thead><tbody>${state.runs.filter(item => ["排队中", "运行中"].includes(item.status)).map(run => `<tr><td><a class="row-link" href="#/runs/${e(run.id)}">${e(run.name)}</a></td><td>${badge(run.status)}</td><td>${e(run.gpu)}</td><td>${e(run.started)}</td></tr>`).join("")}</tbody></table></div>`)}`;
}
