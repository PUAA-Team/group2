import { TASKS, taskById } from "../data.js?v=console-4";
import { badge, card, emptyState, escapeHtml as e, icon, linkButton, pageHeader } from "../ui.js?v=console-4";

export function renderDatasetList(state, ui) {
  const search = (ui.search || "").trim().toLowerCase();
  const type = ui.datasetType || "全部类型";
  const items = state.datasets.filter(item => (type === "全部类型" || item.type === type) && (!search || `${item.name} ${item.format} ${taskById(item.taskId)?.name}`.toLowerCase().includes(search)));
  const rows = items.map(item => `<tr><td><a class="row-link" href="#/datasets/${e(item.id)}">${e(item.name)}</a></td><td>${e(item.type)}</td><td>${e(taskById(item.taskId)?.name || "—")}</td><td>v${e(item.version)}</td><td>${e(item.count || "—")}</td><td>${badge(item.status)}</td><td class="nowrap">${e(item.updated)}</td></tr>`).join("");
  const body = rows ? `<div class="table-scroll"><table class="table"><thead><tr><th>数据集</th><th>类型</th><th>适用任务</th><th>版本</th><th>样本数</th><th>状态</th><th>更新</th></tr></thead><tbody>${rows}</tbody></table></div>` : emptyState("没有找到数据集", "调整筛选条件，或导入新的数据集。", linkButton("导入数据集", "#/datasets/new", "primary", "plus"));
  return `${pageHeader("数据集", "按数据类型准备可训练的数据", linkButton("导入数据集", "#/datasets/new", "primary", "plus"))}
    <div class="toolbar"><div class="toolbar-left"><div class="search-field">${icon("search", 16)}<input class="input bg-zinc-100 border-0 rounded-lg text-sm" type="search" placeholder="搜索数据集" value="${e(ui.search || "")}" data-filter="search" aria-label="搜索数据集" /></div><select class="select filter-select" data-filter="datasetType" aria-label="数据类型">${["全部类型", "图像", "文本", "表格", "大语言模型"].map(option => `<option ${type === option ? "selected" : ""}>${option}</option>`).join("")}</select></div><span class="subtle">共 ${items.length} 个数据集</span></div>${card(body)}`;
}

export function renderDatasetNew(ui) {
  const task = taskById(ui.datasetTask || TASKS[0].id);
  const files = ui.datasetFiles || [];
  const fileList = files.map(file => `<div class="file-item"><span class="truncate">${e(file.name)}</span><span>${e((file.size / 1024).toFixed(1))} KB</span></div>`).join("");
  return `<div class="breadcrumb"><a href="#/datasets">数据集</a>${icon("chevron", 13)}<span>导入数据集</span></div>
    ${pageHeader("导入数据集", "先确定任务类型，再核对对应的数据格式")}
    <div class="split-layout"><form id="dataset-form" class="stack">
      ${card(`<div class="card-header"><div><h2>基本信息</h2></div></div><div class="field-row"><div class="field"><label for="dataset-name">数据集名称</label><input id="dataset-name" name="name" class="input bg-zinc-100 border-0 rounded-lg text-sm" value="${e(ui.datasetName || "")}" placeholder="例如：产品图片分类样本" required maxlength="50" /></div><div class="field"><label for="dataset-task">适用任务</label><select id="dataset-task" name="taskId" class="select" data-dataset-task>${TASKS.map(item => `<option value="${item.id}" ${item.id === task.id ? "selected" : ""}>${item.group} · ${item.name}</option>`).join("")}</select></div></div>`)}
      ${card(`<div class="card-header"><h2>选择文件</h2></div><label class="upload-zone">${icon("data", 23)}<strong>点击选择文件</strong><input id="dataset-files" type="file" multiple data-dataset-files /></label>${files.length ? `<div class="file-list">${fileList}</div>${ui.datasetPreview ? `<pre class="template-preview" style="margin-top:12px">${e(ui.datasetPreview)}</pre>` : ""}` : ""}<div class="field" style="margin-top:16px"><label for="sample-count">样本数（可选）</label><input id="sample-count" name="count" class="input" type="number" min="0" value="${e(ui.datasetCount || "")}" placeholder="导入后可补充" /></div>`)}
      <div class="heading-actions"><button class="btn btn-primary rounded-lg text-sm font-medium transition-colors" type="submit">登记数据集</button><a class="btn btn-secondary rounded-lg text-sm font-medium transition-colors" href="#/datasets">取消</a></div>
    </form><div class="stack">
      ${card(`<div class="card-header"><div><h2>格式模板</h2></div></div><pre class="template-preview">${e(task.template)}</pre><button class="btn btn-secondary btn-small rounded-lg text-sm font-medium transition-colors" style="margin-top:14px" data-action="download-template" data-task-id="${task.id}">${icon("download", 14)}下载示例</button>`)}
      ${card(`<div class="card-header"><h2>处理步骤</h2></div><div class="checklist">${task.processing.map(item => `<span class="check-item">${icon("check", 14)}${e(item)}</span>`).join("")}</div>`)}
    </div></div>`;
}

