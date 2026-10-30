import { badge, btn, can, date, e, fieldsInfo, input, link, options, pageHeader, pager, select, table, tag, TASKS, toolbar, workspaceRequired } from "./components.js?v=stage13-3a";
import { renderAnnotation } from "./annotation-view.js?v=stage13-3a";

export const DATA_STATES = { open: "进行中", draft: "草稿", submitted: "待审核", approved: "已通过", rejected: "已退回", queued: "排队中", running: "运行中", review: "待发布", published: "已发布", failed: "失败", cancelled: "已取消" };
export const DATA_KINDS = { clean: "数据清洗", split: "数据划分", augment: "数据增强" };
export const PARTITIONS = { train: "训练集", validation: "验证集", test: "测试集" };
export const isDataPage = path => ["/annotation", "/augmentation", "/data-operations"].includes(path) || /^\/(annotation|data-operations)\/[^/]+$/.test(path) || /^\/datasets\/[^/]+\/samples$/.test(path);
export const versionOptions = (ctx, chosen = "") => options((ctx.dataChoices?.versions || []).map(version => [version.id, `${version.name} · v${version.number} · ${TASKS[version.task_type]}`]), chosen);

export async function loadDataWorkflow(api, ctx, signal) {
  if (!ctx.workspace) return {};
  const base = `/workspaces/${ctx.workspace.id}`;
  const query = `page=${ctx.page}&page_size=20&q=${encodeURIComponent(ctx.q)}`;
  const batchId = ctx.path.match(/^\/annotation\/([^/]+)$/)?.[1];
  const operationId = ctx.path.match(/^\/data-operations\/([^/]+)$/)?.[1];
  const datasetId = ctx.path.match(/^\/datasets\/([^/]+)\/samples$/)?.[1];
  if (batchId) return (await api.request(`${base}/annotation-batches/${encodeURIComponent(batchId)}?${query}`, { signal })).data;
  if (datasetId) {
    const [item, versions] = await Promise.all([api.request(`${base}/datasets/${datasetId}`, { signal }), api.all(`${base}/datasets/${datasetId}/versions`, signal)]);
    const version = versions.find(value => value.id === ctx.params.get("version")) || versions.at(-1);
    const samples = version ? (await api.request(`${base}/dataset-versions/${version.id}/samples?${query}`, { signal })).data : null;
    return { item: item.data, versions, version, samples };
  }
  if (operationId) {
    const item = (await api.request(`${base}/data-operations/${encodeURIComponent(operationId)}`, { signal })).data;
    const candidate = Math.max(0, Number(ctx.params.get("candidate")) || 0);
    const preview = ["review", "published"].includes(item.status) && item.candidates.length ? (await api.request(`${base}/data-operations/${item.id}/preview?candidate=${candidate}&${query}`, { signal })).data : null;
    return { item, preview, candidate };
  }
  const kind = ctx.path === "/annotation" ? "annotation-batches" : "data-operations";
  const filter = ctx.path === "/augmentation" ? "augment" : ctx.params.get("kind") || "";
  return api.request(`${base}/${kind}?${query}${kind === "data-operations" ? `&kind=${encodeURIComponent(filter)}` : ""}`, { signal });
}

export function renderSampleTable(ctx, data, taskType, imageBase) {
  if (!data) return "";
  const rows = data.samples.map(row => [tag(row.index + 1), ...(taskType === "image_classification" ? [`<img class="data-thumbnail" src="${e(imageBase(row.index))}" alt="样本${row.index + 1}" loading="lazy"/>`, e(row.filename), tag(row.label || "未标注")] : taskType === "llm_sft" ? [e(row.instruction), `<div class="data-sample-text">${e(row.input)}</div>`, `<div class="data-sample-text">${e(row.output)}</div>`] : [`<div class="data-sample-text">${e(row.text)}</div>`, tag(row.label || "未标注")])]);
  return table(taskType === "image_classification" ? ["序号", "图片", "文件", "标签"] : taskType === "llm_sft" ? ["序号", "指令", "输入", "输出"] : ["序号", "文本", "标签"], rows) + pager({ page: data.page, page_size: data.page_size, total: data.total });
}

