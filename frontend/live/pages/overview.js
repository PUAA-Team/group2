import { ACTIONS, badge, btn, can, card, date, e, fieldsInfo, link, pageHeader, pager, QUOTAS, raw, table, tag, TASKS, workspaceRequired } from "../components.js?v=stage20a-2";

const JOB_STATUS_LABELS = { draft: "草稿", queued: "排队中", preparing: "准备中", running: "运行中", stopping: "停止中", succeeded: "已完成", failed: "失败", stopped: "已停止", cancelled: "已取消" };

export function renderHome(ctx) {
  if (!ctx.workspace) return pageHeader("工作台") + workspaceRequired(ctx);
  const values = ctx.data.counts || {};
  const counts = [["训练项目", values.projects, "/projects"], ["运行中训练", values.active, "/runs?status=running"], ["排队中训练", values.queued, "/runs?status=queued"], ["已完成训练", values.succeeded, "/runs?status=succeeded"], ["可用数据集", values.datasets, "/datasets"]].filter(([, value]) => value !== null);
  const actions = can(ctx, "training.write") ? '<a class="btn btn-primary" href="#/train/new">新建训练</a>' : "";
  const rows = (ctx.data.recent_jobs || []).map(item => [raw(link(item.name, `/runs/${item.id}`)), raw(tag(TASKS[item.task_type] || "—")), raw(badge(JOB_STATUS_LABELS[item.status] || item.status)), item.result?.accuracy == null ? "—" : `${(item.result.accuracy * 100).toFixed(1)}%`, item.model_name || "—", date(item.created_at)]);
  const shortcuts = [["新建训练", "/train/new", "training.write"], ["导入数据集", "/datasets/new", "datasets.write"], ["在线标注", "/annotation", "datasets.write"], ["模型仓库", "/models", "models.read"]].filter(([, , action]) => can(ctx, action)).map(([label, href]) => `<a class="quick-link" href="#${href}">${label}<span aria-hidden="true">›</span></a>`).join("");
  const actionNames = { "presets.create": "添加示例资产", "jobs.create": "创建任务", "jobs.submit": "提交任务", "jobs.stop": "停止任务", "projects.create": "新建项目", "datasets.create": "新增数据集", "dataset_versions.create": "导入数据", "models.create": "登记模型", "model_versions.create": "登记模型版本" };
  const activity = (ctx.data.activity || []).map(item => `<div class="console-activity"><strong>${e(actionNames[item.action] || item.action)}</strong><span>${e(item.actor_name)}</span><time>${date(item.created_at)}</time></div>`).join("");
  const pItems = Array.isArray(ctx.data.pending_items) ? ctx.data.pending_items : [];
  const pendingBar = pItems.length ? `<div class="section-heading"><h2>待处理事项</h2></div><section class="console-summary">${pItems.map(item => `<a href="#${e(item.href)}"><span>${e(item.label)}</span><strong>${e(item.count)}</strong></a>`).join("")}</section>` : "";
  return pageHeader("工作台", "", actions) + `<section class="console-summary">${counts.map(([label, value, href]) => `<a href="#${href}"><span>${label}</span><strong>${value ?? "—"}</strong></a>`).join("")}</section>` + pendingBar +
    `<div class="section-heading"><h2>最近训练</h2>${can(ctx, "training.read") ? '<a class="entity-link" href="#/runs">全部训练</a>' : ""}</div>` + table(["任务", "任务类型", "状态", "准确率", "模型", "创建时间"], rows) +
    `<div class="section-heading"><h2>继续操作</h2>${can(ctx, "models.write") && can(ctx, "datasets.write") ? btn("添加示例资产", "modal", "examples") : ""}</div><div class="console-home-bottom"><div class="console-quick">${shortcuts || '<a class="quick-link" href="#/space">用户空间</a>'}</div>${card(`<div class="card-header"><h2>近期操作</h2></div>${activity || '<div class="empty-state">暂无操作记录</div>'}`)}</div>`;
}

