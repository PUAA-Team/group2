import { badge, btn, date, e, graceDaysSelected, options, pageHeader, pager, raw, table, tag, toolbar } from "../components.js?v=stage29-1";
import { formatSize } from "./assets.js?v=stage29-1";

export function renderUsers(ctx) {
  const groups = ctx.tab === "groups";
  const rows = (ctx.data.data || []).map(item => groups
    ? [item.name, raw(tag(`${item.allow_actions.length} 项允许`)), raw(tag(`${item.deny_actions.length} 项禁用`)), `GPU ${item.quota.gpu_count || 0} / 并发 ${item.quota.concurrent_jobs || 0}`, raw(`<div class="live-row-actions">${btn("配置", "edit-group", item.id)}${btn("成员", "admin-group-members", item.id)}${btn('共享预算', 'gov-group-budget', item.id)}</div>`)]
    : [raw(`<div><strong>${e(item.display_name)}</strong><span class="secondary">${e(item.account)}</span></div>`), raw(tag(item.is_admin ? "管理员" : "成员")), ctx.groups.find(g => g.id === item.group_id)?.name || (item.group_id ? "受限用户组" : "未分组"), raw(badge(item.active ? "启用" : "停用")), raw(`<div class="live-row-actions">${btn("配置", "edit-user", item.id)}${btn("有效权限", "admin-user-access", item.id)}${btn("重置密码", "admin-reset-password", item.id)}${btn("生成重置码", "admin-issue-reset-code", item.id)}${btn(item.active ? "停用" : "启用", "toggle-user", item.id)}</div>`)]);
  const invite = ctx.generatedInvite ? `<div class="notice"><label for="invite-url">邀请链接（仅显示本次）</label><div class="heading-actions"><input id="invite-url" class="input" readonly value="${e(ctx.generatedInvite)}"/>${btn("复制", "admin-copy-invite")}${btn("关闭", "admin-hide-invite")}</div></div>` : "";
  const resetCode = ctx.generatedResetCode ? `<div class="notice"><label for="reset-code">重置码（仅显示本次，15 分钟内有效）：${e(ctx.generatedResetCode.account)}</label><div class="heading-actions"><input id="reset-code" class="input" readonly value="${e(ctx.generatedResetCode.code)}"/>${btn("复制", "admin-copy-reset-code")}${btn("关闭", "admin-hide-reset-code")}</div></div>` : "";
  const filtered = ctx.q || ["group_id", "user_status"].some(key => ctx.params?.get(key));
  const filters = groups ? "" : `<select class="select filter-select" data-query-filter="group_id" aria-label="用户组筛选">${options([["", "全部用户组"], ...ctx.groups.map(group => [group.id, group.name])], ctx.params?.get("group_id") || "")}</select><select class="select filter-select" data-query-filter="user_status" aria-label="用户状态">${options([["", "全部状态"], ["active", "启用"], ["disabled", "停用"]], ctx.params?.get("user_status") || "")}</select>`;
  const invitationStatusLabels = { active: "未使用", used: "已使用", expired_grace: "已过期（宽限期内）", expired: "已过期（待清理）", revoked: "已撤销" };
  // 邀请列表宽限期展示与清理口径对齐（stage 28-2，27-3 残留）：选择宽限期后
  // 经 data-query-filter 写入 URL 的 grace_days，加载时透传到列表请求。
  // 29-1：回显以后端接口返回的 grace_days 为准（ctx.invitationsGraceDays），
  // 与 URL 不一致时以接口返回为准，未返回时回落到 URL 参数。
  const graceFilter = `<select class="select filter-select" data-query-filter="grace_days" aria-label="过期宽限期">${options([["", "默认宽限期（7 天）"], ["0", "无宽限期（0 天）"], ["30", "宽限期 30 天"]], graceDaysSelected(ctx.invitationsGraceDays, ctx.params?.get("grace_days") || ""))}</select>`;
  const invitationSection = groups ? "" : `<div class="section-heading"><h2>注册邀请</h2>${graceFilter}</div>` + table(["工作空间", "角色", "状态", "使用人", "过期时间", "操作"], (ctx.invitations || []).map(item => [
    item.workspace_name || "—", raw(tag(item.role === "viewer" ? "查看者" : "编辑者")), raw(badge(invitationStatusLabels[item.status] || "未使用")),
    item.used_by_account || "—", date(item.expires_at),
    item.status === "active" ? raw(btn("撤销", "admin-revoke-invitation", item.id)) : "—",
  ]), "暂无注册邀请");
  return pageHeader("用户管理", "", (groups ? "" : btn("邀请注册", "modal", "invite-new")) + btn(groups ? "新增用户组" : "新增用户", "modal", groups ? "group-new" : "user-new", "primary")) + invite + resetCode +
    `<div class="tabs"><a class="tab ${!groups ? "active" : ""}" href="#/admin/users">用户</a><a class="tab ${groups ? "active" : ""}" href="#/admin/users?tab=groups">用户组</a></div>` +
    toolbar(ctx.q, filters) + table(groups ? ["用户组", "基础授权", "显式禁用", "配额", "操作"] : ["用户", "角色", "用户组", "状态", "操作"], rows, filtered ? (groups ? "没有符合筛选条件的用户组" : "没有符合筛选条件的用户") : (groups ? "暂无用户组" : "暂无用户")) + pager(ctx.data.pagination) + invitationSection;
}