function samplesPage(ctx) {
  const { item, versions, version, samples } = ctx.data;
  const base = `/api/v1/workspaces/${ctx.workspace.id}/dataset-versions/${version?.id}`;
  return `<div class="breadcrumb">${link("数据集", "/datasets")}/ ${link(item.name, `/datasets/${item.id}`)} / 样本</div>` + pageHeader(item.name, "", version ? `<a class="btn btn-secondary" href="${base}/download">下载版本</a>${can(ctx, "datasets.write") ? btn("新建标注", "data-new-annotation", version.id, "primary") : ""}` : "") +
    `<div class="toolbar"><select class="select" data-query-filter="version" aria-label="数据版本">${options(versions.map(value => [value.id, `v${value.number} · ${value.filename}`]), version?.id)}</select><div class="heading-actions">${tag(TASKS[item.task_type])}${version?.provenance.partition ? tag(PARTITIONS[version.provenance.partition]) : ""}${Object.entries(samples?.labels || {}).map(([label, count]) => tag(`${label} ${count}`)).join("")}</div></div>` + renderSampleTable(ctx, samples, item.task_type, index => `${base}/images/${index}`);
}

function operationDetail(ctx) {
  const { item, preview, candidate } = ctx.data;
  const base = `/api/v1/workspaces/${ctx.workspace.id}/data-operations/${item.id}`;
  const write = can(ctx, "datasets.write");
  const actions = btn("刷新", "refresh") + (write && ["queued", "running", "review"].includes(item.status) ? btn("取消任务", "data-confirm-cancel", item.id) : "") + (write && item.status === "review" ? btn("发布版本", "data-confirm-publish", item.id, "primary") : "");
  const choices = item.candidates.map((value, index) => [index, `${PARTITIONS[value.partition] || DATA_KINDS[item.kind]} · ${value.sample_count} 条`]);
  return `<div class="breadcrumb">${link(DATA_KINDS[item.kind], item.kind === "augment" ? "/augmentation" : "/data-operations")} / ${e(item.name)}</div>` + pageHeader(item.name, "", actions) +
    `<div class="live-detail-meta">${tag(DATA_KINDS[item.kind])}${badge(DATA_STATES[item.status])}</div>` + fieldsInfo([["源数据", link(`${item.dataset_name} · v${item.version_number}`, `/datasets/${item.dataset_id}/samples?version=${item.version_id}`)], ["随机种子", e(item.options.seed)], ["处理进度", `${e(item.progress.phase || "等待处理")} ${item.progress.total ? `${item.progress.done}/${item.progress.total}` : ""}`], ["创建时间", e(date(item.created_at))]]) +
    (item.error ? `<div class="notice notice-danger" role="alert">${e(item.error)}</div>` : "") +
    (item.status === "published" ? `<div class="section-heading"><h2>已发布版本</h2><div class="heading-actions">${item.output_version_ids.map((id, index) => link(PARTITIONS[item.candidates[index]?.partition] || "查看样本", `/datasets/${item.dataset_id}/samples?version=${id}`)).join("")}</div></div>` : "") +
    (preview ? `<div class="section-heading data-candidate-heading"><h2>结果预览</h2><select class="select" data-query-filter="candidate" aria-label="候选分区">${options(choices, candidate)}</select></div>${renderSampleTable(ctx, preview, item.task_type, index => `${base}/images/${index}?candidate=${candidate}`)}` : "");
}

export function renderDataWorkflow(ctx) {
  if (!ctx.workspace) return pageHeader("数据管理") + workspaceRequired(ctx);
  if (/^\/datasets\/[^/]+\/samples$/.test(ctx.path)) return samplesPage(ctx);
  if (ctx.path.startsWith("/annotation/")) return renderAnnotation(ctx);
  if (ctx.path.startsWith("/data-operations/")) return operationDetail(ctx);
  const annotation = ctx.path === "/annotation", augment = ctx.path === "/augmentation";
  const actions = can(ctx, "datasets.write") ? btn(annotation ? "新建标注" : augment ? "新建增强" : "新建处理", annotation ? "data-new-annotation" : "data-new-operation", annotation ? "" : augment ? "augment" : "clean", "primary") : "";
  const rows = (ctx.data.data || []).map(item => annotation ? [link(item.name, `/annotation/${item.id}`), e(item.dataset_name), tag(`v${item.version_number}`), tag(TASKS[item.task_type]), badge(DATA_STATES[item.status]), `${item.counts.approved || 0}/${item.counts.total}`, date(item.created_at)] : [link(item.name, `/data-operations/${item.id}`), tag(DATA_KINDS[item.kind]), e(item.dataset_name), tag(`v${item.version_number}`), badge(DATA_STATES[item.status]), item.progress.total ? `${item.progress.done}/${item.progress.total}` : "—", date(item.created_at)]);
  const filter = !annotation && !augment ? `<select class="select" data-query-filter="kind" aria-label="处理类型">${options([["", "全部类型"], ...Object.entries(DATA_KINDS)], ctx.params.get("kind"))}</select>` : "";
  return pageHeader(annotation ? "在线标注" : augment ? "数据增强" : "数据处理", "", actions) + toolbar(ctx.q, filter, "搜索任务名称") + table(annotation ? ["标注批次", "数据集", "版本", "任务", "状态", "已审核", "创建时间"] : ["处理任务", "类型", "数据集", "版本", "状态", "已处理", "创建时间"], rows) + pager(ctx.data.pagination);
}

