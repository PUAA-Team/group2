import { TASKS, modelById, taskById } from "../data.js?v=console-4";
import { card, emptyState, escapeHtml as e, icon, linkButton, pageHeader } from "../ui.js?v=console-4";

export function renderModelList(state, ui) {
  const tab = ui.modelTab || "prebuilt";
  const group = ui.modelGroup || "全部类型";
  const search = (ui.search || "").trim().toLowerCase();
  const tabs = [["prebuilt", "预置模型"], ["network", "网络训练"], ["my", "我的模型"]];
  let contents;
  if (tab === "my") {
    const runs = state.runs.filter(run => run.status === "已完成" && (!search || `${run.name} ${taskById(run.taskId)?.name}`.toLowerCase().includes(search)));
    contents = runs.length ? `<div class="catalog-grid">${runs.map(run => {
      const project = state.projects.find(item => item.id === run.projectId);
      return card(`<div class="catalog-top"><span class="type-mark image">模</span><span class="chip">v1</span></div><h3><a class="entity-link" href="#/runs/${e(run.id)}?tab=outputs">${e(project?.name || run.name)}</a></h3><div class="project-meta"><span class="chip">${e(taskById(run.taskId)?.name || "—")}</span><span class="chip">${e(run.metric)} ${e(run.score)}</span></div><div class="project-foot"><span>${e(modelById(run.modelId)?.name || "—")}</span><a class="card-link" href="#/runs/${e(run.id)}?tab=outputs">查看产物</a></div>`, "catalog-card model-card");
    }).join("")}</div>` : emptyState("还没有模型产物", "训练完成后，模型版本会在这里出现。", linkButton("新建训练", "#/train/new", "primary"));
  } else {
    const targetKind = tab === "prebuilt" ? "预置模型" : "网络训练";
    const models = TASKS.flatMap(task => task.models.filter(model => model.kind === targetKind).map(model => ({ ...model, task }))).filter(item => (group === "全部类型" || item.task.group === group) && (!search || `${item.name} ${item.task.name}`.toLowerCase().includes(search)));
    contents = models.length ? `<div class="catalog-grid">${models.map(item => card(`<div class="catalog-top"><span class="type-mark ${item.task.group === "图像" ? "image" : item.task.group === "文本" ? "text" : item.task.group === "大语言模型" ? "llm" : "tabular"}">${e(item.task.group.slice(0, 1))}</span><span class="chip">${e(item.kind)}</span></div><h3><a class="entity-link" href="#/models/${e(item.id)}">${e(item.name)}</a></h3><div class="project-meta"><span class="chip">${e(item.task.name)}</span><span class="chip">${e(item.task.metric)}</span></div><div class="project-foot"><a class="card-link" href="#/models/${e(item.id)}">查看详情 ${icon("arrow", 13)}</a></div>`, "catalog-card model-card")).join("")}</div>` : emptyState("没有找到模型", "调整搜索或筛选条件。");
  }
  return `${pageHeader("模型仓库", "按任务选择预置模型或网络，管理训练产物")}
    <div class="tabs">${tabs.map(([key, label]) => `<a class="tab ${tab === key ? "active" : ""}" href="#/models?tab=${key}">${label}</a>`).join("")}</div>
    <div class="toolbar"><div class="toolbar-left"><div class="search-field">${icon("search", 16)}<input class="input" type="search" placeholder="搜索模型或任务" value="${e(ui.search || "")}" data-filter="search" aria-label="搜索模型" /></div>${tab !== "my" ? `<select class="select filter-select" data-filter="modelGroup" aria-label="任务类型">${["全部类型", "图像", "文本", "表格", "大语言模型"].map(option => `<option ${group === option ? "selected" : ""}>${option}</option>`).join("")}</select>` : ""}</div></div>${contents}`;
}

export function renderModelDetail(state, id) {
  const model = modelById(id);
  if (!model) return emptyState("模型不存在", "返回模型库重新选择。", linkButton("返回模型库", "#/models"));
  const task = taskById(model.taskId);
  const datasets = state.datasets.filter(item => item.taskId === task.id && item.status === "可训练");
  return `<div class="breadcrumb"><a href="#/models">模型仓库</a>${icon("chevron", 13)}<span>${e(model.name)}</span></div>
    ${pageHeader(model.name, `${model.kind} · ${task.group} · ${task.name}`, linkButton("使用此模型训练", `#/train/new?task=${e(task.id)}&model=${e(model.id)}`, "primary", "plus"))}
    <div class="grid-2">${card(`<div class="card-header"><h2>适用任务</h2></div><dl class="info-list"><div><dt>任务类别</dt><dd>${e(task.group)} · ${e(task.name)}</dd></div><div><dt>训练方式</dt><dd>${e(model.kind)}</dd></div><div><dt>数据格式</dt><dd>${e(task.format)}</dd></div><div><dt>评估指标</dt><dd>${e(task.metric)}</dd></div></dl>`)}${card(`<div class="card-header"><h2>默认参数</h2></div><dl class="info-list">${task.params.map(param => `<div><dt>${e(param.label)}</dt><dd>${e(param.value)}</dd></div>`).join("")}</dl>`)}</div>
    <div class="section-heading"><h2>兼容数据集</h2></div>${card(datasets.length ? `<div class="table-scroll"><table class="table"><thead><tr><th>数据集</th><th>样本数</th><th>版本</th><th>操作</th></tr></thead><tbody>${datasets.map(dataset => `<tr><td><a class="row-link" href="#/datasets/${e(dataset.id)}">${e(dataset.name)}</a></td><td>${e(dataset.count)}</td><td>v${e(dataset.version)}</td><td><a class="card-link" href="#/train/new?task=${e(task.id)}&model=${e(model.id)}&dataset=${e(dataset.id)}">开始训练</a></td></tr>`).join("")}</tbody></table></div>` : emptyState("暂无兼容数据集", "先导入对应任务的数据集。", linkButton("导入数据集", `#/datasets/new?task=${e(task.id)}`, "primary")))}`;
}
