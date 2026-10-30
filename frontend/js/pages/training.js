import { TASKS, modelById, taskById } from "../data.js?v=console-4";
import { badge, card, emptyState, escapeHtml as e, icon, lineChart, linkButton, pageHeader } from "../ui.js?v=console-4";

const stepNames = ["任务与模型", "数据集", "参数与资源", "核对提交"];
const inputClass = "input";

function stepper(step) {
  return `<div class="wizard-steps" aria-label="新建训练步骤">${stepNames.map((name, index) => `${index ? '<span class="wizard-step-sep"></span>' : ""}<span class="wizard-step ${index === step ? "active" : index < step ? "done" : ""}"><span>${index < step ? icon("check", 12) : index + 1}</span>${name}</span>`).join("")}</div>`;
}

function summary(state, draft) {
  const task = taskById(draft.taskId);
  const dataset = state.datasets.find(item => item.id === draft.datasetId);
  const project = state.projects.find(item => item.id === draft.projectId);
  const model = modelById(draft.modelId);
  return card(`<h3>当前配置</h3>${[["项目", project?.name || draft.projectName || "未选择"], ["任务", task?.name || "未选择"], ["训练方式", model?.kind || "未选择"], ["模型 / 网络", model?.name || "未选择"], ["数据集", dataset?.name || "未选择"], ["资源", draft.gpu || "未选择"]].map(([label, value]) => `<div class="summary-row"><span>${label}</span><span>${e(value)}</span></div>`).join("")}`, "summary-panel");
}

function stepOne(state, draft, ui) {
  const task = taskById(draft.taskId);
  const group = ui.wizardGroup || task?.group || "图像";
  const projectOptions = state.projects.map(project => `<option value="${e(project.id)}" ${draft.projectId === project.id ? "selected" : ""}>${e(project.name)}</option>`).join("");
  const taskOptions = TASKS.filter(item => item.group === group).map(item => `<label class="option-card ${draft.taskId === item.id ? "selected" : ""}"><input type="radio" name="taskId" value="${item.id}" ${draft.taskId === item.id ? "checked" : ""} data-wizard-task /><span><strong>${e(item.name)}</strong></span></label>`).join("");
  const modelOptions = task?.models.map(model => `<label class="option-card ${draft.modelId === model.id ? "selected" : ""}"><input type="radio" name="modelId" value="${model.id}" ${draft.modelId === model.id ? "checked" : ""} data-wizard-model /><span><strong>${e(model.name)}</strong><span class="option-tags"><span class="chip">${e(model.kind)}</span></span></span></label>`).join("") || "";
  return `<div class="wizard-section"><h2>选择任务与模型</h2>
    <div class="field-row"><div class="field"><label for="project-select">训练项目</label><select id="project-select" class="select" name="projectId" data-wizard-project><option value="new" ${draft.projectId === "new" ? "selected" : ""}>+ 新建项目</option>${projectOptions}</select></div><div class="field"><label for="run-name">训练任务名称</label><input id="run-name" class="${inputClass}" name="name" value="${e(draft.name || "")}" placeholder="例如：安全帽检测 · 基线 03" maxlength="60" /></div></div>
    ${draft.projectId === "new" ? `<div class="field" style="margin-top:16px"><label for="project-name">项目名称</label><input id="project-name" class="${inputClass}" name="projectName" value="${e(draft.projectName || "")}" placeholder="例如：商品分类" maxlength="50" /></div>` : ""}
    <div class="form-divider">任务类型</div><div class="choice-row">${["图像", "文本", "表格", "大语言模型"].map(item => `<button type="button" class="choice-button ${group === item ? "active" : ""}" data-action="wizard-group" data-group="${item}">${item}</button>`).join("")}</div><div class="wizard-options">${taskOptions}</div>
    <div class="form-divider">训练方式</div><div class="wizard-options">${modelOptions}</div></div>`;
}

