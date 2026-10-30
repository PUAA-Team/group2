import { badge, btn, can, date, e, fieldsInfo, input, link, options, pageHeader, pager, select, table, tag, TASKS, toolbar, workspaceRequired } from "./components.js?v=stage13-3a";
import { renderProjectCatalog, taskFilter } from "./catalog.js?v=stage13-3a";
import { renderTrainingDetail } from "./job-detail.js?v=stage13-3a";
import { renderWizard } from "./training-wizard.js?v=stage13-3a";

const routes = { "/runs": "train", "/admin/jobs": "train", "/evaluation": "evaluate", "/services": "service" };
const titles = { train: "训练任务", evaluate: "模型评估", service: "在线服务" };
export const JOB_STATUS = { draft: "草稿", queued: "排队中", preparing: "准备中", running: "运行中", ready: "运行中", stopping: "停止中", stopped: "已停止", cancelled: "已取消", succeeded: "已完成", failed: "失败" };
const ended = ["cancelled", "stopped", "succeeded", "failed"];
export const isWorkflowPage = path => !!routes[path] || path === "/train/new" || path === "/projects" || path === "/api-keys" || /^\/runs\/[^/]+$/.test(path);
const formFields = ["name", "model_version_id", "dataset_version_id", "project_id", "device_kind", "node_id"];

function inferenceFields(profile = {}) {
  const labels = profile.labels || [], mode = profile.mode || "generate";
  return select("输出方式", "inference_mode", options([["label", "标签分类"], ["generate", "自由生成"]], mode), "data-inference-mode") +
    `<div class="field"><label for="inference-instruction">任务指令</label><textarea id="inference-instruction" class="textarea" name="inference_instruction" maxlength="2048" rows="3" ${mode === "label" ? "required" : ""}>${e(profile.instruction || "")}</textarea></div>` +
    `<div class="field" data-inference-labels ${mode === "label" ? "" : "hidden"}><label for="inference-labels">输出标签</label><textarea id="inference-labels" class="textarea" name="inference_labels" rows="3" ${mode === "label" ? "required" : ""}>${e(labels.join("\n"))}</textarea></div>`;
}

export async function loadWorkflow(api, ctx, signal) {
  if (!ctx.workspace) return {};
  const base = `/workspaces/${ctx.workspace.id}`;
  const query = `page=${ctx.page}&page_size=20&q=${encodeURIComponent(ctx.q)}`;
  const detailId = ctx.path.match(/^\/runs\/([^/]+)$/)?.[1];
  let data;
  if (detailId) {
    const job = (await api.request(`${base}/jobs/${encodeURIComponent(detailId)}`, { signal })).data;
    let events = [], after = 0;
    for (let round = 0; round < 25; round++) {
      const batch = (await api.request(`${base}/jobs/${encodeURIComponent(detailId)}/events?after=${after}`, { signal })).data;
      events.push(...batch); if (batch.length < 200) break; after = batch.at(-1).seq;
    }
    data = { item: job, events };
  } else if (ctx.path === "/train/new") {
    const source = ctx.params.get("edit") || ctx.params.get("copy");
    data = source ? { sourceJob: (await api.request(`${base}/jobs/${encodeURIComponent(source)}`, { signal })).data } : {};
  } else if (ctx.path === "/projects") data = await api.request(`${base}/project-catalog?${query}`, { signal });
  else if (ctx.path === "/api-keys") data = await api.request(`${base}/service-keys`, { signal });
  else {
    const filters = new URLSearchParams();
    for (const key of ["status", "device_kind", "task_type", "sort"]) if (ctx.params?.get(key)) filters.set(key, ctx.params.get(key));
    data = await api.request(`${base}/jobs?kind=${routes[ctx.path] || "train"}&${query}&${filters}${ctx.params?.get("project") ? `&project_id=${encodeURIComponent(ctx.params.get("project"))}` : ""}`, { signal });
  }
  const editable = ["training.write", "services.write"].some(action => can(ctx, action));
  if (editable) {
    data.options = can(ctx, "models.read") && can(ctx, "datasets.read") ? (await api.request(`${base}/job-options`, { signal })).data : { models: [], datasets: [] };
    data.projects = can(ctx, "training.read") ? await api.all(`${base}/projects`, signal) : [];
    data.nodes = can(ctx, "resources.read") ? await api.all(`${base}/resources`, signal) : [];
    if (ctx.path === "/api-keys") data.services = await api.all(`${base}/jobs?kind=service`, signal);
  }
  return data;
}

