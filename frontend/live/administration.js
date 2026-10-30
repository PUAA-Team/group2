import { ACTIONS, badge, btn, can, card, date, e, fieldsInfo, input, link, options, pageHeader, pager, QUOTAS, select, table, tag, TASKS, toolbar } from "./components.js?v=stage13-3a";
import { actionLabel } from "./labels.js?v=stage13-3a";

const catalogs = { "/admin/data": "datasets", "/admin/models": "models", "/admin/jobs": "jobs", "/admin/audit": "audit" };
const titles = { datasets: "数据管理", models: "模型管理", jobs: "作业管理", audit: "操作记录" };
const kinds = { train: "训练", evaluate: "评估", service: "在线服务" };
const states = { draft: "草稿", queued: "排队中", preparing: "准备中", running: "运行中", ready: "运行中", stopping: "停止中", stopped: "已停止", cancelled: "已取消", succeeded: "已完成", failed: "失败" };
const capabilities = { text: "文本", vision: "视觉", json: "结构化输出" };
export const isManagementPage = path => !!catalogs[path] || ["/admin/stats", "/admin/settings"].includes(path);
const spaceFilter = ctx => `<select class="select filter-select" data-query-filter="space" aria-label="工作空间筛选">${options([["", "全部工作空间"], ...ctx.workspaces.map(item => [item.id, item.name])], ctx.params?.get("space") || "")}</select>`;

export async function loadManagement(api, ctx, signal) {
  const query = new URLSearchParams({ page: ctx.page || 1, page_size: 20, q: ctx.q || "" });
  for (const key of ["space", "status", "job_kind"]) if (ctx.params.get(key)) query.set(key, ctx.params.get(key));
  if (ctx.path === "/admin/stats") return (await api.request(`/admin/statistics?${query}`, { signal })).data;
  if (ctx.path === "/admin/settings") {
    const [settings, connections] = await Promise.all([api.request("/admin/settings", { signal }), api.request("/admin/model-connections", { signal })]);
    return { settings: settings.data, connections: connections.data };
  }
  return api.request(`/admin/asset-catalog/${catalogs[ctx.path]}?${query}`, { signal });
}

function trendChart(rows) {
  const values = rows.map(row => row.train + row.evaluate + row.service), max = Math.max(1, ...values);
  return `<div class="console-trend"><svg width="100%" height="210" role="img" aria-label="最近14天作业创建数量">${[...new Set([0, Math.ceil(max / 2), max])].map(value => `<line x1="36" y1="${170 - value / max * 130}" x2="96%" y2="${170 - value / max * 130}" stroke="#e3e5e8"/><text x="28" y="${175 - value / max * 130}" text-anchor="end">${value}</text>`).join("")}${values.map((value, i) => `<rect x="${12 + i * 6}%" y="${170 - value / max * 130}" width="3%" height="${value / max * 130}" rx="2" fill="#51768d"><title>${e(rows[i].date)}：${value}</title></rect>`).join("")}<text x="12%" y="199">${e(rows[0]?.date || "")}</text><text x="96%" y="199" text-anchor="end">${e(rows.at(-1)?.date || "")}</text></svg></div>`;
}

