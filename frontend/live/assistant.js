import { badge, btn, can, date, e, fieldsInfo, input, link, options, pageHeader, pager, raw, select, table, tag, TASKS, workspaceRequired } from "./components.js?v=stage29-1";
import { captureDraft, jobPayload } from "./training-wizard.js?v=stage29-1";

const STATES = { preview: "预览待确认", queued: "排队中", running: "进行中", succeeded: "已完成", applied: "已采纳", failed: "失败", cancelled: "已取消" };
const PURPOSES = { annotation: "智能标注", parameters: "智能参数", logs: "智能解释" };
const SCOPES = [["configuration", "训练配置"], ["logs", "运行日志"], ["text_samples", "文本样本"], ["image_samples", "图像样本"]];
const PARAMETERS = { epochs: "训练轮次", batch_size: "批量大小", learning_rate: "学习率", validation_ratio: "验证比例", seed: "随机种子", max_length: "最大序列长度", lora_rank: "LoRA 秩" };
const USAGE_LABELS = { prompt_tokens: "提示 Token", completion_tokens: "完成 Token", total_tokens: "总 Token" };
const NEW_REQUESTS = ["assistant-annotation-new", "assistant-parameters-new", "assistant-logs-new"];

export const isAssistantPage = path => path === "/assistants" || /^\/assistants\/[^/]+$/.test(path);
const requestId = path => path.match(/^\/assistants\/([^/]+)$/)?.[1] || "";
const clip = (value, size = 36) => { const text = String(value ?? "").replace(/\s+/g, " ").trim(); return text.length > size ? `${text.slice(0, size)}…` : text; };

function objectText(item) {
  const source = item.source || {};
  if (item.purpose === "annotation") return `${TASKS[source.task_type] || "标注批次"} · ${(source.sample_indices || []).length} 个样本`;
  return source.job?.name || "训练任务";
}

function objectLink(item) {
  const source = item.source || {};
  if (item.purpose === "annotation" && source.batch_id) return link(objectText(item), `/annotation/${source.batch_id}`);
  if (item.purpose === "logs" && source.job_id) return link(objectText(item), `/runs/${source.job_id}`);
  return e(objectText(item));
}

const adoptTarget = target => target?.job_id ? link("训练草稿", `/runs/${target.job_id}`)
  : target?.batch_id ? link(`标注批次 ${target.indices?.length || 0} 个样本`, `/annotation/${target.batch_id}`) : "—";

export async function loadAssistant(api, ctx, signal) {
  if (!ctx.workspace) return {};
  const base = `/workspaces/${ctx.workspace.id}`;
  const id = requestId(ctx.path);
  if (id) return (await api.request(`${base}/assistant-requests/${encodeURIComponent(id)}`, { signal })).data;
  const query = new URLSearchParams({ page: ctx.page || 1, page_size: 20 });
  for (const key of ["purpose", "status"]) if (ctx.params.get(key)) query.set(key, ctx.params.get(key));
  return api.request(`${base}/assistant-requests?${query}`, { signal });
}

export function renderAssistant(ctx) {
  if (!ctx.workspace) return pageHeader("智能辅助") + workspaceRequired(ctx);
  return requestId(ctx.path) ? requestDetail(ctx) : requestList(ctx);
}

function objectCell(item) {
  const text = objectText(item);
  return raw(`<span class="live-source" title="${e(text)}">${objectLink(item)}</span>`);
}

function connectionText(item) {
  const connection = item.preview?.connection;
  if (!connection) return "—";
  return connection.model ? `${connection.name} · ${connection.model}` : connection.name;
}

function requestList(ctx) {
  const rows = (ctx.data.data || []).map(item => [objectCell(item), raw(tag(PURPOSES[item.purpose] || item.purpose)),
    raw(badge(STATES[item.status] || item.status) + (item.expired ? tag("预览已过期") : "")),
    raw(`<span class="live-source" title="${e(connectionText(item))}">${e(connectionText(item))}</span>`),
    date(item.created_at), raw(link("详情", `/assistants/${item.id}`))]);
  const filter = (key, label, entries) => `<select class="select" data-query-filter="${key}" aria-label="${label}">${options(entries, ctx.params.get(key))}</select>`;
  const actions = (can(ctx, "members.manage") ? btn("空间授权", "assistant-policy") : "") + btn("刷新", "refresh");
  const filtered = ["purpose", "status"].some(key => ctx.params?.get(key));
  return pageHeader("智能辅助", "", actions) +
    `<div class="toolbar">${filter("purpose", "用途", [["", "全部用途"], ...Object.entries(PURPOSES)])}${filter("status", "状态", [["", "全部状态"], ...Object.entries(STATES)])}</div>` +
    table(["对象", "用途", "状态", "模型连接", "创建时间", "操作"], rows, filtered ? "没有符合筛选条件的智能辅助请求" : "暂无智能辅助请求") + pager(ctx.data.pagination);
}

