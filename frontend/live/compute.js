import { badge, btn, can, card, date, e, fieldsInfo, input, link, options, pageHeader, pager, select, table, tag, toolbar } from "./components.js?v=stage13-3a";

export const isComputePage = path => ["/monitor", "/admin/resources"].includes(path);

export async function loadCompute(api, ctx, signal) {
  const admin = ctx.path === "/admin/resources";
  if (!admin && !ctx.workspace) return { data: [] };
  const base = admin ? "/admin/nodes" : `/workspaces/${ctx.workspace.id}/resources`;
  const [nodes, runtime] = await Promise.all([
    api.request(`${base}?page=${ctx.page}&page_size=20&q=${encodeURIComponent(ctx.q)}`, { signal }),
    ctx.session.user.is_admin && ctx.session.access.actions.includes("resources.manage") ? api.request("/admin/worker-runtimes", { signal }) : null,
  ]);
  const detail = ctx.params.get("node") ? (await api.request(`/resources/nodes/${encodeURIComponent(ctx.params.get("node"))}`, { signal })).data : null;
  const connection = ctx.resourceConnection;
  let receipt;
  if (connection?.id) receipt = (await api.request(`/resources/enrollments/${connection.id}`, { signal })).data;
  return { ...nodes, runtime: runtime?.data, detail, connectionReceipt: receipt };
}

const nodeRoute = (ctx, node) => `${ctx.path}?node=${encodeURIComponent(node.id)}`;
export function renderCompute(ctx) {
  const admin = ctx.path === "/admin/resources";
  const tab = ctx.params.get("tab") || "devices";
  const manage = ctx.session.user.is_admin ? ctx.session.access.actions.includes("resources.manage") : can(ctx, "resources.manage");
  const nodes = ctx.data.data || [];
  const actions = manage ? btn("生成接入命令", "modal", "enroll-new", "primary", !ctx.workspace) +
    (ctx.data.runtime?.local_enabled ? btn("接入本机", "modal", "local-worker", "secondary", !ctx.workspace) + btn("停止本机 Worker", "modal", "local-stop") : "") : "";
  if (ctx.data.detail) return renderNode(ctx, ctx.data.detail, manage);
  let content = "";
  if (tab === "connect") content = renderConnection(ctx, actions);
  else if (tab === "nodes") content = table(["节点", "空间", "操作系统", "GPU", "状态", "最近心跳", "操作"], nodes.map(node => [
    link(node.name, nodeRoute(ctx, node)), e(ctx.workspaces.find(space => space.id === node.workspace_id)?.name || "—"), e(node.inventory.platform),
    e(node.devices.filter(device => device.kind === "cuda" && device.present).length), badge(node.status), date(node.last_seen_at),
    manage ? btn("配置", "node-config", node.id) + btn("探测", "node-probe", node.id) : "—",
  ])) + pager(ctx.data.pagination, "个节点");
  else content = nodes.length ? nodes.map(node => `<div class="section-heading"><h2><a class="entity-link" href="#${e(nodeRoute(ctx, node))}">${e(node.name)}</a></h2>${badge(node.status)}</div>` +
    table(["设备", "类型", "显存 / 内存", "利用率", "状态", "运行时"], node.devices.filter(device => device.present || device.reserved_execution_id).map(device => [
      e(device.name), tag(device.kind === "cuda" ? "GPU" : "CPU"), device.memory_mb ? `${device.memory_mb} MiB` : "—",
      device.metrics.utilization === null || device.metrics.utilization === undefined ? "—" : `${e(device.metrics.utilization)}%`, badge(device.status),
      tag(device.kind === "cuda" ? node.inventory.runtime.cuda_available ? "CUDA 就绪" : "CUDA 未就绪" : node.inventory.runtime.torch_version ? "PyTorch" : "待配置"),
    ]))).join("") + pager(ctx.data.pagination, "个节点") : `<div class="empty-state"><h3>尚未接入计算节点</h3>${actions}</div>`;
  return pageHeader(admin ? "资源管理" : "资源监控", "", actions) +
    `<div class="tabs">${[["devices", "设备"], ["nodes", "计算节点"], ["connect", "接入新节点"]].map(([key, label]) => `<a class="tab ${tab === key ? "active" : ""}" href="#${ctx.path}?tab=${key}">${label}</a>`).join("")}</div>` +
    (tab === "connect" ? "" : toolbar(ctx.q, "", "搜索节点")) + content;
}

