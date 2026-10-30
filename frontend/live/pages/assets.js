import { badge, btn, can, date, e, fieldsInfo, link, pageHeader, pager, STATUS, table, tag, TASKS, toolbar, workspaceRequired } from "../components.js?v=stage13-3a";
import { renderAssetCatalog } from "../catalog.js?v=stage13-3a";

export function renderAssets(kind, ctx) {
  if (!ctx.path?.startsWith("/admin/")) return renderAssetCatalog(kind, ctx);
  const models = kind === "models";
  const title = models ? "模型仓库" : "数据集";
  const actions = can(ctx, `${kind}.write`) ? btn(models ? "新增模型" : "新增数据集", "modal", models ? "model-new" : "dataset-new", "primary", !ctx.workspace) : "";
  if (!ctx.workspace) return pageHeader(title) + workspaceRequired(ctx);
  const rows = (ctx.data.data || []).map(item => [link(item.name, `/${kind}/${item.id}`), tag(TASKS[item.task_type]),
    ...(models ? [e(ctx.templates.find(t => t.id === item.trainer_id)?.name || item.trainer_id), `<span class="live-source" title="${e(item.source_ref)}">${e(item.source_ref)}</span>`] : [tag("版本管理")]),
    date(item.created_at), can(ctx, `${kind}.write`) ? btn("编辑", "edit-asset", item.id) : "—"]);
  return pageHeader(title, "", actions) + toolbar(ctx.q) + table(models ? ["模型名称", "任务", "训练模板", "模型来源", "登记时间", "操作"] : ["数据集名称", "任务", "内容", "登记时间", "操作"], rows) + pager(ctx.data.pagination);
}

export function renderAssetDetail(kind, ctx) {
  const item = ctx.data.item;
  const models = kind === "models";
  const write = can(ctx, `${kind}.write`);
  const uploadSupported = true;
  const versions = ctx.data.versions?.data || [];
  const actions = write ? btn("编辑", "edit-asset", item.id) + (models ? btn("登记版本", "modal", "model-version", "primary") : `<a class="btn btn-primary" href="#/datasets/new?dataset=${e(item.id)}">导入版本</a>`) : "";
  const metadata = [["登记时间", e(date(item.created_at))]];
  if (models) metadata.push(["训练模板", e(ctx.templates.find(t => t.id === item.trainer_id)?.name || item.trainer_id)], ["模型来源", `<span class="live-break">${e(item.source_ref)}</span>`]);
  if (item.description) metadata.push(["说明", e(item.description)]);
  const rows = versions.map(version => models
    ? [tag(version.version), `<span class="live-break">${e(version.source_ref)}</span>`, badge(version.status === "available" ? "可训练" : "已登记"), date(version.created_at)]
    : [tag(`v${version.number}`), e(version.filename), e(version.format.toUpperCase()), e(version.sample_count), `${(version.size_bytes / 1024).toFixed(1)} KiB`, tag(({train:"训练集",validation:"验证集",test:"测试集"})[version.provenance?.partition] || ({annotation:"人工标注",clean:"数据清洗",augment:"数据增强"})[version.provenance?.operation] || "上传"), badge(STATUS[version.status] || version.status), `<div class="live-row-actions">${link("浏览样本", `/datasets/${item.id}/samples?version=${version.id}`)}<a class="entity-link" href="/api/v1/workspaces/${ctx.workspace.id}/dataset-versions/${version.id}/download">下载</a>${write ? btn("处理", "data-new-operation", `clean:${version.id}`) : ""}</div>`]);
  return `<div class="breadcrumb"><a href="#/${kind}">${models ? "模型仓库" : "数据集"}</a><span>/</span><span>${e(item.name)}</span></div>` +
    pageHeader(item.name, "", actions) + `<div class="live-detail-meta">${tag(TASKS[item.task_type])}</div>` +
    fieldsInfo(metadata) + `<div class="section-heading"><h2>历史版本</h2>${!models && uploadSupported ? btn("下载模板", "template", item.task_type) : ""}</div>` +
    table(models ? ["版本", "模型来源", "状态", "登记时间"] : ["版本", "文件", "格式", "样本数", "大小", "来源", "状态", "操作"], rows, "暂无版本") +
    (can(ctx, "training.write") && versions.length ? `<div class="heading-actions console-section-actions"><a class="btn btn-primary" href="#/train/new?${models ? "model_version" : "dataset_version"}=${e(versions.at(-1).id)}">新建训练</a></div>` : "") +
    pager(ctx.data.versions?.pagination) + (!models && ctx.data.preview ? renderPreview(ctx.data.preview) : "");
}

export function renderPreview(preview) {
  const keys = Object.keys(preview.samples[0] || {});
  return `<div class="section-heading" id="samples"><h2>样本预览</h2>${tag(`共 ${preview.total} 条`)}</div>` +
    table(keys, preview.samples.map(row => keys.map(key => `<div class="live-sample">${e(row[key])}</div>`)));
}
