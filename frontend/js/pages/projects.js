import { modelById, taskById } from "../data.js?v=console-4";
import { badge, card, emptyState, escapeHtml as e, icon, linkButton, pageHeader } from "../ui.js?v=console-4";

export function renderProjectList(state, ui) {
  const search = (ui.search || "").toLowerCase();
  const projects = state.projects.filter(project => !search || `${project.name} ${project.description} ${taskById(project.taskId)?.name}`.toLowerCase().includes(search));
  const cards = projects.map(project => {
    const runs = state.runs.filter(run => run.projectId === project.id);
    const completed = runs.filter(run => run.status === "已完成").length;
    return card(`<div class="catalog-top"><span class="type-mark ${project.taskId.startsWith("image") || project.taskId.includes("detection") || project.taskId.includes("segmentation") ? "image" : project.taskId.startsWith("text") || project.taskId === "named-entity" ? "text" : project.taskId === "llm-instruction" ? "llm" : "tabular"}">${e(taskById(project.taskId)?.group?.slice(0, 1) || "项")}</span><span class="subtle">更新 ${e(project.updated)}</span></div><h3><a class="entity-link" href="#/projects/${e(project.id)}">${e(project.name)}</a></h3><div class="project-meta"><span class="chip">${e(taskById(project.taskId)?.name || "—")}</span><span class="chip">${runs.length} 次训练</span><span class="chip">${completed} 次完成</span></div><div class="project-foot"><a class="card-link" href="#/projects/${e(project.id)}" aria-label="打开${e(project.name)}">进入项目 ${icon("arrow", 13)}</a></div>`, "project-card");
  }).join("");
  return `${pageHeader("训练项目", "", linkButton("新建训练", "#/train/new", "primary", "plus"))}
    <div class="toolbar"><div class="search-field">${icon("search", 16)}<input class="input" type="search" placeholder="搜索项目" value="${e(ui.search || "")}" data-filter="search" aria-label="搜索项目" /></div><span class="subtle">共 ${projects.length} 个项目</span></div>${projects.length ? `<div class="catalog-grid">${cards}</div>` : emptyState("没有找到项目", "可新建训练并同时建立项目。", linkButton("新建训练", "#/train/new", "primary"))}`;
}

export function renderProjectDetail(state, id) {
  const project = state.projects.find(item => item.id === id);
  if (!project) return emptyState("项目不存在", "返回列表重新选择。", linkButton("返回项目", "#/projects"));
  const task = taskById(project.taskId);
  const runs = state.runs.filter(run => run.projectId === project.id);
  const completed = runs.filter(run => run.status === "已完成");
  const best = completed.length ? completed.reduce((winner, current) => Number(current.score) > Number(winner.score) ? current : winner) : null;
  const rows = runs.map(run => `<tr><td><a class="row-link" href="#/runs/${e(run.id)}">${e(run.name)}</a></td><td>${e(modelById(run.modelId)?.name || "—")}</td><td>${badge(run.status)}</td><td>${e(run.score)}</td><td>${e(run.duration)}</td><td>${e(run.started)}</td></tr>`).join("");
  const compare = completed.length > 1 ? `<div class="table-scroll"><table class="table compare-table"><thead><tr><th>训练任务</th><th>模型</th><th>训练轮次</th><th>批大小</th><th>学习率</th><th>${e(task?.metric || "指标")}</th></tr></thead><tbody>${completed.map(run => `<tr><td><a class="row-link" href="#/runs/${e(run.id)}">${e(run.name)}</a></td><td>${e(modelById(run.modelId)?.name || "—")}</td><td>${e(run.epochs)}</td><td>${e(run.batch)}</td><td>${e(run.lr)}</td><td><strong>${e(run.score)}</strong></td></tr>`).join("")}</tbody></table></div>` : emptyState("等待更多训练结果", "至少两次任务完成后可在这里比较参数和指标。");
  return `<div class="breadcrumb"><a href="#/projects">训练项目</a>${icon("chevron", 13)}<span>${e(project.name)}</span></div>
    ${pageHeader(project.name, project.description || task?.name || "", linkButton("在此项目新建训练", `#/train/new?project=${e(project.id)}`, "primary", "plus"))}
    <div class="grid-3">${card(`<div class="metric-label">任务类型</div><div class="metric-value" style="font-size:19px">${e(task?.name || "—")}</div>`, "metric-card")}${card(`<div class="metric-label">训练次数</div><div class="metric-value">${runs.length}</div>`, "metric-card")}${card(`<div class="metric-label">最佳${e(task?.metric || "指标")}</div><div class="metric-value green">${e(best?.score || "—")}</div>`, "metric-card")}</div>
    <div class="section-heading"><h2>训练任务</h2><a class="card-link" href="#/runs">全部任务</a></div>${card(runs.length ? `<div class="table-scroll"><table class="table"><thead><tr><th>任务</th><th>模型</th><th>状态</th><th>${e(task?.metric || "指标")}</th><th>耗时</th><th>开始时间</th></tr></thead><tbody>${rows}</tbody></table></div>` : emptyState("还没有训练任务", "新建一次训练开始记录结果。"))}
    <div class="section-heading"><h2>训练结果对比</h2></div>${card(compare)}`;
}