function metricValues(result = {}) {
  return [["准确率", result.accuracy === undefined ? "—" : `${(result.accuracy * 100).toFixed(1)}%`],
    ["Macro F1", result.macro_f1 === undefined ? "—" : result.macro_f1.toFixed(3)],
    ["Loss", result.validation_loss === undefined && result.loss === undefined ? "—" : Number(result.validation_loss ?? result.loss).toFixed(4)]];
}

export function metricChart(events, names, title) {
  const rows = events.filter(item => item.type === "metric").map(item => item.payload);
  const values = rows.flatMap(row => names.map(key => row[key]).filter(Number.isFinite));
  if (!values.length) return `<section class="execution-chart"><h2>${e(title)}</h2><div class="empty-state">暂无指标</div></section>`;
  const max = Math.max(...values, 0.01) * 1.12, min = Math.min(0, ...values), width = 600, height = 210;
  const colors = ["#176bc1", "#198a71"];
  const lines = names.map((key, index) => {
    const points = rows.map((row, position) => Number.isFinite(row[key]) ? `${52 + position / Math.max(1, rows.length - 1) * 522},${177 - (row[key] - min) / (max - min) * 148}` : null).filter(Boolean).join(" ");
    return `<polyline fill="none" stroke="${colors[index]}" stroke-width="2.4" points="${points}"/>` + rows.map((row, position) => Number.isFinite(row[key]) ? `<circle cx="${52 + position / Math.max(1, rows.length - 1) * 522}" cy="${177 - (row[key] - min) / (max - min) * 148}" r="3.2" fill="${colors[index]}"><title>Epoch ${e(row.epoch)} · ${e(key)} ${e(row[key])}</title></circle>` : "").join("");
  }).join("");
  return `<section class="execution-chart"><div class="section-heading"><h2>${e(title)}</h2><div class="heading-actions">${names.map((name, i) => `<span class="chart-legend" style="--line:${colors[i]}">${e(name)}</span>`).join("")}</div></div><svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${e(title)}">${[0, 1, 2, 3].map(i => `<line x1="52" y1="${29 + i * 49.3}" x2="574" y2="${29 + i * 49.3}" stroke="#e6eaf0"/><text x="43" y="${34 + i * 49.3}" text-anchor="end">${(max - (max - min) * i / 3).toFixed(2)}</text>`).join("")}${lines}<text x="52" y="203">Epoch ${e(rows[0].epoch)}</text><text x="574" y="203" text-anchor="end">${e(rows.at(-1).epoch)}</text></svg></section>`;
}