export function renderManagement(ctx) {
  if (ctx.path === "/admin/settings") return renderSettings(ctx);
  if (ctx.path === "/admin/stats") {
    const data = ctx.data, counts = data.counts || {};
    return pageHeader("统计面板", "", btn("刷新", "refresh")) + `<div class="toolbar">${spaceFilter(ctx)}</div><section class="console-summary console-summary-six">${[["用户", "users"], ["数据集", "datasets"], ["模型", "models"], ["全部作业", "jobs"], ["运行中", "active"], ["失败作业", "failed"]].filter(([, key]) => counts[key] !== null).map(([label, key]) => `<div><span>${label}</span><strong>${counts[key] ?? "—"}</strong></div>`).join("")}</section><div class="console-detail-grid">${card(`<div class="card-header"><h2>作业趋势</h2></div>${trendChart(data.trend || [])}`)}${card(`<div class="card-header"><h2>作业状态</h2></div>${fieldsInfo(Object.entries(data.states || {}).map(([state, count]) => [states[state] || state, e(count)]))}`)}</div><div class="section-heading"><h2>工作空间</h2></div>${table(["工作空间", "作业数"], (data.workspaces || []).map(item => [e(item.name), e(item.jobs)]))}`;
  }
  const kind = catalogs[ctx.path], data = ctx.data.data || [];
  const jobFilters = kind === "jobs" ? `<select class="select filter-select" data-query-filter="job_kind" aria-label="作业类型">${options([["", "全部类型"], ...Object.entries(kinds)], ctx.params.get("job_kind") || "")}</select><select class="select filter-select" data-query-filter="status" aria-label="作业状态">${options([["", "全部状态"], ...Object.entries(states)], ctx.params.get("status") || "")}</select>` : "";
  const heads = kind === "audit" ? ["时间", "操作", "操作者", "工作空间", "目标", "结果"] : kind === "jobs" ? ["作业", "类型", "工作空间", "创建人", "状态", "资源", "创建时间"] : ["名称", "任务", "工作空间", "空间所有者", "最新版本", ...(kind === "datasets" ? ["样本数"] : ["训练器"]), "创建时间"];
  const rows = data.map(item => {
    if (kind === "audit") return [date(item.created_at), e(actionLabel(item.action)), e(item.actor_name), e(item.workspace_name), `<span class="live-source">${e(item.target_id)}</span>`, badge(item.result === "success" ? "已保存" : "失败")];
    const href = kind === "jobs" ? `/runs/${item.id}?workspace=${item.workspace_id}` : `/${kind}/${item.id}?workspace=${item.workspace_id}`;
    if (kind === "jobs") return [link(item.name, href), tag(kinds[item.kind]), e(item.workspace_name), e(item.actor_name), badge(states[item.status] || item.status), tag(item.device_kind === "cuda" ? "GPU" : "CPU"), date(item.created_at)];
    return [link(item.name, href), tag(TASKS[item.task_type]), e(item.workspace_name), e(item.actor_name), e(kind === "datasets" ? item.latest_version ? `v${item.latest_version.number}` : "—" : item.latest_version?.version || "—"), e(kind === "datasets" ? item.latest_version?.sample_count ?? "—" : item.trainer_id), date(item.created_at)];
  });
  return pageHeader(titles[kind]) + toolbar(ctx.q, spaceFilter(ctx) + jobFilters, kind === "audit" ? "搜索操作" : "搜索名称") + table(heads, rows) + pager(ctx.data.pagination);
}

function renderSettings(ctx) {
  const config = ctx.data.settings;
  return pageHeader("系统设置", "", btn("修改设置", "modal", "settings-edit", "primary")) +
    card(`<div class="card-header"><h2>平台设置</h2></div>${fieldsInfo([["平台名称", e(config.platform_name)], ["邀请注册", tag(config.invitations_enabled ? "开启" : "关闭")], ["全局并发上限", e(config.global_concurrent_jobs)], ["单文件上限", `${config.max_upload_mib} MiB`], ["样本数上限", e(config.max_samples)]])}`) +
    `<div class="section-heading"><h2>大模型连接</h2>${btn("新增连接", "modal", "connection-new", "primary")}</div>` +
    table(["连接", "服务地址", "模型", "能力", "凭据", "状态", "操作"], (ctx.data.connections || []).map(item => [e(item.name), `<span class="live-source" title="${e(item.endpoint)}">${e(item.endpoint)}</span>`, e(item.model), item.capabilities.map(capability => tag(capabilities[capability])).join(" "), tag(item.credential_set ? "已配置" : "未配置"), badge(!item.active ? "停用" : item.health.status === "available" ? "连接成功" : item.health.status === "failed" ? "连接失败" : "未测试"), `<div class="live-row-actions">${btn("配置", "admin-edit-connection", item.id)}${btn("测试连接", "admin-test-connection", item.id, "secondary", !item.active)}</div>`]));
}