export function renderSpace(ctx) {
  const create = ctx.session.access.actions.includes("workspaces.create") ? btn("创建空间", "modal", "workspace-new", "primary") : "";
  const joinBtn = btn("加入空间", "modal", "workspace-join");
  const spaces = `<div class="live-spaces">${ctx.workspaces.map(space => `<button class="live-space ${space.id === ctx.workspace?.id ? "selected" : ""}" data-action="select-workspace" data-id="${e(space.id)}"><strong>${e(space.name)}</strong>${space.id === ctx.workspace?.id ? tag("当前空间") : ""}</button>`).join("")}</div>`;
  if (!ctx.workspace) return pageHeader("用户空间", "", joinBtn + create) + spaces + workspaceRequired(ctx);
  const members = ctx.data.members;
  const inviteBanner = ctx.generatedSpaceInvite ? `<div class="notice"><label for="space-invite-url">空间邀请链接（仅显示本次）</label><div class="heading-actions"><input id="space-invite-url" class="input" readonly value="${e(ctx.generatedSpaceInvite.url)}"/>${btn("复制链接", "admin-copy-space-invite")}${btn("关闭", "admin-hide-space-invite")}</div></div>` : "";
  const inviteRows = (ctx.data.invites || []).map(inv => [
    inv.code_preview, raw(tag(inv.role === "viewer" ? "查看者" : "编辑者")), raw(tag(inv.require_approval ? "需审核" : "免审核")),
    inv.max_uses == null ? `${inv.used_count} / 不限` : `${inv.used_count} / ${inv.max_uses}`,
    date(inv.expires_at), raw(badge(inv.revoked_at ? "已撤销" : "有效")),
    inv.revoked_at ? "—" : raw(btn("撤销", "admin-revoke-space-invite", inv.id)),
  ]);
  const requestRows = (ctx.data.joinRequests || []).map(req => [
    req.display_name, req.account, raw(tag(req.requested_role === "viewer" ? "查看者" : "编辑者")),
    raw(badge(({ pending: "待审批", approved: "已通过", rejected: "已拒绝" })[req.status] || req.status)),
    req.status === "pending" ? raw(`<div class="live-row-actions">${btn("批准", "admin-approve-join", req.id, "primary")}${btn("拒绝", "admin-reject-join", req.id)}</div>`) : date(req.reviewed_at),
  ]);
  const memberSection = can(ctx, "members.manage") ? `<div class="section-heading"><h2>空间成员</h2><div class="heading-actions">${btn("生成空间邀请", "modal", "workspace-invite")}${btn("添加成员", "modal", "member", "primary")}</div></div>` + inviteBanner +
    table(["成员", "账号", "空间角色", "操作"], (members?.data || []).map(member => [member.display_name, member.account, raw(tag(member.role === "viewer" ? "查看者" : "编辑者")),
      ctx.workspace.owner_id === member.user_id ? raw(tag("所有者")) : raw(`<div class="live-row-actions">${btn("修改角色", "edit-member", member.user_id)}${btn("移除", "admin-remove-member", member.user_id)}</div>`) ])) + pager(members?.pagination) +
    `<div class="section-heading"><h2>空间邀请码</h2></div>` + table(["邀请码", "默认角色", "加入方式", "使用次数", "过期时间", "状态", "操作"], inviteRows, "暂无空间邀请") +
    `<div class="section-heading"><h2>加入申请</h2></div>` + table(["姓名", "账号", "申请角色", "状态", "处理"], requestRows, "暂无加入申请") : "";
  return pageHeader("用户空间", "", (can(ctx, "assistants.use") ? `<a class="btn btn-secondary" href="#/assistants">智能辅助</a>` : "") + (can(ctx, "members.manage") && can(ctx, "assistants.use") ? btn("智能辅助授权", "assistant-policy") : "") + btn("个人资料", "modal", "profile") + btn("修改密码", "modal", "password-own") + joinBtn + create + (can(ctx, "members.manage") ? btn("修改空间", "modal", "workspace-edit") + btn("删除空间", "modal", "workspace-delete") : "")) + spaces +
    `<div class="section-heading"><h2>我的权限</h2></div><div class="permission-grid live-permissions">${ACTIONS.filter(([key]) => ctx.access.actions.includes(key)).map(([, label]) => tag(label)).join("") || tag("暂无权限")}</div>` +
    `<div class="section-heading"><h2>资源上限</h2></div>` + fieldsInfo(QUOTAS.map(([key, label]) => [label, e(ctx.access.quota[key] ?? 0)])) +
    (ctx.data.storage ? `<div class="section-heading"><h2>文件存储</h2></div>` + fieldsInfo([
      ['我的文件', `${(ctx.data.storage.personal_bytes / 1048576).toFixed(2)} MiB`],
      ['当前空间', `${(ctx.data.storage.workspace_bytes / 1048576).toFixed(2)} MiB`],
      ['数据版本', `${((ctx.data.storage.categories.dataset || 0) / 1048576).toFixed(2)} MiB`],
      ['模型产物', `${((ctx.data.storage.categories.artifact || 0) / 1048576).toFixed(2)} MiB`],
      ['处理候选', `${((ctx.data.storage.categories.candidate || 0) / 1048576).toFixed(2)} MiB`],
      ['未归属文件', `${(ctx.data.storage.unattributed_bytes / 1048576).toFixed(2)} MiB`]]) : '') +
    (ctx.data.myJobs ? `<div class="section-heading"><h2>我的近期任务</h2></div>` + table(["任务", "类型", "状态", "创建时间"], (ctx.data.myJobs || []).map(job => [
      raw(link(job.name, `/runs/${job.id}`)), raw(tag(TASKS[job.task_type] || job.job_kind || "—")), raw(badge(JOB_STATUS_LABELS[job.status] || job.status)), date(job.created_at),
    ]), "暂无个人任务") : "") +
    (ctx.data.sessions ? `<div class="section-heading"><h2>登录会话管理</h2>${ctx.data.sessions.length > 1 ? btn("踢出其他设备", "session-revoke-others") : ""}</div>` + table(["会话标识", "登录时间", "过期时间", "状态", "操作"], ctx.data.sessions.map(s => [
      raw(`<code>${e(s.id)}</code>`), date(s.created_at), date(s.expires_at), raw(badge(s.current ? "当前设备" : "其他设备")),
      s.current ? raw(tag("当前会话")) : raw(btn("退出该设备", "session-revoke", s.id)),
    ]), "暂无活跃会话") : "") + memberSection;
}

const pending = {
  "/monitor": ["资源监控", "资源接入待完成"], "/annotation": ["在线标注", "智能标注待接入"], "/augmentation": ["数据增强", "数据处理待接入"],
  "/projects": ["训练项目", "训练执行待接入"], "/runs": ["训练任务", "训练执行待接入"], "/evaluation": ["模型评估", "评估执行待接入"],
  "/services": ["在线服务", "推理服务待接入"], "/api-keys": ["API KEY管理", "推理鉴权待接入"], "/admin/resources": ["资源管理", "Worker 待接入"],
  "/admin/jobs": ["作业管理", "调度待接入"], "/admin/settings": ["系统设置", "模型网关待接入"],
};
export function renderPending(path) {
  const [title, state] = pending[path] || ["页面不存在", "返回工作台"];
  return pageHeader(title) + `<div class="live-pending">${tag(state)}<div class="heading-actions"><a class="btn btn-secondary" href="#/datasets">数据集</a><a class="btn btn-secondary" href="#/models">模型仓库</a></div></div>`;
}
