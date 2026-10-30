import { ADMIN_NAV, badge, card, escapeHtml as e, icon, NAV_GROUPS, pageHeader } from "../js/ui.js?v=console-4";
export { badge, card, e, icon, pageHeader };
export const pageTitle = path => [...NAV_GROUPS.flatMap(group => group.children), ...ADMIN_NAV].find(([, href]) => path === href || path.startsWith(`${href}/`))?.[0] || "工作空间";

export const TASKS = { text_classification: "文本分类", image_classification: "图像分类", llm_sft: "指令微调" };
export const ACTIONS = [
  ["workspaces.create", "创建空间"], ["members.manage", "管理成员"], ["models.read", "查看模型"],
  ["models.write", "维护模型"], ["datasets.read", "查看数据"], ["datasets.write", "维护数据"],
  ["audit.read", "查看审计"], ["users.manage", "管理用户"], ["groups.manage", "管理用户组"],
  ["resources.read", "查看资源"], ["resources.manage", "管理资源"],
  ["training.read", "查看训练"], ["training.write", "管理训练"], ["services.read", "查看服务"], ["services.write", "管理服务"], ["services.invoke", "调用服务"],
  ["settings.manage", "管理系统设置"], ["assistants.use", "使用智能辅助"],
];
export const QUOTAS = [["gpu_count", "GPU 数量"], ["concurrent_jobs", "并发任务"], ["storage_gib", "存储 GiB"]];
export const STATUS = { registered: "已登记", available: "可训练", needs_annotation: "待标注" };
export const date = value => value ? new Date(value).toLocaleString("zh-CN", { hour12: false }) : "—";
export const btn = (text, action, value = "", kind = "secondary", disabled = false) => `<button type="button" class="btn btn-${kind}" data-action="${e(action)}" data-id="${e(value)}" ${disabled ? "disabled" : ""}>${e(text)}</button>`;
export const tag = text => `<span class="chip">${e(text)}</span>`;
export const link = (name, href) => `<a class="row-link" href="#${e(href)}">${e(name)}</a>`;
export const options = (items, selected = "") => items.map(([value, label]) => `<option value="${e(value)}" ${String(selected) === String(value) ? "selected" : ""}>${e(label)}</option>`).join("");
export const taskOptions = selected => options(Object.entries(TASKS), selected);
export const input = (label, name, value = "", attrs = "") => `<div class="field"><label for="live-${e(name)}">${e(label)}</label><input id="live-${e(name)}" class="input" name="${e(name)}" value="${e(value)}" ${attrs} /></div>`;
export const select = (label, name, content, attrs = "") => `<div class="field"><label for="live-${e(name)}">${e(label)}</label><select id="live-${e(name)}" class="select" name="${e(name)}" ${attrs}>${content}</select></div>`;
export const description = value => `<div class="field"><label for="live-description">说明</label><textarea id="live-description" class="textarea" name="description" rows="3" maxlength="2000">${e(value || "")}</textarea></div>`;
export function table(headings, rows, empty = "暂无记录") {
  return rows.length ? card(`<div class="table-scroll"><table class="table"><thead><tr>${headings.map(head => `<th>${e(head)}</th>`).join("")}</tr></thead><tbody>${rows.map(cells => `<tr>${cells.map(cell => `<td>${cell}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`, "live-table")
    : `<div class="empty-state"><div class="empty-icon">${icon("data", 24)}</div><h3>${e(empty)}</h3></div>`;
}
export function pager(pagination, unit = "条") {
  if (!pagination) return "";
  const { total, page, page_size: size } = pagination;
  return `<div class="live-pager"><span>共 ${total} ${e(unit)}</span>${btn("上一页", "page", page - 1, "secondary", page <= 1)}<span>${page} / ${Math.max(1, Math.ceil(total / size))}</span>${btn("下一页", "page", page + 1, "secondary", page * size >= total)}</div>`;
}
export function toolbar(q = "", extra = "", placeholder = "搜索名称或账号") {
  return `<div class="toolbar"><form class="toolbar-left live-search" data-form="search"><div class="search-field">${icon("search", 16)}<input class="input" name="q" type="search" maxlength="100" aria-label="${e(placeholder)}" placeholder="${e(placeholder)}" value="${e(q)}" /></div><button class="btn btn-secondary" type="submit">搜索</button>${q ? btn("清空", "clear-search") : ""}</form><div class="heading-actions">${extra}${btn("刷新", "refresh")}</div></div>`;
}
export function fieldsInfo(values) {
  return `<dl class="info-list live-info">${values.map(([key, value]) => `<div><dt>${e(key)}</dt><dd>${value}</dd></div>`).join("")}</dl>`;
}
export const can = (ctx, action) => (ctx.access?.actions || []).includes(action);
export function workspaceRequired(ctx) {
  return `<div class="empty-state"><h3>请选择工作空间</h3>${ctx.session.access.actions.includes("workspaces.create") ? btn("创建工作空间", "modal", "workspace-new", "primary") : ""}</div>`;
}