export function administrationDialog(modal, ctx) {
  const item = modal.item || {};
  if (modal.kind === "settings-edit") {
    const config = ctx.data.settings;
    return { title: "平台设置", fields: input("平台名称", "platform_name", config.platform_name, 'required maxlength="40"') + `<div class="live-field-grid">${input("全局并发上限", "global_concurrent_jobs", config.global_concurrent_jobs, 'required type="number" min="1" max="100"')}${input("单文件上限 / MiB", "max_upload_mib", config.max_upload_mib, 'required type="number" min="1" max="10"')}${input("单版本样本上限", "max_samples", config.max_samples, 'required type="number" min="2" max="10000"')}</div><label class="check-item"><input type="checkbox" name="invitations_enabled" ${config.invitations_enabled ? "checked" : ""}/>允许邀请注册</label>` };
  }
  if (["connection-new", "connection-edit"].includes(modal.kind)) return { title: item.id ? "配置大模型连接" : "新增大模型连接", fields: input("连接名称", "name", item.name || "", 'required maxlength="100"') + input("API基础地址", "endpoint", item.endpoint || "", 'required type="url" maxlength="1000" placeholder="https://example.com/v1"') + input("模型名称", "model", item.model || "", 'required maxlength="200"') + input(item.id ? "更换API密钥" : "API密钥", "secret", "", `type="password" autocomplete="new-password" maxlength="512" ${item.id ? "" : "required"}`) + `<fieldset class="live-check-field"><legend>模型能力</legend><div class="live-checks">${Object.entries(capabilities).map(([key, label]) => `<label><input type="checkbox" name="capabilities" value="${key}" ${(item.capabilities || ["text"]).includes(key) ? "checked" : ""}/>${label}</label>`).join("")}</div></fieldset><label class="check-item"><input type="checkbox" name="active" ${item.active !== false ? "checked" : ""}/>启用连接</label>` + (item.health?.message ? `<div class="notice">${e(item.health.message)}</div>` : "") };
  if (modal.kind === "invite-new") return { title: "邀请成员注册", fields: select("工作空间", "workspace_id", options(ctx.workspaces.map(space => [space.id, space.name]), ctx.workspace?.id), "required") + select("用户组", "group_id", options([["", "未分组"], ...ctx.groups.map(group => [group.id, group.name])])) + select("空间角色", "role", options([["editor", "编辑者"], ["viewer", "查看者"]])) + input("有效天数", "days", 3, 'required type="number" min="1" max="7"'), submit: "生成邀请" };
  if (["password-own", "password-reset"].includes(modal.kind)) return { title: modal.kind === "password-own" ? "修改密码" : `重置密码：${item.display_name}`, fields: (modal.kind === "password-own" ? input("原密码", "current_password", "", 'required type="password" autocomplete="current-password"') : "") + input("新密码", "password", "", 'required type="password" minlength="12" maxlength="256" autocomplete="new-password"') + input("确认密码", "confirm", "", 'required type="password" minlength="12" maxlength="256" autocomplete="new-password"') };
  if (modal.kind === "profile") return { title: "个人资料", fields: fieldsInfo([["账号", e(ctx.session.user.account)]]) + input("姓名", "display_name", ctx.session.user.display_name, 'required maxlength="100"') };
  if (modal.kind === "workspace-edit") return { title: "修改空间名称", fields: input("空间名称", "name", ctx.workspace.name, 'required maxlength="100"') };
  if (modal.kind === "member-remove") return { title: "移除空间成员", fields: fieldsInfo([["成员", e(item.display_name)], ["账号", e(item.account)]]), submit: "确认移除" };
  if (modal.kind === "user-access") return { title: `${item.display_name}的有效权限`, readOnly: true, fields: `<div class="live-permissions">${item.access.actions.map(key => tag(ACTIONS.find(([action]) => action === key)?.[1] || key)).join("")}</div>` + fieldsInfo(QUOTAS.map(([key, label]) => [label, e(item.access.quota[key])])) };
  if (modal.kind === "group-members") return { title: `${item.name}的成员`, readOnly: true, wide: true, fields: table(["成员", "账号", "状态", "操作"], item.users.map(user => [e(user.display_name), e(user.account), badge(user.active ? "启用" : "停用"), btn("配置", "admin-edit-member-user", user.id)])) };
  return null;
}

