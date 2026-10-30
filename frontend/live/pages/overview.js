import { ACTIONS, badge, btn, can, card, date, e, fieldsInfo, link, pageHeader, pager, QUOTAS, table, tag, TASKS, workspaceRequired } from "../components.js?v=stage13-3a";

export function renderHome(ctx) {
  if (!ctx.workspace) return pageHeader("工作台") + workspaceRequired(ctx);
  const values = ctx.data.counts || {};
  const counts = [["训练项目", values.projects, "/projects"], ["运行中训练", values.active, "/runs?status=running"], ["排队中训练", values.queued, "/runs?status=queued"], ["已完成训练", values.succeeded, "/runs?status=succeeded"], ["可用数据集", values.datasets, "/datasets"]].filter(([, value]) => value !== null);
  const actions = can(ctx, "training.write") ? '<a class="btn btn-primary" href="#/train/new">新建训练</a>' : "";
  const labels = { draft: "草稿", queued: "排队中", preparing: "准备中", running: "运行中", stopping: "停止中", succeeded: "已完成", failed: "失败", stopped: "已停止", cancelled: "已取消" };
  const rows = (ctx.data.recent_jobs || []).map(item => [link(item.name, `/runs/${item.id}`), tag(TASKS[item.task_type] || "—"), badge(labels[item.status] || item.status), item.result?.accuracy == null ? "—" : `${(item.result.accuracy * 100).toFixed(1)}%`, e(item.model_name || "—"), date(item.created_at)]);
  const shortcuts = [["新建训练", "/train/new", "training.write"], ["导入数据集", "/datasets/new", "datasets.write"], ["在线标注", "/annotation", "datasets.write"], ["模型仓库", "/models", "models.read"]].filter(([, , action]) => can(ctx, action)).map(([label, href]) => `<a class="quick-link" href="#${href}">${label}<span aria-hidden="true">›</span></a>`).join("");
  const actionNames = { "presets.create": "添加示例资产", "jobs.create": "创建任务", "jobs.submit": "提交任务", "jobs.stop": "停止任务", "projects.create": "新建项目", "datasets.create": "新增数据集", "dataset_versions.create": "导入数据", "models.create": "登记模型", "model_versions.create": "登记模型版本" };
  const activity = (ctx.data.activity || []).map(item => `<div class="console-activity"><strong>${e(actionNames[item.action] || item.action)}</strong><span>${e(item.actor_name)}</span><time>${date(item.created_at)}</time></div>`).join("");
  return pageHeader("工作台", "", actions) + `<section class="console-summary">${counts.map(([label, value, href]) => `<a href="#${href}"><span>${label}</span><strong>${value ?? "—"}</strong></a>`).join("")}</section>` +
    `<div class="section-heading"><h2>最近训练</h2>${can(ctx, "training.read") ? '<a class="entity-link" href="#/runs">全部训练</a>' : ""}</div>` + table(["任务", "任务类型", "状态", "准确率", "模型", "创建时间"], rows) +
    `<div class="section-heading"><h2>继续操作</h2>${can(ctx, "models.write") && can(ctx, "datasets.write") ? btn("添加示例资产", "modal", "examples") : ""}</div><div class="console-home-bottom"><div class="console-quick">${shortcuts || '<a class="quick-link" href="#/space">用户空间</a>'}</div>${card(`<div class="card-header"><h2>近期操作</h2></div>${activity || '<div class="empty-state">暂无操作记录</div>'}`)}</div>`;
}

export function renderSpace(ctx) {
  const create = ctx.session.access.actions.includes("workspaces.create") ? btn("创建空间", "modal", "workspace-new", "primary") : "";
  const spaces = `<div class="live-spaces">${ctx.workspaces.map(space => `<button class="live-space ${space.id === ctx.workspace?.id ? "selected" : ""}" data-action="select-workspace" data-id="${e(space.id)}"><strong>${e(space.name)}</strong>${space.id === ctx.workspace?.id ? tag("当前空间") : ""}</button>`).join("")}</div>`;
  if (!ctx.workspace) return pageHeader("用户空间", "", create) + spaces + workspaceRequired(ctx);
  const members = ctx.data.members;
  const memberSection = can(ctx, "members.manage") ? `<div class="section-heading"><h2>空间成员</h2>${btn("添加成员", "modal", "member", "primary")}</div>` +
    table(["成员", "账号", "空间角色", "操作"], (members?.data || []).map(member => [e(member.display_name), e(member.account), tag(member.role === "viewer" ? "查看者" : "编辑者"),
      ctx.workspace.owner_id === member.user_id ? tag("所有者") : `<div class="live-row-actions">${btn("修改角色", "edit-member", member.user_id)}${btn("移除", "admin-remove-member", member.user_id)}</div>`])) + pager(members?.pagination) : "";
  return pageHeader("用户空间", "", btn("个人资料", "modal", "profile") + btn("修改密码", "modal", "password-own") + create + (can(ctx, "members.manage") ? btn("修改空间", "modal", "workspace-edit") : "")) + spaces +
    `<div class="section-heading"><h2>我的权限</h2></div><div class="permission-grid live-permissions">${ACTIONS.filter(([key]) => ctx.access.actions.includes(key)).map(([, label]) => tag(label)).join("") || tag("暂无权限")}</div>` +
    `<div class="section-heading"><h2>资源上限</h2></div>` + fieldsInfo(QUOTAS.map(([key, label]) => [label, e(ctx.access.quota[key] ?? 0)])) + memberSection;
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
