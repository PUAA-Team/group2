import { btn, can, card, e, fieldsInfo, input, options, pageHeader, select, tag, TASKS, workspaceRequired } from "./components.js?v=stage13-3a";

const steps = ["任务与模型", "数据集", "参数与资源", "核对提交"];
const numbers = ["epochs", "batch_size", "learning_rate", "validation_ratio", "seed", "max_length", "lora_rank"];
const defaults = task => ({ epochs: task === "llm_sft" ? 1 : 5, batch_size: task === "llm_sft" ? 1 : 8, learning_rate: task === "llm_sft" ? 0.0002 : 0.01, validation_ratio: 0.2, seed: 42, max_length: 128, lora_rank: 4 });

export function initialDraft(ctx, source) {
  const models = ctx.data.options?.models || [];
  const model = models.find(item => item.id === (source?.model_version_id || ctx.params?.get("model_version"))) || models[0];
  const task = model?.task_type || "text_classification";
  return { workspaceId: ctx.workspace.id, key: ctx.params?.get("edit") || ctx.params?.get("copy") || "new", step: 0,
    editId: ctx.params?.get("edit") ? source?.id : null, created: null, revision: source?.revision,
    values: { name: source ? source.name + (ctx.params?.get("edit") ? "" : " · 副本") : "", task_type: task,
      project_id: source?.project_id || ctx.params?.get("project") || "", model_version_id: model?.id || "",
      dataset_version_id: source?.dataset_version_id || ctx.params?.get("dataset_version") || "", device_kind: source?.device_kind || (task === "llm_sft" ? "cuda" : "cpu"),
      node_id: source?.node_id || "", min_memory_mb: source?.min_memory_mb || 0, priority: source?.priority || 0, ...defaults(task), ...(source?.config || {}) } };
}

export function ensureDraft(ctx) {
  const key = ctx.params?.get("edit") || ctx.params?.get("copy") || "new";
  if (!ctx.wizard || ctx.wizard.workspaceId !== ctx.workspace.id || ctx.wizard.key !== key) ctx.wizard = initialDraft(ctx, ctx.data.sourceJob);
  return ctx.wizard;
}

export function captureDraft(draft, form) {
  const before = JSON.stringify(draft.values);
  for (const [key, value] of form.entries()) if (key !== "submit_now") draft.values[key] = numbers.includes(key) || ["priority", "min_memory_mb"].includes(key) ? Number(value) : String(value);
  if (JSON.stringify(draft.values) !== before) draft.dirty = true;
  return draft;
}

export function updateTask(draft, choices, task, selected) {
  const model = choices.models.find(item => item.id === selected && item.task_type === task) || choices.models.find(item => item.task_type === task);
  const changed = task !== draft.values.task_type;
  Object.assign(draft.values, { task_type: task, model_version_id: model?.id || "", dataset_version_id: "" });
  if (changed) Object.assign(draft.values, defaults(task), { device_kind: task === "llm_sft" ? "cuda" : "cpu", node_id: "" });
}

export function parameterFields(values, llm) {
  return `<div class="live-field-grid">${[["epochs", "Epochs", 1, 100, 1], ["batch_size", "Batch size", 1, 64, 1], ["learning_rate", "Learning rate", 0.000001, 1, "any"], ["validation_ratio", "验证比例", 0.1, 0.5, 0.05], ["seed", "Seed", 0, 2147483647, 1], ...(llm ? [["max_length", "最大长度", 32, 512, 1]] : [])].map(([key, title, min, max, step]) => input(title, key, values[key], `required type="number" min="${min}" max="${max}" step="${step}"`)).join("")}${llm ? select("LoRA rank", "lora_rank", options([[4, "4"], [8, "8"], [16, "16"]], values.lora_rank)) : ""}</div>`;
}

