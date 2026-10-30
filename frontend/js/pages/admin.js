import { badge, card, escapeHtml as e, pageHeader } from "../ui.js?v=console-4";
export { renderResources } from "./admin-resources.js?v=console-4";
export { renderUsers } from "./admin-access.js?v=console-4";

export function renderAudit(state) {
  const rows = state.audit.map(item => `<tr><td class="nowrap">${e(item.time)}</td><td>${e(item.actor)}</td><td>${e(item.action)}</td><td>${e(item.target)}</td><td>${badge(item.result === "成功" ? "已完成" : "失败")}</td></tr>`).join("");
  return `${pageHeader("操作记录", "查看训练、数据与服务的关键操作")}${card(`<div class="table-scroll"><table class="table"><thead><tr><th>时间</th><th>操作者</th><th>操作</th><th>对象</th><th>结果</th></tr></thead><tbody>${rows}</tbody></table></div>`)}`;
}
