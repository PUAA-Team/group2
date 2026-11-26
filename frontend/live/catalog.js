import { badge, btn, can, card, date, e, link, options, pageHeader, pager, raw, select, STATUS, table, tag, TASKS, toolbar, workspaceRequired } from "./components.js?v=stage20a-2";

export const CATEGORY = { all: "全部模型", prebuilt: "预置模型", network: "基础网络", trained: "训练产物" };
export function taskFilter(ctx) {
  return `<select class="select filter-select" data-query-filter="task_type" aria-label="任务类型">${options([["", "全部任务"], ...Object.entries(TASKS)], ctx.params?.get("task_type") || "")}</select>`;
}

export function archiveFilter(ctx) {
  return `<select class="select filter-select" data-query-filter="status" aria-label="归档状态">${options([['', '全部状态'], ['active', '未归档'], ['archived', '已归档']], ctx.params?.get('status') || '')}</select>`;
}

export function renderAssetCatalog(kind, ctx) {
  const models = kind === "models", title = models ? "模型仓库" : "数据集";
  if (!ctx.workspace) return pageHeader(title) + workspaceRequired(ctx);
  const write = can(ctx, `${kind}.write`), items = ctx.data.data || [];
  const add = write ? models ? btn("新增模型", "modal", "model-new", "primary") : '<a class="btn btn-primary" href="#/datasets/new">导入数据集</a>' : "";
  const category = ctx.params?.get("category") || "all", list = ctx.params?.get("view") === "list";
  const params = new URLSearchParams(ctx.params || []);
  const mode = value => { const next = new URLSearchParams(params); next.set("view", value); return `#/models?${next}`; };
  const tabs = models ? `<div class="tabs">${Object.entries(CATEGORY).map(([key, text]) => {
    const next = new URLSearchParams(params); next.set("category", key); next.delete("page");
    return `<a class="tab ${category === key ? "active" : ""}" href="#/models?${next}">${text}</a>`;
  }).join("")}</div>` : "";
  const view = models ? `<div class="console-view-toggle"><a class="btn ${list ? "btn-secondary" : "btn-primary"}" aria-label="卡片视图" href="${e(mode("cards"))}">卡片</a><a class="btn ${list ? "btn-primary" : "btn-secondary"}" aria-label="列表视图" href="${e(mode("list"))}">列表</a></div>` : "";
  let body;
  if (models && !list) body = items.length ? `<div class="catalog-grid console-catalog">${items.map(item => {
    const version = item.latest_version;
    return card(`<div class="catalog-top">${tag(TASKS[item.task_type])}${tag(CATEGORY[item.category] || "已登记")}</div><h3>${link(item.name, `/models/${item.id}`)}</h3><div class="console-card-fields"><span>版本</span><strong>${e(version?.version || "未登记")}</strong><span>训练器</span><span>${e(ctx.templates.find(t => t.id === item.trainer_id)?.name || item.trainer_id)}</span><span>模型来源</span><span class="live-source" title="${e(version?.source_ref || item.source_ref)}">${e(version?.source_ref || item.source_ref)}</span></div><div class="project-foot"><a class="entity-link" href="#/models/${e(item.id)}">查看详情</a><div class="live-row-actions">${write ? btn("编辑", "edit-asset", item.id) : ""}${version && !item.archived && can(ctx, "training.write") && version.source_ref ? `<a class="btn btn-secondary" href="#/train/new?model_version=${e(version.id)}">训练</a>` : ""}</div></div>`, "catalog-card console-entity-card");
  }).join("")}</div>` : table([], []);
  else body = table(models ? ["模型名称", "任务", "分类", "版本", "训练器", "模型来源", "操作"] : ["数据集名称", "任务", "版本", "样本数", "格式", "状态", "更新时间"], items.map(item => {
    const version = item.latest_version;
    return models ? [raw(link(item.name, `/models/${item.id}`)), raw(tag(TASKS[item.task_type])), raw(tag(CATEGORY[item.category] || "已登记")), version?.version || "—", ctx.templates.find(t => t.id === item.trainer_id)?.name || item.trainer_id, raw(`<span class="live-source">${e(version?.source_ref || item.source_ref)}</span>`), write ? raw(btn("编辑", "edit-asset", item.id)) : "—"]
      : [raw(link(item.name, `/datasets/${item.id}`)), raw(tag(TASKS[item.task_type])), version ? raw(tag(`v${version.number}`)) : "—", version?.sample_count ?? "—", raw(tag(version?.format.toUpperCase() || "—")), raw(badge(STATUS[version?.status] || "已登记")), date(version?.created_at || item.created_at)];
  }));
  const versionFilter = models ? '' : `<select class="select filter-select" data-query-filter="version_status" aria-label="数据状态">${options([['', '全部数据'], ['available', '可训练'], ['needs_annotation', '待标注'], ['unversioned', '无版本']], ctx.params?.get('version_status') || '')}</select>`;
  return pageHeader(title, "", add) + tabs + toolbar(ctx.q, taskFilter(ctx) + archiveFilter(ctx) + versionFilter + view, models ? "搜索模型" : "搜索数据集") + body + pager(ctx.data.pagination);
}

export function renderProjectCatalog(ctx) {
  const actions = can(ctx, "training.write") ? btn("新建项目", "modal", "project-new", "primary") : "";
  const items = ctx.data.data || [];
  const cards = items.map(item => card(`<div class="catalog-top">${tag(`${item.job_count ?? 0} 次训练`)}${item.archived ? badge('已归档') : ''}${item.active_count ? tag(`${item.active_count} 个活跃任务`) : ""}</div><h3>${link(item.name, `/projects/${item.id}`)}</h3><div class="console-card-fields"><span>最近任务</span><span>${item.latest_job ? link(item.latest_job.name, `/runs/${item.latest_job.id}`) : "—"}</span><span>最佳准确率</span><strong>${item.best_accuracy == null ? "—" : `${(item.best_accuracy * 100).toFixed(1)}%`}</strong><span>创建时间</span><span>${date(item.created_at)}</span></div><div class="project-foot"><a class="entity-link" href="#/runs?project=${e(item.id)}">查看实验</a>${can(ctx, "training.write") && !item.archived ? `<a class="btn btn-secondary" href="#/train/new?project=${e(item.id)}">新建训练</a>` : ""}</div>`, "catalog-card console-entity-card")).join("");
  return pageHeader("训练项目", "", actions) + toolbar(ctx.q, archiveFilter(ctx), "搜索项目") + (cards ? `<div class="catalog-grid console-catalog">${cards}</div>` : table([], [])) + pager(ctx.data.pagination);
}