function resultPanel(item) {
  const result = item.result || {};
  const suggestions = rows => table(["参数", "建议值", "理由"], rows.map(value => [PARAMETERS[value.field] || value.field, value.value, value.reason]), "暂无参数建议");
  if (item.purpose === "annotation") {
    return table(["样本", "建议值", "理由"], (result.samples || []).map(value => [raw(tag(value.index + 1)), value.value, value.reason]), "暂无样本建议");
  }
  if (item.purpose === "parameters") return suggestions(result.suggestions || []);
  const causes = result.causes || [];
  return fieldsInfo([["摘要", e(result.summary || "—")]]) +
    (causes.length ? `<div class="section-heading"><h2>可能原因</h2><div class="heading-actions">${tag(`共 ${causes.length} 个`)}</div></div>` +
      causes.map((cause, index) => `<div class="live-cause"><h3>原因 ${index + 1}</h3><p>${e(cause.reason || "—")}</p>` +
        `<div class="live-detail-meta">${(cause.evidence || []).length ? (cause.evidence || []).map(value => tag(value)).join("") : tag("无日志序号")}</div>` +
        ((cause.steps || []).length ? `<ol>${(cause.steps || []).map(step => `<li>${e(step)}</li>`).join("")}</ol>` : "<p>暂无排查步骤</p>") +
        `</div>`).join("") : "") +
    (result.suggestions?.length ? suggestions(result.suggestions) : "");
}

function requestDetail(ctx) {
  const item = ctx.data, preview = item.preview || {}, mine = item.created_by === ctx.session.user.id;
  const write = item.purpose === "annotation" ? can(ctx, "datasets.write") : can(ctx, "training.write");
  const actions = btn("刷新", "refresh") +
    (mine && item.status === "preview" && !item.expired ? btn("确认发送", "assistant-confirm", item.id, "primary") : "") +
    (mine && ["preview", "queued", "running", "succeeded"].includes(item.status) ? btn("取消", "assistant-cancel", item.id) : "") +
    (mine && item.status === "succeeded" && write ? btn("采纳结果", "assistant-apply", item.id, "primary") : "");
  const marks = [tag(PURPOSES[item.purpose] || item.purpose), badge(STATES[item.status] || item.status)];
  if (item.expired) marks.push(tag("预览已过期"));
  if (preview.image_count) marks.push(tag(`图像 ${preview.image_count} 张 · 序号 ${(preview.image_indices || []).join(", ")}`));
  for (const [label, count] of Object.entries(preview.redactions || {})) marks.push(tag(`${label}已脱敏 ${count}`));
  const usage = Object.entries(item.usage || {}).filter(([, value]) => typeof value === "number");
  const usageStrip = usage.length ? `<div class="live-stat-strip">${usage.map(([key, value]) => `<div><span>${e(USAGE_LABELS[key] || key)}</span><strong>${e(value)}</strong></div>`).join("")}</div>` : "";
  return `<div class="breadcrumb">${link("智能辅助", "/assistants")} / ${e(objectText(item))}</div>` + pageHeader(objectText(item), "", actions) +
    `<div class="live-detail-meta">${marks.join("")}</div>` +
    fieldsInfo([["对象", objectLink(item)], ["模型连接", e(preview.connection ? `${preview.connection.name} · ${preview.connection.model}` : item.connection_id)],
      ["创建时间", date(item.created_at)], ["确认时间", date(item.confirmed_at)]]) +
    usageStrip +
    (item.expired ? '<div class="notice">预览已过期，请从对应业务页面重新生成。</div>' : "") +
    (item.error?.message ? `<div class="notice notice-danger" role="alert">${e(item.error.message)}</div>` : "") +
    `<div class="section-heading"><h2>外发内容</h2><div class="heading-actions">${tag(`输出上限 ${preview.max_tokens || item.max_tokens || "—"} Token`)}</div></div>` +
    (preview.system ? fieldsInfo([["系统指令", `<span class="live-break">${e(preview.system)}</span>`]]) : "") +
    `<pre class="execution-log console-log">${e(preview.text || "")}</pre>` +
    (preview.images || []).map(image => `<figure class="annotation-image"><img src="${e(image.data_url)}" alt="外发样本 ${image.index + 1}"/><figcaption>样本 ${image.index + 1}</figcaption></figure>`).join("") +
    (["succeeded", "applied"].includes(item.status) ? `<div class="section-heading"><h2>结果</h2></div>${resultPanel(item)}` : "") +
    (item.adoption ? `<div class="section-heading"><h2>采纳记录</h2></div>${fieldsInfo([["目标", adoptTarget(item.adoption.target)], ["采纳时间", date(item.adoption.created_at)]])}` : "");
}