export async function saveAdministration(api, modal, form, ctx) {
  const item = modal.item || {}, base = `/workspaces/${modal.workspaceId}`;
  if (modal.kind === "settings-edit") return { data: await api.request("/admin/settings", { method: "PATCH", revision: ctx.data.settings.revision, body: { platform_name: form.get("platform_name"), invitations_enabled: form.has("invitations_enabled"), ...Object.fromEntries(["global_concurrent_jobs", "max_upload_mib", "max_samples"].map(key => [key, Number(form.get(key))])) } }) };
  if (["connection-new", "connection-edit"].includes(modal.kind)) {
    const body = { name: form.get("name"), endpoint: form.get("endpoint"), model: form.get("model"), capabilities: form.getAll("capabilities"), active: form.has("active") };
    if (form.get("secret")) body.secret = form.get("secret");
    await api.request(`/admin/model-connections${item.id ? `/${item.id}` : ""}`, { method: item.id ? "PATCH" : "POST", revision: item.revision, body }); return {};
  }
  if (modal.kind === "invite-new") {
    const result = (await api.request("/admin/invitations", { method: "POST", body: { workspace_id: form.get("workspace_id"), group_id: form.get("group_id") || null, role: form.get("role"), days: Number(form.get("days")) } })).data;
    ctx.generatedInvite = `${ctx.origin}/#/register?invitation=${encodeURIComponent(result.invitation)}`; return {};
  }
  if (["password-own", "password-reset"].includes(modal.kind)) {
    if (form.get("password") !== form.get("confirm")) throw new Error("两次输入的密码不一致");
    await api.request(modal.kind === "password-own" ? "/auth/password" : `/admin/users/${item.id}/password`, { method: "POST", body: { password: form.get("password"), current_password: form.get("current_password") || null } });
    return modal.kind === "password-own" || item.id === ctx.session.user.id ? { destination: "/login" } : {};
  }
  if (modal.kind === "profile") { await api.request("/auth/profile", { method: "PATCH", revision: ctx.session.user.revision, body: { display_name: form.get("display_name") } }); return {}; }
  if (modal.kind === "workspace-edit") { await api.request(base, { method: "PATCH", revision: ctx.workspace.revision, body: { name: form.get("name") } }); return {}; }
  if (modal.kind === "member-remove") { await api.request(`${base}/members/${item.user_id}/remove`, { method: "POST" }); return {}; }
  return null;
}

export async function administrationAction(action, id, { api, ctx, openModal, render, load, toast }) {
  if (!action.startsWith("admin-")) return false;
  const user = ctx.data.data?.find(item => item.id === id);
  if (action === "admin-test-connection") {
    if (ctx.adminBusy) return true;
    ctx.adminBusy = true;
    try { toast("正在测试模型连接…"); const result = (await api.request(`/admin/model-connections/${id}/test`, { method: "POST" })).data; await load(); toast(result.health.message); }
    finally { ctx.adminBusy = false; }
  }
  if (action === "admin-edit-connection") openModal("connection-edit", ctx.data.connections.find(item => item.id === id));
  if (action === "admin-reset-password") openModal("password-reset", user);
  if (action === "admin-user-access") openModal("user-access", { ...user, access: (await api.request(`/admin/users/${id}/access`)).data });
  if (action === "admin-group-members") openModal("group-members", { ...user, users: await api.all(`/admin/users?group_id=${id}`) });
  if (action === "admin-edit-member-user") openModal("user-edit", ctx.ui.modal.item.users.find(item => item.id === id));
  if (action === "admin-remove-member") openModal("member-remove", ctx.data.members.data.find(item => item.user_id === id));
  if (action === "admin-copy-invite") { await navigator.clipboard.writeText(ctx.generatedInvite); toast("邀请链接已复制"); }
  if (action === "admin-hide-invite") { ctx.generatedInvite = null; render(); }
  return true;
}