function detail(ctx) {
  const job = ctx.data.item, write = can(ctx, job.kind === "service" ? "services.write" : "training.write");
  const actions = (job.status === "draft" && write ? btn("编辑草稿", "workflow-edit", job.id) + btn("提交", "workflow-submit", job.id, "primary") : "") +
    (!ended.includes(job.status) && write ? btn(job.status === "draft" || job.status === "queued" ? "取消任务" : "停止", "workflow-stop", job.id, "secondary", job.status === "stopping") : "") +
    (ended.includes(job.status) && write ? btn("重跑", "workflow-retry", job.id) : "");
  const result = job.result || {}, events = ctx.data.events || [];
  const languageModel = job.snapshot?.task_type === "llm_sft";
  const source = ctx.data.options?.models.find(item => item.id === job.model_version_id);
  const dataset = ctx.data.options?.datasets.find(item => item.id === job.dataset_version_id);
  const meta = [["状态", badge(JOB_STATUS[job.status])], ["任务类型", tag(TASKS[job.snapshot?.task_type || source?.task_type] || "待提交")],
    ["模型版本", e(source ? `${source.name} / ${source.version}` : job.model_version_id)], ["数据版本", e(dataset ? `${dataset.name} / v${dataset.number}` : job.dataset_version_id || "—")],
    ["执行设备", tag(job.device_kind === "cuda" ? "GPU" : "CPU")], ["创建时间", e(date(job.created_at))]];
  if (job.kind === "service" && (job.snapshot?.trainer_id === "qwen-lora-v1" || source?.trainer_id === "qwen-lora-v1")) meta.push(["输出方式", tag(job.config.inference?.mode === "label" ? "标签分类" : "自由生成")], ...(job.config.inference?.mode === "label" ? [["输出标签", job.config.inference.labels.map(tag).join(" ")]] : []));
  const configuration = `<div class="section-heading"><h2>训练配置</h2></div>` + fieldsInfo([["Epochs", e(job.config.epochs)], ["Batch size", e(job.config.batch_size)], ["Learning rate", e(job.config.learning_rate)], ["验证比例", e(job.config.validation_ratio)], ["Seed", e(job.config.seed)], ...(job.snapshot?.trainer_id === "qwen-lora-v1" ? [["最大长度", e(job.config.max_length)], ["LoRA rank", e(job.config.lora_rank)]] : [])]);
  const outcome = job.status === "succeeded" ? `<div class="section-heading"><h2>执行结果</h2><div class="heading-actions">${job.artifact_sha256 ? `<a class="btn btn-secondary" href="/api/v1/workspaces/${e(ctx.workspace.id)}/jobs/${e(job.id)}/artifact">下载产物</a>` : ""}${job.output_model_version_id && can(ctx, "training.write") ? btn("创建评估", "workflow-evaluate", job.output_model_version_id) : ""}${job.output_model_version_id && can(ctx, "services.write") ? btn("部署服务", "workflow-deploy", job.output_model_version_id, "primary") : ""}</div></div>` + fieldsInfo([...metricValues(result).map(([key, value]) => [key, e(value)]), ...["samples", "training_samples", "validation_samples", "response_tokens", "perplexity"].filter(key => result[key] !== undefined).map(key => [({ samples: "样本数", training_samples: "训练样本", validation_samples: "验证样本", response_tokens: "响应 Token", perplexity: "困惑度" })[key], e(Number(result[key]).toFixed(key === "perplexity" ? 3 : 0))])]) +
    (result.confusion_matrix ? `<div class="section-heading"><h2>混淆矩阵</h2>${tag("行：实际 / 列：预测")}</div>` + table(["类别", ...result.labels], result.confusion_matrix.map((row, i) => [e(result.labels[i]), ...row.map(e)])) : "") : "";
  const prediction = ctx.callResult?.job_id === job.id ? ctx.callResult.result : null;
  const predictionHtml = prediction?.label ? fieldsInfo([["分类结果", tag(prediction.label)]]) : prediction ? `<pre class="execution-output">${e(typeof prediction.text === "string" ? prediction.text : JSON.stringify(prediction, null, 2))}</pre>` : "";
  const invoke = job.kind === "service" && can(ctx, "services.invoke") ? `<div class="section-heading"><h2>调用测试</h2>${btn("发送请求", "workflow-invoke", job.id, "primary", job.status !== "ready")}</div>${predictionHtml}` : "";
  return `<div class="breadcrumb"><a href="#${job.kind === "train" ? "/runs" : job.kind === "service" ? "/services" : "/evaluation"}">${titles[job.kind]}</a><span>/</span>${e(job.name)}</div>` + pageHeader(job.name, "", actions) +
    fieldsInfo(meta) + (job.queue_reason ? `<div class="notice">${e(job.queue_reason)}${ctx.access.quota.concurrent_jobs === 0 ? "；请先配置并发额度" : ""}</div>` : "") +
    (job.error ? `<div class="notice notice-danger" role="alert">${e(job.error)}</div>` : "") + outcome + invoke +
    (job.kind === "train" ? `<div class="execution-charts ${languageModel ? "execution-single-chart" : ""}">${metricChart(events, ["loss", "val_loss"], "Loss")}${languageModel ? "" : metricChart(events, ["accuracy", "val_accuracy"], "准确率")}</div>${configuration}` : "") +
    `<div class="section-heading"><h2>运行日志</h2>${btn("刷新", "refresh")}</div><pre class="execution-log">${e(events.filter(item => item.type === "log").map(item => item.payload.message).join("\n") || "暂无日志" )}</pre>`;
}