export function renderDatasetDetail(state, datasetId) {
  const item = state.datasets.find(dataset => dataset.id === datasetId);
  if (!item) return emptyState("数据集不存在", "返回列表重新选择。", linkButton("返回数据集", "#/datasets"));
  const task = taskById(item.taskId);
  const options = task?.processing || [];
  const fileNames = item.files?.length ? item.files.map(name => `<span class="chip">${e(name)}</span>`).join("") : '<span class="chip">无本地文件</span>';
  return `<div class="breadcrumb"><a href="#/datasets">数据集</a>${icon("chevron", 13)}<span>${e(item.name)}</span></div>
    <div class="detail-header"><div><div class="detail-title"><h1>${e(item.name)}</h1>${badge(item.status)}</div></div><div class="detail-actions">${linkButton("用此数据新建训练", `#/train/new?task=${e(item.taskId)}&dataset=${e(item.id)}`, "primary", "plus")}</div></div>
    <div class="grid-3">${card(`<div class="metric-label">样本数</div><div class="metric-value">${e(item.count || "—")}</div>`, "metric-card")}${card(`<div class="metric-label">数据规模</div><div class="metric-value" style="font-size:21px">${e(item.size)}</div>`, "metric-card")}${card(`<div class="metric-label">当前版本</div><div class="metric-value">v${e(item.version)}</div>`, "metric-card")}</div>
    <div class="section-heading"><h2>数据内容</h2></div><div class="grid-2">
      ${card(`<div class="card-header"><h2>格式与文件</h2></div><dl class="info-list"><div><dt>适用任务</dt><dd>${e(task?.name || "—")}</dd></div><div><dt>标注格式</dt><dd>${e(item.format)}</dd></div><div><dt>样本概况</dt><dd>${e(item.sample)}</dd></div><div><dt>更新时间</dt><dd>${e(item.updated)}</dd></div><div><dt>最近处理</dt><dd>${e(item.processing?.join("、") || "尚未在本演示中处理")}</dd></div></dl><hr/><div class="permission-cell">${fileNames}</div>`)}
      ${card(`<div class="card-header"><h2>格式示例</h2></div><pre class="template-preview">${e(task?.template || "—")}</pre><button class="btn btn-secondary btn-small rounded-lg text-sm font-medium transition-colors" style="margin-top:14px" data-action="download-template" data-task-id="${e(item.taskId)}">${icon("download", 14)}下载示例</button>`)}
    </div>
    <div class="section-heading"><h2>数据处理</h2><button class="btn btn-primary" data-action="open-modal" data-modal="process-dataset" data-id="${e(item.id)}">创建处理版本</button></div>${card(`<div class="checklist">${options.map(option => `<span class="check-item">${icon("check", 14)}${e(option)}</span>`).join("")}</div>`)}`;
}