export function renderWizard(ctx) {
  if (!ctx.workspace) return pageHeader("新建训练") + workspaceRequired(ctx);
  if (!can(ctx, "training.write")) return pageHeader("无权创建训练");
  const draft = ensureDraft(ctx), v = draft.values, choices = ctx.data.options || { models: [], datasets: [] };
  const model = choices.models.find(item => item.id === v.model_version_id);
  const compatible = choices.datasets.filter(item => item.task_type === v.task_type && !["validation", "test"].includes(item.provenance?.partition));
  let fields;
  if (draft.step === 0) fields = input("训练任务名称", "name", v.name, 'required maxlength="100"') + `<div class="live-field-grid">${select("任务类型", "task_type", options(Object.entries(TASKS), v.task_type), "required data-wizard-task")}${select("训练项目", "project_id", options([["", "未分组"], ...(ctx.data.projects || []).map(item => [item.id, item.name])], v.project_id))}</div>` +
    select("模型版本", "model_version_id", options(choices.models.filter(item => item.task_type === v.task_type).map(item => [item.id, `${item.name} / ${item.version}`]), v.model_version_id), "required data-wizard-model") + (model ? `<div class="console-selection">${tag(TASKS[v.task_type])}${tag(model.trainer_id === "qwen-lora-v1" ? "LoRA" : model.source_ref?.startsWith("artifact://") ? "继续训练" : "基础训练")}${tag(model.version)}</div>` : '<div class="notice">请先登记兼容的模型版本。</div>');
  if (draft.step === 1) fields = select("数据集版本", "dataset_version_id", options([["", "请选择数据版本"], ...compatible.map(item => [item.id, `${item.name} / v${item.number} / ${item.sample_count} 条`])], v.dataset_version_id), "required data-wizard-dataset") +
    `<div class="heading-actions">${btn("样本预览", "wizard-preview", "", "secondary", !v.dataset_version_id)}<a class="entity-link" href="#/datasets/new">导入数据集</a></div>` + (draft.preview ? `<pre class="template-preview">${e(JSON.stringify(draft.preview.samples, null, 2))}</pre>` : "") + (!compatible.length ? '<div class="notice">当前任务尚无可训练的数据版本。</div>' : "");
  if (draft.step === 2) fields = parameterFields(v, v.task_type === "llm_sft") + `<div class="section-heading"><h2>计算资源</h2></div><div class="live-field-grid">${select("设备", "device_kind", options(v.task_type === "llm_sft" ? [["cuda", "GPU"]] : [["cpu", "CPU"], ["cuda", "GPU"]], v.device_kind), "required")}${select("计算节点", "node_id", options([["", "自动选择"], ...(ctx.data.nodes || []).map(node => [node.id, node.name])], v.node_id))}${input("最低显存 / MiB", "min_memory_mb", v.min_memory_mb, 'type="number" min="0" max="1048576" required')}${input("优先级", "priority", v.priority, 'type="number" min="0" max="10" required')}</div>`;
  if (draft.step === 3) {
    const dataset = compatible.find(item => item.id === v.dataset_version_id);
    fields = fieldsInfo([["任务名称", e(v.name)], ["任务类型", tag(TASKS[v.task_type])], ["模型", e(model ? `${model.name} / ${model.version}` : "—")], ["数据集", e(dataset ? `${dataset.name} / v${dataset.number}` : "—")], ["设备", tag(v.device_kind === "cuda" ? "GPU" : "CPU")], ["节点", e(ctx.data.nodes?.find(node => node.id === v.node_id)?.name || "自动选择")], ...numbers.filter(key => v.task_type === "llm_sft" || !["max_length", "lora_rank"].includes(key)).map(key => [key, e(v[key])])]);
  }
  return `<div class="breadcrumb"><a href="#/runs">训练任务</a><span>/</span><span>${draft.editId ? "编辑草稿" : "新建训练"}</span></div>` + pageHeader(draft.editId ? "编辑训练草稿" : "新建训练") +
    `<ol class="console-stepper">${steps.map((name, index) => `<li class="${index === draft.step ? "active" : index < draft.step ? "complete" : ""}" ${index === draft.step ? 'aria-current="step"' : ""}><span>${index + 1}</span><strong>${name}</strong></li>`).join("")}</ol>` +
    `<form data-form="training-wizard" class="console-wizard-form"><div class="notice notice-danger" data-wizard-error role="alert" ${draft.error ? "" : "hidden"}>${e(draft.error || "")}</div>${card(`<div class="card-header"><h2>${steps[draft.step]}</h2></div><div class="stack">${fields}</div>`, "console-form-panel")}<div class="console-wizard-footer"><a class="btn btn-secondary" href="#/runs">返回列表</a><div class="heading-actions">${draft.step ? btn("上一步", "wizard-back") : ""}${draft.step < 3 ? btn("下一步", "wizard-next", "", "primary") : '<button class="btn btn-secondary" type="submit" name="intent" value="draft">保存草稿</button><button class="btn btn-primary" type="submit" name="intent" value="submit">提交训练</button>'}</div></div></form>`;
}

export async function persistTraining(api, ctx, submitNow) {
  const draft = ctx.wizard, v = draft.values, base = `/workspaces/${draft.workspaceId}`;
  const payload = { name: v.name, kind: "train", project_id: v.project_id || null, model_version_id: v.model_version_id, dataset_version_id: v.dataset_version_id,
    device_kind: v.device_kind, node_id: v.node_id || null, min_memory_mb: Number(v.min_memory_mb), priority: Number(v.priority), config: Object.fromEntries(numbers.map(key => [key, Number(v[key])])) };
  let job = draft.created;
  if (!job) {
    job = (await api.request(`${base}/jobs${draft.editId ? `/${draft.editId}` : ""}`, { method: draft.editId ? "PATCH" : "POST", revision: draft.revision, body: payload })).data;
    draft.created = job;
    draft.dirty = false;
  }
  if (job.status === "draft" && draft.dirty) {
    const current = (await api.request(`${base}/jobs/${job.id}`)).data;
    job = (await api.request(`${base}/jobs/${job.id}`, { method: "PATCH", revision: current.revision, body: payload })).data;
    draft.created = job; draft.dirty = false;
  }
  if (submitNow && job.status === "draft") {
    const current = (await api.request(`${base}/jobs/${job.id}`)).data;
    if (current.status === "draft") job = (await api.request(`${base}/jobs/${job.id}/submit`, { method: "POST", revision: current.revision })).data;
    else job = current;
    draft.created = job;
  }
  return `/runs/${job.id}`;
}