export function renderWorkflow(ctx) {
  if (ctx.path === "/train/new") return renderWizard(ctx);
  const title = ctx.path === "/projects" ? "训练项目" : ctx.path === "/api-keys" ? "API KEY管理" : titles[routes[ctx.path] || ctx.data.item?.kind || "train"];
  if (!ctx.workspace) return pageHeader(title) + workspaceRequired(ctx);
  if (ctx.data.item) return ctx.data.item.kind === "train" ? renderTrainingDetail(ctx, metricChart) : detail(ctx);
  if (ctx.path === "/projects") return renderProjectCatalog(ctx);
  if (ctx.path === "/api-keys") return pageHeader(title, "", can(ctx, "services.write") ? btn("创建密钥", "modal", "key-new", "primary") : "") +
    (ctx.generatedKey ? `<div class="notice"><label for="one-time-key">新密钥（仅显示本次）</label><div class="heading-actions"><input id="one-time-key" class="input" readonly value="${e(ctx.generatedKey)}"/>${btn("复制", "workflow-copy-key")}${btn("关闭", "workflow-hide-key")}</div></div>` : "") +
    table(["名称", "服务", "到期时间", "状态", "操作"], (ctx.data.data || []).map(item => [e(item.name), link(ctx.data.services?.find(service => service.id === item.job_id)?.name || item.job_id, `/runs/${item.job_id}`), date(item.expires_at), badge(item.revoked_at ? "已停用" : new Date(item.expires_at) <= new Date() ? "已停止" : "正常"), !item.revoked_at && can(ctx, "services.write") ? btn("撤销", "workflow-revoke-key", item.id) : "—"]));
  const kind = routes[ctx.path] || "train", write = can(ctx, kind === "service" ? "services.write" : "training.write");
  const rows = (ctx.data.data || []).map(item => [link(item.name, `/runs/${item.id}`), e(item.model_name || "—"), tag(TASKS[item.task_type] || "—"), badge(JOB_STATUS[item.status]), tag(item.device_kind === "cuda" ? "GPU" : "CPU"), ...metricValues(item.result).map(([, value]) => e(value)), date(item.created_at)]);
  const add = write ? btn(kind === "train" ? "新建训练" : kind === "evaluate" ? "创建评估" : "部署服务", "workflow-new", kind, "primary") : "";
  const filters = taskFilter(ctx) + `<select class="select filter-select" data-query-filter="status" aria-label="任务状态">${options([["", "全部状态"], ...Object.entries(JOB_STATUS)], ctx.params?.get("status") || "")}</select>`;
  return pageHeader(title, "", add) + toolbar(ctx.q, filters, "搜索任务") + table(["名称", "模型", "任务类型", "状态", "资源", "准确率", "Macro F1", "Loss", "创建时间"], rows) + pager(ctx.data.pagination);
}