export function dataDialog(modal, ctx) {
  const item = modal.item || {};
  if (modal.kind === "data-annotation-new") return { title: "新建标注批次", fields: input("批次名称", "name", "", 'required maxlength="100"') + select("数据版本", "version_id", versionOptions(ctx, item.version_id), "required") + `<div class="field"><label for="annotation-labels">标签集合</label><textarea id="annotation-labels" class="textarea" name="labels" rows="3" placeholder="分类数据每行一个标签；指令数据可留空">${e((item.labels || []).join("\n"))}</textarea></div>` + `<div class="live-field-grid">${input("样本数量", "limit", 100, 'required type="number" min="1" max="10000"')}${select("分配成员", "assigned_to", options([["", "共同编辑"], ...(ctx.dataChoices?.members || []).map(member => [member.id, member.name])]))}</div>`, submit: "创建" };
  if (modal.kind === "data-operation-new") return { title: "新建数据处理", fields: input("任务名称", "name", "", 'required maxlength="100"') + select("数据版本", "version_id", versionOptions(ctx, item.version_id), "required data-processing-version") + select("处理类型", "kind", options(Object.entries(DATA_KINDS), item.kind || "clean"), "data-processing-kind") + input("随机种子", "seed", 42, 'required type="number" min="0" max="2147483647"') +
    `<fieldset class="live-check-field" data-processing-section="clean" ${item.kind && item.kind !== "clean" ? "hidden" : ""}><legend>清洗规则</legend><div class="live-checks">${[["deduplicate", "去除重复样本"], ["trim", "去除首尾空白"], ["drop_unlabeled", "过滤未标注样本"]].map(([key, label]) => `<label><input type="checkbox" name="${key}" ${key !== "drop_unlabeled" ? "checked" : ""}/>${label}</label>`).join("")}</div><div class="field"><label for="label-map">标签映射</label><textarea id="label-map" class="textarea" name="label_map" rows="2" placeholder="旧标签=新标签，每行一组"></textarea></div></fieldset>` +
    `<div class="live-field-grid" data-processing-section="split" ${item.kind !== "split" ? "hidden" : ""}>${input("训练集比例", "train_ratio", 0.8, 'type="number" min="0.1" max="0.9" step="0.05"')}${input("验证集比例", "validation_ratio", 0.1, 'type="number" min="0.05" max="0.4" step="0.05"')}</div>` +
    `<fieldset class="live-check-field" data-processing-section="augment" ${item.kind !== "augment" ? "hidden" : ""}><legend>增强方法</legend><div class="live-checks">${[["flip", "水平翻转"], ["brightness", "亮度变化"], ["noise", "轻量噪声"], ["punctuation", "文本标点变体"]].map(([key, label]) => `<label data-augment-method="${key}"><input type="checkbox" name="methods" value="${key}"/>${label}</label>`).join("")}</div></fieldset>`, submit: "创建任务" };
  if (["data-publish", "annotation-publish", "data-cancel"].includes(modal.kind)) return { title: modal.kind === "data-cancel" ? "取消数据处理" : "发布数据版本", fields: fieldsInfo([["任务", e(item.name)], ["状态", tag(DATA_STATES[item.status])]]), submit: modal.kind === "data-cancel" ? "确认取消" : "确认发布" };
  return null;
}
