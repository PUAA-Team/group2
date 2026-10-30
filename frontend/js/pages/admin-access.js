import { badge, card, escapeHtml as e, pageHeader } from "../ui.js?v=console-4";

export function renderUsers(state, ui = {}) {
  const tab = ui.adminUsersTab || "users";
  const userRows = state.users.map(user => `<tr><td><strong>${e(user.name)}</strong></td><td>${e(user.account)}</td><td>${e(user.role)}</td><td>${e(state.groups.find(item => item.id === user.groupId)?.name || "—")}</td><td>${badge(user.status)}</td><td>${user.role === "管理员" ? "—" : `<button class="btn btn-secondary btn-small" data-action="open-modal" data-modal="user-access" data-id="${e(user.id)}">配置</button> <button class="btn btn-secondary btn-small" data-action="toggle-user" data-user-id="${e(user.id)}">${user.status === "启用" ? "停用" : "启用"}</button>`}</td></tr>`).join("");
  const groupRows = state.groups.map(item => `<tr><td><strong>${e(item.name)}</strong></td><td>${state.users.filter(user => user.groupId === item.id).length} 人</td><td>${item.permissions.length} 项</td><td>GPU ${item.quota.gpu} · 并发 ${item.quota.jobs}</td><td>${item.id === "group-admin" ? "—" : `<button class="btn btn-secondary btn-small" data-action="open-modal" data-modal="group-access" data-id="${e(item.id)}">配置</button>`}</td></tr>`).join("");
  const createAction = `<button class="btn btn-primary" data-action="open-modal" data-modal="${tab === "users" ? "user-new" : "group-new"}">新增${tab === "users" ? "用户" : "用户组"}</button>`;
  return `${pageHeader("用户管理", "", createAction)}
    <div class="tabs"><button class="tab ${tab === "users" ? "active" : ""}" data-action="admin-users-tab" data-tab="users">用户</button><button class="tab ${tab === "groups" ? "active" : ""}" data-action="admin-users-tab" data-tab="groups">用户组</button></div>
    ${tab === "users" ? card(`<div class="table-scroll"><table class="table"><thead><tr><th>用户</th><th>邮箱</th><th>角色</th><th>用户组</th><th>状态</th><th>操作</th></tr></thead><tbody>${userRows}</tbody></table></div>`) : card(`<div class="table-scroll"><table class="table"><thead><tr><th>用户组</th><th>成员</th><th>基础授权</th><th>配额</th><th>操作</th></tr></thead><tbody>${groupRows}</tbody></table></div>`)}`;
}