export function workflowDialog(modal, ctx) {
  const item = modal.item || {}, choices = ctx.data.options || { models: [], datasets: [] };
  if (modal.kind === "project-new") return { title: "新建项目", fields: input("项目名称", "name", "", 'required maxlength="100"'), submit: "创建" };
  if (modal.kind === "job-new" || modal.kind === "job-edit") {
    const kind = item.kind || "train";
    const models = choices.models.filter(model => kind === "train" || model.status === "available");
    const model = models.find(model => model.id === item.model_version_id) || models[0];
    const config = { epochs: model?.task_type === "llm_sft" ? 1 : 5, batch_size: model?.task_type === "llm_sft" ? 1 : 8, learning_rate: model?.task_type === "llm_sft" ? 0.0002 : 0.01, validation_ratio: 0.2, seed: 42, max_length: 128, lora_rank: 4, ...(item.config || {}) };
    let fields = input("名称", "name", item.name || "", 'required maxlength="100"') +
      `<div class="live-field-grid">${select("模型版本", "model_version_id", options(models.map(m => [m.id, `${m.name} / ${m.version}`]), model?.id), "required data-job-model")}${kind === "service" ? "" : select("数据版本", "dataset_version_id", options(choices.datasets.filter(data => data.task_type === model?.task_type).map(data => [data.id, `${data.name} / v${data.number}`]), item.dataset_version_id), "required")}</div>` +
      `<div class="live-field-grid">${select("设备", "device_kind", options([["cpu", "CPU"], ["cuda", "GPU"]], item.device_kind || (model?.task_type === "llm_sft" ? "cuda" : "cpu")))}${select("节点", "node_id", options([["", "自动选择"], ...(ctx.data.nodes || []).map(node => [node.id, node.name])], item.node_id || ""))}</div>`;
    if (kind === "service") fields += `<div class="stack" data-inference-settings>${model?.trainer_id === "qwen-lora-v1" ? inferenceFields(config.inference || model.inference_suggestion) : ""}</div>`;
    if (kind === "train") fields += select("项目", "project_id", options([["", "未分组"], ...(ctx.data.projects || []).map(project => [project.id, project.name])], item.project_id || ctx.params?.get("project"))) +
      `<div class="section-heading"><h2>训练参数</h2></div><div class="live-field-grid">${[["epochs", "Epochs", 1, 100, 1], ["batch_size", "Batch size", 1, 64, 1], ["learning_rate", "Learning rate", 0.000001, 1, "any"], ["validation_ratio", "验证比例", 0.1, 0.5, 0.05], ["seed", "Seed", 0, 2147483647, 1], ["max_length", "最大长度", 32, 512, 1]].map(([key, title, min, max, step]) => input(title, key, config[key], `required type="number" min="${min}" max="${max}" step="${step}"`)).join("")}${select("LoRA rank", "lora_rank", options([[4, "4"], [8, "8"], [16, "16"]], config.lora_rank))}</div>`;
    fields += `<label class="live-check"><input type="checkbox" name="submit_now" checked />立即提交</label>`;
    return { title: modal.kind === "job-edit" ? "编辑草稿" : kind === "train" ? "新建训练" : kind === "evaluate" ? "创建评估" : "部署服务", fields, wide: true, submit: "保存" };
  }
  if (modal.kind === "job-stop") return { title: "停止任务", fields: fieldsInfo([["任务", e(item.name)], ["当前状态", e(JOB_STATUS[item.status])]]), submit: "确认" };
  if (modal.kind === "service-invoke") return { title: "调用测试", fields: item.snapshot?.task_type === "image_classification" ? input("图片", "image", "", 'type="file" accept="image/png,image/jpeg" required') :
    (item.config?.inference?.mode === "label" ? `<div class="heading-actions">${item.config.inference.labels.map(tag).join("")}</div>` : "") + `<div class="field"><label for="call-text">输入内容</label><textarea id="call-text" class="textarea" name="text" required maxlength="4096" rows="5"></textarea></div>`, submit: "发送" };
  if (modal.kind === "key-new") return { title: "创建 API KEY", fields: input("名称", "name", "", 'required maxlength="100"') + select("服务", "job_id", options((ctx.data.services || []).map(job => [job.id, job.name])), "required") + input("有效天数", "days", 30, 'type="number" min="1" max="365" required'), submit: "创建" };
  if (modal.kind === "key-revoke") return { title: "撤销密钥", fields: fieldsInfo([["密钥名称", e(item.name)]]), submit: "撤销" };
  return null;
}

export async function saveWorkflow(api, modal, form, ctx) {
  const base = `/workspaces/${modal.workspaceId}`, item = modal.item || {};
  if (modal.kind === "project-new") { await api.request(base + "/projects", { method: "POST", body: { name: form.get("name") } }); return {}; }
  if (["job-new", "job-edit"].includes(modal.kind)) {
    const payload = Object.fromEntries(formFields.map(key => [key, form.get(key) || null]));
    payload.kind = item.kind || "train"; payload.config = item.config || {};
    if (payload.kind === "train") payload.config = Object.fromEntries(["epochs", "batch_size", "learning_rate", "validation_ratio", "seed", "max_length", "lora_rank"].map(key => [key, Number(form.get(key))]));
    if (payload.kind === "service") {
      payload.config = { ...payload.config, inference: form.has("inference_mode") ? { mode: form.get("inference_mode"), instruction: form.get("inference_instruction") || "",
        labels: form.get("inference_mode") === "label" ? String(form.get("inference_labels") || "").split(/\r?\n/).map(text => text.trim()).filter(Boolean) : [] } : null };
    }
    const result = (await api.request(`${base}/jobs${item.id ? `/${item.id}` : ""}`, { method: item.id ? "PATCH" : "POST", revision: item.revision, body: payload })).data;
    if (form.has("submit_now")) await api.request(`${base}/jobs/${result.id}/submit`, { method: "POST", revision: result.revision });
    return { destination: `/runs/${result.id}` };
  }
  if (modal.kind === "job-stop") { await api.request(`${base}/jobs/${item.id}/stop`, { method: "POST" }); return {}; }
  if (modal.kind === "service-invoke") {
    let body = { text: form.get("text") };
    if (form.get("image")) {
      const file = form.get("image"); if (file.size > 1024 * 1024) throw new Error("图片不得超过 1 MiB");
      const encoded = await new Promise((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(reader.result.split(",")[1]); reader.onerror = reject; reader.readAsDataURL(file); });
      body = { image_base64: encoded };
    }
    const call = (await api.request(`${base}/jobs/${item.id}/calls`, { method: "POST", body })).data;
    ctx.pendingCall = { id: call.id, workspaceId: modal.workspaceId, jobId: item.id }; ctx.callResult = { ...call, result: { 状态: "等待推理" } };
    return {};
  }
  if (modal.kind === "key-new") { ctx.generatedKey = (await api.request(base + "/service-keys", { method: "POST", body: { name: form.get("name"), job_id: form.get("job_id"), days: Number(form.get("days")) } })).data.key; return {}; }
  if (modal.kind === "key-revoke") { await api.request(base + `/service-keys/${item.id}/revoke`, { method: "POST" }); return {}; }
  return null;
}

