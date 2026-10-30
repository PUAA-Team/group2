import { badge, btn, date, e, options, pageHeader, pager, table, tag, toolbar } from "../components.js?v=stage13-3a";

export function renderUsers(ctx) {
  const groups = ctx.tab === "groups";
  const rows = (ctx.data.data || []).map(item => groups
    ? [e(item.name), tag(`${item.allow_actions.length} 项允许`), tag(`${item.deny_actions.length} 项禁用`), e(`GPU ${item.quota.gpu_count || 0} / 并发 ${item.quota.concurrent_jobs || 0}`), `<div class="live-row-actions">${btn("配置", "edit-group", item.id)}${btn("成员", "admin-group-members", item.id)}</div>`]
    : [e(item.display_name), e(item.account), tag(item.is_admin ? "管理员" : "成员"), e(ctx.groups.find(g => g.id === item.group_id)?.name || (item.group_id ? "受限用户组" : "未分组")), badge(item.active ? "启用" : "停用"), `<div class="live-row-actions">${btn("配置", "edit-user", item.id)}${btn("有效权限", "admin-user-access", item.id)}${btn("重置密码", "admin-reset-password", item.id)}${btn(item.active ? "停用" : "启用", "toggle-user", item.id)}</div>`]);
  const invite = ctx.generatedInvite ? `<div class="notice"><label for="invite-url">邀请链接（仅显示本次）</label><div class="heading-actions"><input id="invite-url" class="input" readonly value="${e(ctx.generatedInvite)}"/>${btn("复制", "admin-copy-invite")}${btn("关闭", "admin-hide-invite")}</div></div>` : "";
  const filters = groups ? "" : `<select class="select filter-select" data-query-filter="group_id" aria-label="用户组筛选">${options([["", "全部用户组"], ...ctx.groups.map(group => [group.id, group.name])], ctx.params?.get("group_id") || "")}</select><select class="select filter-select" data-query-filter="user_status" aria-label="用户状态">${options([["", "全部状态"], ["active", "启用"], ["disabled", "停用"]], ctx.params?.get("user_status") || "")}</select>`;
  return pageHeader("用户管理", "", (groups ? "" : btn("邀请注册", "modal", "invite-new")) + btn(groups ? "新增用户组" : "新增用户", "modal", groups ? "group-new" : "user-new", "primary")) + invite +
    `<div class="tabs"><a class="tab ${!groups ? "active" : ""}" href="#/admin/users">用户</a><a class="tab ${groups ? "active" : ""}" href="#/admin/users?tab=groups">用户组</a></div>` +
    toolbar(ctx.q, filters) + table(groups ? ["用户组", "基础授权", "显式禁用", "配额", "操作"] : ["用户", "账号", "角色", "用户组", "状态", "操作"], rows) + pager(ctx.data.pagination);
}

const actions = {
  "workspaces.create": "创建空间", "members.update": "调整空间成员", "models.create": "登记模型", "models.update": "修改模型",
  "model_versions.create": "登记模型版本", "datasets.create": "登记数据集", "datasets.update": "修改数据集", "dataset_versions.create": "导入数据版本",
};
export function renderAudit(ctx) {
  return pageHeader("操作记录", "", btn("刷新", "refresh")) + table(["时间", "操作", "操作者", "目标", "结果"], (ctx.data.data || []).map(item => [
    date(item.created_at), e(actions[item.action] || item.action), e(item.actor_id === ctx.session.user.id ? ctx.session.user.display_name : item.actor_id),
    `<span class="live-source" title="${e(item.target_id)}">${e(item.target_id)}</span>`, badge(item.result === "success" ? "已保存" : "失败"),
  ])) + pager(ctx.data.pagination);
}