export function renderSessions(ctx) {
  const items = ctx.data.data || [];
  const current = items.find(item => item.current);
  const stats = `<section class="live-stat-strip">${[["在线会话", String(items.length)], ["当前会话", current ? `${current.user_display_name}（${current.user_account}）` : "—"]].map(([label, value]) => `<div><span>${label}</span><strong>${e(value)}</strong></div>`).join("")}</section>`;
  const rows = items.map(item => [
    raw(`<div><strong>${e(item.user_display_name)}</strong><span class="secondary">${e(item.user_account)}</span></div>`),
    date(item.created_at),
    date(item.last_active_at),
    date(item.expires_at),
    raw(item.client_ip || item.client_agent
      ? `<div>${e(item.client_ip || "—")}</div>${item.client_agent ? `<span class="secondary live-source" title="${e(item.client_agent)}">${e(item.client_agent)}</span>` : ""}`
      : "—"),
    item.current ? raw(tag("当前会话")) : raw(badge("在线")),
    item.current ? "—" : raw(btn("踢出", "admin-revoke-session", item.id)),
  ]);
  // 按用户筛选与按账号/姓名搜索（stage 25-2，27-2 改按输入搜索加载）：
  // 用户下拉只放与 user_q 匹配的第一页（20 条），已选中的用户置顶
  // 回显；匹配超出 20 条时提示继续输入缩小范围。user_id 与 q 一起
  // 经 URL 参数透传到 /admin/sessions 请求；带筛选时空态区分。
  const filtered = ctx.q || ctx.params?.get("user_id");
  const user_q = ctx.params?.get("user_q") || "";
  const selectedId = ctx.params?.get("user_id") || "";
  const selected = ctx.selectedSessionUser;
  const shown = [...(ctx.sessionUsers || [])];
  if (selected && !shown.some(user => user.id === selected.id)) shown.unshift(selected);
  const filters = `<input class="input" data-query-filter="user_q" aria-label="搜索用户" placeholder="输入账号或姓名筛选用户" value="${e(user_q)}"/>` +
    `<select class="select filter-select" data-query-filter="user_id" aria-label="用户筛选">${options([["", "全部用户"], ...shown.map(user => [user.id, `${user.display_name}（${user.account}）`])], selectedId)}</select>` +
    ((ctx.sessionUsersTotal || 0) > (ctx.sessionUsers || []).length ? `<span class="secondary">仅显示前 ${(ctx.sessionUsers || []).length} 个匹配用户，继续输入可缩小范围</span>` : "");
  return pageHeader("会话管理", "", btn("刷新", "refresh")) + stats + toolbar(ctx.q, filters, "搜索用户账号或姓名") +
    table(["用户", "登录时间", "最后活跃", "过期时间", "客户端", "状态", "操作"], rows, filtered ? "没有符合筛选条件的会话" : "暂无在线会话") + pager(ctx.data.pagination);
}