const connectionChoices = (ctx, capability) => (ctx.assistantOptions?.connections || []).filter(item => (item.capabilities || []).includes(capability));

function policyDialog(ctx) {
  const policy = ctx.assistantOptions?.policy || {};
  const connections = ctx.assistantOptions?.connections || [];
  const checks = (name, label, entries) => `<fieldset class="live-check-field"><legend>${label}</legend><div class="live-checks">${entries.map(([key, text]) => `<label><input type="checkbox" name="${name}" value="${e(key)}" ${(policy[name] || []).includes(key) ? "checked" : ""}/>${e(text)}</label>`).join("")}</div></fieldset>`;
  return { title: "智能辅助授权", wide: true,
    fields: `<div class="live-checks"><label><input type="checkbox" name="enabled" ${policy.enabled ? "checked" : ""}/>启用智能辅助</label></div>` +
      (connections.length ? checks("connection_ids", "允许的模型连接", connections.map(value => [value.id, `${value.name} · ${value.model}`]))
        : '<div class="notice">平台尚未配置可用的模型连接，请先在系统设置中新增连接。</div>') +
      checks("scopes", "允许外发的内容", SCOPES) +
      `<div class="live-field-grid">${input("每日请求上限", "daily_requests", policy.daily_requests ?? 30, 'required type="number" min="1" max="1000"')}${input("单次样本数", "max_samples", policy.max_samples ?? 5, 'required type="number" min="1" max="20"')}${input("单次文字上限", "max_characters", policy.max_characters ?? 12000, 'required type="number" min="1000" max="30000"')}${input("输出上限 Token", "max_tokens", policy.max_tokens ?? 1024, 'required type="number" min="128" max="4096"')}</div>` };
}

function requestDialog(modal, ctx) {
  const purpose = modal.kind.split("-")[1], title = PURPOSES[purpose] || "智能辅助";
  const policy = ctx.assistantOptions?.policy || {}, item = modal.item || {};
  const blocked = policy.enabled ? "" : "空间尚未启用智能辅助，请先完成智能辅助授权";
  const image = purpose === "annotation" && ctx.data.dataset?.task_type === "image_classification";
  const connections = blocked ? [] : connectionChoices(ctx, image ? "vision" : "text").filter(value => policy.connection_ids?.includes(value.id));
  if (!connections.length) return { title, submit: "生成预览", readOnly: true,
    fields: `<div class="notice">${e(blocked || (image ? "没有支持图像输入的模型连接" : "空间没有可用的模型连接"))}</div>` };
  const chosen = select("模型连接", "connection_id", options(connections.map(value => [value.id, `${value.name} · ${value.model}`])), "required");
  if (purpose === "annotation") {
    const limit = Math.min(policy.max_samples || 5, image ? 4 : 20);
    const samples = (ctx.data.samples || []).filter(sample => sample.result?.state !== "approved").slice(0, limit);
    return { title, fields: chosen + `<fieldset class="live-check-field"><legend>选择样本（最多 ${limit} 个）</legend><div class="live-checks live-checks-stacked">${samples.map(sample => `<label><input type="checkbox" name="sample_indices" value="${sample.index}" ${sample.result ? "" : "checked"}/>样本 ${sample.index + 1}${sample.source?.text ? ` · ${e(clip(sample.source.text))}` : ""}</label>`).join("")}</div></fieldset>` };
  }
  if (purpose === "parameters") {
    const job = item.job || {}, config = job.config || {};
    return { title, fields: chosen + fieldsInfo([["任务名称", e(job.name || "—")], ["任务类型", tag(TASKS[job.task_type] || "—")],
      ...Object.entries(PARAMETERS).filter(([key]) => config[key] != null).map(([key, label]) => [label, e(config[key])])]) };
  }
  return { title, fields: chosen + `<div class="live-field-grid">${input("起始日志序号", "log_start", "", 'type="number" min="1"')}${input("结束日志序号", "log_end", "", 'type="number" min="1"')}</div>` };
}