function renderNode(ctx, node, manage) {
  const actions = manage ? btn("配置", "node-config", node.id) + btn("重新探测", "node-probe", node.id) + btn(node.enabled ? "暂停接收" : "恢复接收", "node-toggle", node.id) + btn("撤销接入", "node-revoke", node.id, "danger") : "";
  const runtime = node.inventory.runtime;
  return `<div class="breadcrumb"><a href="#${ctx.path}">计算节点</a><span>/</span><span>${e(node.name)}</span></div>` + pageHeader(node.name, "", actions) +
    `<div class="live-detail-meta">${badge(node.status)}${node.probe_request_id ? tag("探测处理中") : ""}</div>` +
    fieldsInfo([["主机", e(node.inventory.hostname)], ["系统", e(node.inventory.platform)], ["CPU 线程", e(node.inventory.cpu_count)],
      ["内存", node.inventory.memory_mb ? `${node.inventory.memory_mb} MiB` : "—"], ["最近心跳", date(node.last_seen_at)], ["最近探测", date(node.last_inventory_at)],
      ["PyTorch", e(runtime.torch_version || "未安装")], ["CUDA", e(runtime.cuda_version || "—")], ["执行槽位", e(node.slots)], ["工作空间", e(ctx.workspaces.find(space => space.id === node.workspace_id)?.name || "—")]]) +
    `<div class="section-heading"><h2>设备清单</h2></div>` + table(["设备", "标识", "显存 / 内存", "状态"], node.devices.map(device => [e(device.name), `<span class="live-break">${e(device.hardware_id)}</span>`, `${device.memory_mb} MiB`, badge(device.status)])) +
    (node.inventory.errors?.length ? `<div class="section-heading"><h2>探测结果</h2></div><div class="live-permissions">${node.inventory.errors.map(tag).join("")}</div>` : "");
}

function renderConnection(ctx, actions) {
  const connection = ctx.resourceConnection;
  if (!connection) return `<div class="live-pending">${actions}${tag("等待生成接入命令")}</div>`;
  const receipt = ctx.data.connectionReceipt;
  const status = receipt?.status || (connection.node_id ? "已接入" : "正在启动");
  return `<div class="section-heading"><h2>连接状态</h2>${badge(status)}</div><div class="live-detail-meta">${connection.expires_at ? tag(`有效至 ${date(connection.expires_at)}`) : ""}${receipt?.node_id || connection.node_id ? `<a class="entity-link" href="#${ctx.path}?node=${e(receipt?.node_id || connection.node_id)}">查看节点</a>` : ""}</div>` +
    (connection.display_command ? card(`<div class="card-header"><h2>执行命令</h2>${btn("复制完整命令", "copy-join")}</div><pre class="template-preview compute-command">${e(connection.display_command)}</pre>`) : "") +
    `<div class="heading-actions" style="margin-top:20px">${connection.id && status === "等待连接" ? btn("撤销接入码", "enrollment-revoke", connection.id) : ""}${actions}</div>`;
}