export function renderStorageReconcile(ctx) {
  // 存储对账管理页（stage 25-5，24-1 残留）：管理端调用已有
  // POST /admin/workspaces/{id}/storage/reconcile 接口；进页即自动
  // dry_run 预览孤儿文件，确认清理走二次确认弹窗（必填勾选）。
  const spaces = ctx.workspaces || [];
  const selectedId = ctx.workspace?.id || "";
  const selected = spaces.find(space => space.id === selectedId);
  const result = ctx.storageReconcile || null;
  if (!spaces.length) return pageHeader("存储对账", "", btn("刷新", "refresh")) + '<div class="empty-state">暂无工作空间</div>';
  const filters = `<select class="select filter-select" data-query-filter="workspace" aria-label="工作空间选择">${options(spaces.map(space => [space.id, space.name]), selectedId)}</select>`;
  const stats = result ? `<section class="live-stat-strip">${[["孤儿文件", String(result.orphan_count)], ["孤儿占用空间", formatSize(result.orphan_size_bytes)], ["缺失记账", String(result.missing_count)], ["跳过暂存文件", String((result.skipped || []).length)]].map(([label, value]) => `<div><span>${label}</span><strong>${e(value)}</strong></div>`).join("")}</section>` : "";
  if (!result) return pageHeader("存储对账", "", btn("刷新", "refresh")) + `<div class="toolbar">${filters}</div>` + '<div class="empty-state">正在对账…</div>';
  // 孤儿列表分页（stage 28-4）：后端已按每页 100 条返回当前页，
  // 本页直接渲染；翻页走通用 pager（page 参数即孤儿页码）。
  const shown = result.orphans || [];
  const orphanRows = shown.map(item => [raw(`<span class="live-source" title="${e(item.storage_key)}">${e(item.storage_key)}</span>`), formatSize(item.size_bytes)]);
  const orphanPager = result.orphan_count > 0 ? pager({ total: result.orphan_count, page: ctx.page || 1, page_size: 100 }, "个") : "";
  const missing = result.missing || [];
  const missingSection = missing.length ? `<div class="section-heading"><h2>缺失记账（仅报告，不处理）</h2></div>` +
    table(["记账文件"], missing.slice(0, 20).map(key => [raw(`<span class="live-source" title="${e(key)}">${e(key)}</span>`)]), "暂无缺失记账") +
    (missing.length > 20 ? `<div class="notice">仅显示前 20 条，共 ${missing.length} 条。</div>` : "") : "";
  const skippedNote = (result.skipped || []).length ? `<div class="notice">进行中的上传暂存文件 ${result.skipped.length} 个，已跳过（不清理）；中断上传残留仍由工作空间删除兜底清理。</div>` : "";
  const cleanup = result.orphan_count > 0 ? btn("确认清理", "admin-reconcile-storage", selectedId, "primary") : "";
  return pageHeader("存储对账", "", btn("刷新", "refresh")) + `<div class="toolbar">${filters}</div>` + stats +
    `<div class="section-heading"><h2>孤儿文件${selected ? ` · ${e(selected.name)}` : ""}</h2>${cleanup}</div>` +
    table(["文件", "大小"], orphanRows, "暂无孤儿文件") + orphanPager + missingSection + skippedNote;
}

const actions = {
  "workspaces.create": "创建空间", "members.update": "调整空间成员", "models.create": "登记模型", "models.update": "修改模型",
  "model_versions.create": "登记模型版本", "datasets.create": "登记数据集", "datasets.update": "修改数据集", "dataset_versions.create": "导入数据版本",
};
export function renderAudit(ctx) {
  return pageHeader("操作记录", "", btn("刷新", "refresh")) + table(["时间", "操作", "操作者", "目标", "结果"], (ctx.data.data || []).map(item => [
    date(item.created_at), actions[item.action] || item.action, item.actor_id === ctx.session.user.id ? ctx.session.user.display_name : item.actor_id,
    raw(`<span class="live-source" title="${e(item.target_id)}">${e(item.target_id)}</span>`), raw(badge(item.result === "success" ? "已保存" : "失败")),
  ]), "暂无操作记录") + pager(ctx.data.pagination);
}