function applyDialog(item) {
  const result = item.result || {};
  if (item.purpose === "annotation") {
    const checks = (result.samples || []).map(value => `<label><input type="checkbox" name="indices" value="${value.index}" checked/>样本 ${value.index + 1} · ${e(clip(value.value, 30))}</label>`).join("");
    return { title: "采纳智能标注", submit: "确认采纳",
      fields: `<fieldset class="live-check-field"><legend>写入标注草稿</legend><div class="live-checks live-checks-stacked">${checks}</div></fieldset><div class="notice">采纳的样本转为标注草稿，需人工审核通过后才能发布。</div>` };
  }
  const checks = (result.suggestions || []).map(value => `<label><input type="checkbox" name="fields" value="${e(value.field)}" checked/>${e(PARAMETERS[value.field] || value.field)} = ${e(value.value)}</label>`).join("");
  return { title: "采纳参数建议", submit: "确认采纳", readOnly: !checks,
    fields: (checks ? `<fieldset class="live-check-field"><legend>写入新草稿</legend><div class="live-checks live-checks-stacked">${checks}</div></fieldset>` : '<div class="notice">本次结果没有可采纳的参数。</div>') +
      input("草稿名称", "name", "", 'maxlength="100" placeholder="留空按原名称生成"') + '<div class="notice">采纳后创建新的训练草稿，不修改原任务。</div>' };
}

export function assistantDialog(modal, ctx) {
  if (modal.kind === "assistant-policy") return policyDialog(ctx);
  if (NEW_REQUESTS.includes(modal.kind)) return requestDialog(modal, ctx);
  if (modal.kind === "assistant-apply") return applyDialog(modal.item || {});
  return null;
}

export async function saveAssistant(api, modal, form, ctx) {
  const base = `/workspaces/${modal.workspaceId}`;
  const count = key => Number(form.get(key));
  if (modal.kind === "assistant-policy") {
    await api.request(`${base}/assistant-policy`, { method: "POST", body: { revision: ctx.assistantOptions?.policy?.revision || 0,
      enabled: form.has("enabled"), connection_ids: form.getAll("connection_ids"), scopes: form.getAll("scopes"),
      daily_requests: count("daily_requests"), max_samples: count("max_samples"),
      max_characters: count("max_characters"), max_tokens: count("max_tokens") } });
    return {};
  }
  if (NEW_REQUESTS.includes(modal.kind)) {
    const purpose = modal.kind.split("-")[1];
    const body = { purpose, connection_id: form.get("connection_id") };
    if (purpose === "annotation") Object.assign(body, { source_id: ctx.data.id, sample_indices: form.getAll("sample_indices").map(Number) });
    if (purpose === "parameters") body.job = modal.item.job;
    if (purpose === "logs") Object.assign(body, { source_id: modal.item.source_id, log_start: count("log_start") || null, log_end: count("log_end") || null });
    const result = await api.request(`${base}/assistant-requests`, { method: "POST", body });
    return { destination: `/assistants/${result.data.id}` };
  }
  if (modal.kind === "assistant-apply") {
    if (!(modal.item.purpose === "annotation" ? form.getAll("indices") : form.getAll("fields")).length) throw new Error("请选择要采纳的内容");
    const body = modal.item.purpose === "annotation" ? { indices: form.getAll("indices").map(Number) }
      : { fields: form.getAll("fields"), name: form.get("name") || null };
    const result = await api.request(`${base}/assistant-requests/${modal.item.id}/apply`, { method: "POST", body });
    return { destination: result.data.target?.job_id ? `/runs/${result.data.target.job_id}` : `/assistants/${modal.item.id}` };
  }
  return null;
}

export async function assistantAction(action, id, { api, ctx, openModal, load, toast, form }) {
  if (!action.startsWith("assistant-")) return false;
  const base = `/workspaces/${ctx.workspace?.id}`;
  if (action === "assistant-policy" || NEW_REQUESTS.includes(action)) {
    ctx.assistantOptions = (await api.request(`${base}/assistant-options`)).data;
    if (action === "assistant-parameters-new") {
      if (!ctx.wizard) throw new Error("请先完成训练参数填写");
      if (form) captureDraft(ctx.wizard, new FormData(form));
      const { name, model_version_id, dataset_version_id } = ctx.wizard.values;
      if (!String(name || "").trim()) throw new Error("请先填写训练任务名称");
      if (!model_version_id || !dataset_version_id) throw new Error("请先选择模型版本与数据集");
      openModal(action, { job: jobPayload(ctx.wizard.values) });
      return true;
    }
    openModal(action, action === "assistant-logs-new" ? { source_id: id } : {});
    return true;
  }
  if (action === "assistant-apply") { openModal("assistant-apply", ctx.data); return true; }
  if (action === "assistant-confirm" || action === "assistant-cancel") {
    const confirm = action === "assistant-confirm";
    await api.request(`${base}/assistant-requests/${id}/${confirm ? "confirm" : "cancel"}`,
      { method: "POST", ...(confirm ? { body: { input_digest: ctx.data.input_digest } } : {}) });
    toast(confirm ? "已提交，正在调用模型" : "请求已取消"); await load();
    return true;
  }
  return true;
}