export function computeDialog(modal, ctx) {
  const item = modal.item || {};
  if (modal.kind === "enroll-new") return { title: "生成节点接入命令", submit: "生成", fields:
    input("节点名称", "name", "开发节点", 'required maxlength="100"') +
    select("工作空间", "workspace_id", options(ctx.workspaces.map(space => [space.id, space.name]), ctx.workspace?.id)) +
    select("部署方式", "platform", options([["windows", "Windows PowerShell"], ["linux", "Linux Shell"], ["docker", "Docker 镜像"]]), "data-enroll-platform") +
    input("主服务器地址", "controller_url", ctx.origin || "http://127.0.0.1:8000", 'required type="url"') +
    input("训练 Python", "training_python", "python", 'required maxlength="500"') +
    input("Worker 目录", "state_dir", "D:/model-training-worker", 'required maxlength="500"') +
    `<div class="field" data-image-field hidden><label for="worker-image">已构建的镜像</label><input id="worker-image" class="input" name="image" maxlength="300" /></div>` +
    (ctx.session.user.is_admin ? '<label class="check-item"><input type="checkbox" name="auto_approve" checked />连接后自动准入</label>' : tag("连接后等待管理员审核")) };
  if (modal.kind === "local-worker") return { title: "接入本机 Worker", submit: "启动并接入", fields:
    input("节点名称", "name", "本机 GPU 节点", 'required maxlength="100"') +
    select("工作空间", "workspace_id", options(ctx.workspaces.map(space => [space.id, space.name]), ctx.workspace?.id)) +
    select("训练环境", "runtime_id", options((ctx.data.runtime?.runtimes || []).filter(runtime => runtime.configured).map(runtime => [runtime.id, runtime.name]), "llm")) };
  if (modal.kind === "node-edit") return { title: "配置计算节点", fields: input("节点名称", "name", item.name, 'required maxlength="100"') +
    (ctx.session.user.is_admin ? select("工作空间", "workspace_id", options(ctx.workspaces.map(space => [space.id, space.name]), item.workspace_id)) + '<label class="check-item"><input type="checkbox" name="approved" ' + (item.approved ? "checked" : "") + '/>审核准入</label>' : "") };
  if (["node-toggle", "node-revoke", "enrollment-revoke", "local-stop"].includes(modal.kind)) return { title: modal.kind === "local-stop" ? "停止本机 Worker" : modal.kind === "node-toggle" ? item.enabled ? "暂停接收新任务" : "恢复接收任务" : modal.kind === "node-revoke" ? "撤销节点接入" : "撤销接入码", fields: `<div>${e(item.name || (modal.kind === "local-stop" ? "当前本机 Worker" : "当前接入申请"))}</div>`, submit: "确认" };
  return null;
}

export async function saveCompute(api, modal, form, ctx) {
  if (modal.kind === "enroll-new") {
    const body = Object.fromEntries(["name", "workspace_id", "platform", "controller_url", "training_python", "state_dir", "image"].map(key => [key, form.get(key)]));
    body.auto_approve = form.has("auto_approve");
    ctx.resourceConnection = (await api.request(ctx.session.user.is_admin ? "/admin/enrollments" : `/workspaces/${body.workspace_id}/enrollments`, { method: "POST", body })).data;
    return { destination: ctx.path + "?tab=connect" };
  }
  if (modal.kind === "local-worker") {
    ctx.resourceConnection = (await api.request("/admin/local-worker", { method: "POST", body: Object.fromEntries(form) })).data;
    ctx.resourceConnection.id = ctx.resourceConnection.enrollment_id;
    return { destination: ctx.path + "?tab=connect" };
  }
  if (modal.kind === "local-stop") { await api.request("/admin/local-worker/stop", { method: "POST" }); ctx.resourceConnection = null; return {}; }
  if (modal.kind === "node-edit") {
    const body = { name: form.get("name") };
    if (ctx.session.user.is_admin) Object.assign(body, { workspace_id: form.get("workspace_id"), approved: form.has("approved") });
    await api.request(`/resources/nodes/${modal.item.id}`, { method: "PATCH", revision: modal.item.revision, body }); return {};
  }
  if (modal.kind === "node-toggle") { await api.request(`/resources/nodes/${modal.item.id}`, { method: "PATCH", revision: modal.item.revision, body: { enabled: !modal.item.enabled } }); return {}; }
  if (modal.kind === "node-revoke") { await api.request(`/resources/nodes/${modal.item.id}/revoke`, { method: "POST" }); return {}; }
  if (modal.kind === "enrollment-revoke") { await api.request(`/resources/enrollments/${modal.item.id}/revoke`, { method: "POST" }); ctx.resourceConnection = null; return {}; }
  return null;
}

export async function computeAction(action, id, { api, ctx, openModal, toast, load }) {
  const node = ctx.data.detail || ctx.data.data?.find(item => item.id === id);
  if (action === "node-config") { openModal("node-edit", node); return true; }
  if (action === "node-toggle" || action === "node-revoke") { openModal(action, node); return true; }
  if (action === "enrollment-revoke") { openModal(action, { id }); return true; }
  if (action === "node-probe") { await api.request(`/resources/nodes/${id}/probe`, { method: "POST" }); toast("已发送探测请求"); await load(); return true; }
  if (action === "copy-join") { await navigator.clipboard.writeText(ctx.resourceConnection.command); toast("已复制完整命令"); return true; }
  return false;
}