export async function workflowAction(action, id, { api, ctx, openModal, render, navigate, load, toast }) {
  if (!action.startsWith("workflow-")) return false;
  const job = ctx.data.item;
  if (action === "workflow-new") id === "train" ? navigate("/train/new") : openModal("job-new", { kind: id });
  if (action === "workflow-edit") job.kind === "train" ? navigate(`/train/new?edit=${job.id}`) : openModal("job-edit", job);
  if (action === "workflow-stop") openModal("job-stop", job);
  if (action === "workflow-submit") {
    const model = ctx.data.options?.models.find(item => item.id === job.model_version_id);
    if (job.kind === "service" && !job.config.inference && (job.snapshot?.trainer_id === "qwen-lora-v1" || model?.trainer_id === "qwen-lora-v1")) { openModal("job-edit", job); return true; }
    await api.request(`/workspaces/${ctx.workspace.id}/jobs/${id}/submit`, { method: "POST", revision: job.revision }); await load();
  }
  if (action === "workflow-retry") { const result = (await api.request(`/workspaces/${ctx.workspace.id}/jobs/${id}/retry`, { method: "POST" })).data; navigate(result.kind === "train" ? `/train/new?edit=${result.id}` : `/runs/${result.id}`); }
  if (action === "workflow-deploy" || action === "workflow-evaluate") openModal("job-new", { kind: action === "workflow-deploy" ? "service" : "evaluate", model_version_id: id, dataset_version_id: job.dataset_version_id, device_kind: job.device_kind });
  if (action === "workflow-invoke") openModal("service-invoke", job);
  if (action === "workflow-revoke-key") openModal("key-revoke", ctx.data.data.find(item => item.id === id));
  if (action === "workflow-copy-key") { await navigator.clipboard.writeText(ctx.generatedKey); toast("已复制"); }
  if (action === "workflow-hide-key") { ctx.generatedKey = null; render(); }
  return true;
}

export function workflowModelChanged(form, ctx) {
  const selected = ctx.data.options?.models.find(item => item.id === form.elements.model_version_id.value);
  if (form.elements.dataset_version_id) form.elements.dataset_version_id.innerHTML = options((ctx.data.options?.datasets || []).filter(item => item.task_type === selected?.task_type).map(item => [item.id, `${item.name} / v${item.number}`]));
  const inference = form.querySelector("[data-inference-settings]");
  if (inference) inference.innerHTML = selected?.trainer_id === "qwen-lora-v1" ? inferenceFields(selected.inference_suggestion) : "";
  if (selected?.task_type === "llm_sft") {
    form.elements.device_kind.value = "cuda";
    for (const [key, value] of Object.entries({ epochs: 1, batch_size: 1, learning_rate: 0.0002 })) if (form.elements[key]) form.elements[key].value = value;
  }
}

export function workflowOutputModeChanged(form) {
  const classify = form.elements.inference_mode.value === "label";
  form.querySelector("[data-inference-labels]").hidden = !classify;
  form.elements.inference_labels.required = classify;
  form.elements.inference_instruction.required = classify;
}