function stepTwo(state, draft) {
  const available = state.datasets.filter(item => item.taskId === draft.taskId && item.status === "可训练");
  const rows = available.map(item => `<label class="option-card ${draft.datasetId === item.id ? "selected" : ""}"><input type="radio" name="datasetId" value="${e(item.id)}" ${draft.datasetId === item.id ? "checked" : ""} data-wizard-dataset /><span><strong>${e(item.name)}</strong><span class="option-tags"><span class="chip">v${item.version}</span><span class="chip">${e(item.count)} 样本</span></span></span></label>`).join("");
  return `<div class="wizard-section"><h2>选择数据集</h2>
    ${available.length ? `<div class="wizard-options">${rows}</div>` : emptyState("暂无可用数据集", "先导入并处理对应任务的数据集。", linkButton("导入数据集", `#/datasets/new?task=${e(draft.taskId)}`, "primary", "plus"))}
    <div style="margin-top:18px"><a class="card-link" href="#/datasets/new?task=${e(draft.taskId)}">导入新数据集 ${icon("arrow", 13)}</a></div></div>`;
}

function stepThree(draft) {
  const task = taskById(draft.taskId);
  const isQwen = draft.modelId?.startsWith("qwen25-");
  return `<div class="wizard-section"><h2>参数与资源</h2><div class="field-row-3">${(task?.params || []).map(param => `<div class="field"><label for="param-${param.name}">${e(param.label)}</label><input id="param-${param.name}" class="${inputClass}" type="number" name="${param.name}" value="${e(draft[param.name] ?? param.value)}" min="${param.min}" max="${param.max}" step="${param.step}" /></div>`).join("")}</div>
    ${isQwen ? `<div class="form-divider">微调配置</div><div class="field-row-3"><div class="field"><label for="finetune-mode">方式</label><select id="finetune-mode" name="finetune" class="select"><option value="LoRA" ${(draft.finetune || "LoRA") === "LoRA" ? "selected" : ""}>LoRA</option><option value="全参数" ${draft.finetune === "全参数" ? "selected" : ""}>全参数</option></select></div><div class="field"><label for="lora-rank">LoRA 秩</label><input id="lora-rank" name="loraRank" type="number" class="input" min="4" max="64" value="${e(draft.loraRank || 8)}" /></div><div class="field"><label for="max-length">最大序列长度</label><input id="max-length" name="maxLength" type="number" class="input" min="128" max="4096" step="128" value="${e(draft.maxLength || 1024)}" /></div></div>` : ""}
    <div class="form-divider">计算资源</div><div class="wizard-options">${(isQwen ? ["GPU 01", "GPU 02"] : ["GPU 01", "GPU 02", "CPU 队列"]).map(resource => `<label class="option-card ${draft.gpu === resource ? "selected" : ""}"><input type="radio" name="gpu" value="${resource}" ${draft.gpu === resource ? "checked" : ""} data-wizard-gpu /><span><strong>${resource}</strong>${resource === "CPU 队列" ? "" : `<span class="option-tags"><span class="chip">RTX 4090</span><span class="chip">${resource === "GPU 01" ? "使用中" : "空闲"}</span></span>`}</span></label>`).join("")}</div></div>`;
}

function stepFour(state, draft) {
  const project = state.projects.find(item => item.id === draft.projectId);
  const dataset = state.datasets.find(item => item.id === draft.datasetId);
  const task = taskById(draft.taskId);
  const model = modelById(draft.modelId);
  const items = [["训练任务", draft.name], ["项目", project?.name || draft.projectName], ["任务类型", task?.name], ["模型 / 网络", `${model?.name}（${model?.kind}）`], ["数据集", `${dataset?.name} · v${dataset?.version}`], ["运行资源", draft.gpu], ["参数", `轮次 ${draft.epochs} · 批大小 ${draft.batch} · 学习率 ${draft.lr}`]];
  if (draft.modelId?.startsWith("qwen25-")) items.push(["微调", `${draft.finetune || "LoRA"} · 序列长度 ${draft.maxLength || 1024}${draft.finetune === "全参数" ? "" : ` · 秩 ${draft.loraRank || 8}`}`]);
  return `<div class="wizard-section"><h2>核对训练配置</h2><div class="review-list">${items.map(([label, value]) => `<div class="review-item"><span>${label}</span><strong>${e(value || "—")}</strong></div>`).join("")}</div></div>`;
}

export function renderTrainWizard(state, draft, step, ui) {
  const actions = `<div class="wizard-footer"><button class="btn btn-secondary rounded-lg text-sm font-medium transition-colors" data-action="wizard-back" ${step === 0 ? "disabled" : ""}>上一步</button><button class="btn btn-primary rounded-lg text-sm font-medium transition-colors" data-action="${step === 3 ? "wizard-submit" : "wizard-next"}">${step === 3 ? "创建演示任务" : "下一步"}${step === 3 ? "" : icon("arrow", 15)}</button></div>`;
  const inner = step === 0 ? stepOne(state, draft, ui)
    : step === 1 ? stepTwo(state, draft)
    : step === 2 ? stepThree(draft)
    : stepFour(state, draft);
  return `<div class="breadcrumb"><a href="#/projects">训练项目</a>${icon("chevron", 13)}<span>新建训练</span></div>${pageHeader("新建训练", "从任务与模型开始，完成一次训练配置")}
    <div class="wizard-layout"><div class="wizard-main">${stepper(step)}${ui.wizardError ? `<div class="notice notice-danger" role="alert" style="margin-bottom:14px">${e(ui.wizardError)}</div>` : ""}${card(inner)}${actions}</div>${summary(state, draft)}</div>`;
}

export function renderRunList(state, ui) {
  const search = (ui.search || "").toLowerCase();
  const filter = ui.runStatus || "全部状态";
  const runs = state.runs.filter(run => (filter === "全部状态" || run.status === filter) && (!search || `${run.name} ${modelById(run.modelId)?.name}`.toLowerCase().includes(search)));
  const rows = runs.map(run => `<tr><td><a class="row-link" href="#/runs/${e(run.id)}">${e(run.name)}</a></td><td>${e(modelById(run.modelId)?.name || "—")}</td><td>${e(taskById(run.taskId)?.name || "—")}</td><td>${badge(run.status)}</td><td>${e(run.metric)} <strong>${e(run.score)}</strong></td><td>${e(run.gpu)}</td><td>${e(run.started)}</td></tr>`).join("");
  return `${pageHeader("训练任务", "查看进度、指标、日志和训练产物", linkButton("新建训练", "#/train/new", "primary", "plus"))}<div class="toolbar"><div class="toolbar-left"><div class="search-field">${icon("search", 16)}<input class="input" type="search" placeholder="搜索训练任务" value="${e(ui.search || "")}" data-filter="search" aria-label="搜索训练任务" /></div><select class="select filter-select" data-filter="runStatus" aria-label="任务状态">${["全部状态", "排队中", "运行中", "已完成", "失败"].map(status => `<option ${filter === status ? "selected" : ""}>${status}</option>`).join("")}</select></div><span class="subtle">共 ${runs.length} 次训练</span></div>${card(runs.length ? `<div class="table-scroll"><table class="table"><thead><tr><th>任务</th><th>模型</th><th>类型</th><th>状态</th><th>指标</th><th>资源</th><th>开始时间</th></tr></thead><tbody>${rows}</tbody></table></div>` : emptyState("没有找到任务", "调整筛选条件，或新建一次训练。"))}`;
}

function runLogs(run) {
  if (run.status === "排队中") return `[${run.started}] 任务已创建\n[${run.started}] 等待资源分配`;
  if (run.status === "失败") return `[${run.started}] 任务已创建\n[${run.started}] 开始读取数据集\n[${run.started}] 错误：数据集尚未处理完成，缺少可用训练样本\n[${run.started}] 任务结束：失败`;
  return `[${run.started}] 任务已创建\n[${run.started}] 数据集准备完成\n[${run.started}] 开始训练：${modelById(run.modelId)?.name || "模型"}\n[${run.started}] Epoch 1/${run.epochs} · loss 0.824\n[${run.started}] Epoch ${Math.max(2, Math.round(run.epochs * .4))}/${run.epochs} · loss 0.438\n[${run.started}] ${run.status === "已完成" ? "训练完成，模型产物已保存" : "训练中，等待下一轮指标"}`;
}

export function renderRunDetail(state, id, tab = "overview") {
  const run = state.runs.find(item => item.id === id);
  if (!run) return emptyState("任务不存在", "返回任务列表重新选择。", linkButton("返回训练任务", "#/runs"));
  const project = state.projects.find(item => item.id === run.projectId);
  const dataset = state.datasets.find(item => item.id === run.datasetId);
  const task = taskById(run.taskId);
  const model = modelById(run.modelId);
  const tabs = [["overview", "概况"], ["metrics", "指标"], ["logs", "日志"], ["outputs", "产物"]];
  const nav = `<div class="tabs" role="tablist">${tabs.map(([key, label]) => `<a class="tab ${tab === key ? "active" : ""}" href="#/runs/${e(run.id)}?tab=${key}" role="tab" aria-selected="${tab === key}">${label}</a>`).join("")}</div>`;
  const action = run.demo && ["排队中", "运行中"].includes(run.status) ? `<button class="btn btn-secondary rounded-lg text-sm font-medium transition-colors" data-action="advance-run" data-run-id="${e(run.id)}">推进演示状态</button>` : "";
  let panel;
  if (tab === "metrics") {
    panel = `<div class="grid-2">${card(`<div class="card-header"><h2>训练损失</h2></div>${lineChart([.94,.81,.72,.61,.53,.45,.39,.34,.29,.25], ["第 1 轮","训练轮次","最新"], "#315e72")}`)}${card(`<div class="card-header"><h2>${e(task?.metric || "评估指标")}</h2></div>${lineChart([.36,.44,.5,.57,.62,.68,.72,.76,.81,Number(run.score) || .83], ["第 1 轮","训练轮次","最新"], "#16805d")}`)}</div>`;
  } else if (tab === "logs") {
    panel = card(`<div class="card-header"><h2>训练日志</h2><button class="btn btn-secondary btn-small rounded-lg text-sm font-medium transition-colors" data-action="download-logs" data-run-id="${e(run.id)}">${icon("download", 14)}下载日志</button></div><pre class="log-box">${e(runLogs(run))}</pre>`);
  } else if (tab === "outputs") {
    panel = run.status === "已完成" ? `<div class="grid-2">${card(`<div class="card-header"><h2>模型产物</h2></div><div class="model-summary"><span class="type-mark image">模</span><div><strong>${e(project?.name || "训练模型")} · v1</strong></div></div><hr/><div class="callout-row"><span class="label">模型格式</span><span class="value">演示模型记录</span></div><div class="callout-row"><span class="label">主要指标</span><span class="value">${e(run.metric)} ${e(run.score)}</span></div><div style="margin-top:16px">${linkButton("查看我的模型", "#/models?tab=my", "secondary")}</div>`)}${card(`<div class="card-header"><h2>后续操作</h2></div>${linkButton("创建推理服务", `#/services/new?run=${e(run.id)}`, "primary", "plus")}`)}</div>` : emptyState("暂无模型产物", "任务完成后会在此展示模型版本和结果摘要。");
  } else {
    panel = `<div class="grid-3">${card(`<div class="metric-label">训练进度</div><div class="metric-value blue">${e(run.progress)}%</div><div class="progress" style="margin-top:14px"><span style="width:${e(run.progress)}%"></span></div>`, "metric-card")}${card(`<div class="metric-label">${e(run.metric)}</div><div class="metric-value green">${e(run.score)}</div>`, "metric-card")}${card(`<div class="metric-label">运行时长</div><div class="metric-value" style="font-size:21px">${e(run.duration)}</div>`, "metric-card")}</div>
      ${run.status === "失败" ? `<div class="notice notice-danger" style="margin:16px 0">数据集尚未处理完成。请先在数据集页面完成检查与处理，再重新创建任务。</div>` : ""}
      <div class="section-heading"><h2>任务配置</h2></div>${card(`<dl class="info-list"><div><dt>项目</dt><dd><a class="card-link" href="#/projects/${e(project?.id || "")}">${e(project?.name || "—")}</a></dd></div><div><dt>任务类型</dt><dd>${e(task?.name || "—")}</dd></div><div><dt>模型 / 网络</dt><dd>${e(model?.name || "—")} · ${e(model?.kind || "—")}</dd></div><div><dt>数据集</dt><dd>${e(dataset?.name || "—")}</dd></div><div><dt>计算资源</dt><dd>${e(run.gpu)}</dd></div><div><dt>参数</dt><dd>轮次 ${e(run.epochs)} · 批大小 ${e(run.batch)} · 学习率 ${e(run.lr)}</dd></div>${run.finetune ? `<div><dt>微调</dt><dd>${e(run.finetune)} · 序列长度 ${e(run.maxLength)} · LoRA 秩 ${e(run.loraRank)}</dd></div>` : ""}</dl>`)}
      <div class="section-heading"><h2>执行记录</h2></div>${card(`<div class="callout-row"><span class="label">创建任务</span><span class="value">${e(run.started)}</span>${badge("已完成")}</div><div class="callout-row"><span class="label">资源分配</span><span class="value">${e(run.gpu)}</span>${badge(run.status === "排队中" ? "排队中" : "已完成")}</div><div class="callout-row"><span class="label">训练执行</span><span class="value">${e(run.duration)}</span>${badge(run.status)}</div>`)} `;
  }
  return `<div class="breadcrumb"><a href="#/runs">训练任务</a>${icon("chevron", 13)}<span>${e(run.name)}</span></div><div class="detail-header"><div><div class="detail-title"><h1>${e(run.name)}</h1>${badge(run.status)}</div></div><div class="detail-actions">${action}${linkButton("新建训练", `#/train/new?project=${e(run.projectId)}`, "secondary", "plus")}</div></div>${nav}${panel}`;
}
