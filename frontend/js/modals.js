import { taskById } from "./data.js?v=console-4";
import { effectiveAccess, PERMISSIONS } from "./state.js?v=console-4";
import { escapeHtml as e, icon } from "./ui.js?v=console-4";

const checks = selected => `<div class="permission-grid">${PERMISSIONS.map(([key, label]) => `<label class="check-item"><input type="checkbox" name="permission" value="${key}" ${selected.includes(key) ? "checked" : ""}>${e(label)}</label>`).join("")}</div>`;
const field = (label, control) => `<label class="field"><span>${label}</span>${control}</label>`;
const input = (name, value = "", extra = "") => `<input class="input" name="${name}" value="${e(value)}" ${extra}>`;
const option = (value, label, selected) => `<option value="${e(value)}" ${selected ? "selected" : ""}>${e(label)}</option>`;

function dialog(key, title, formId, body, submitLabel, attributes = "", wide = false) {
  return `<div class="modal-layer" id="demo-modal" data-modal="${e(key)}"><div class="modal-scrim" data-action="close-modal"></div><section class="modal-panel ${wide ? "modal-wide" : ""}" role="dialog" aria-modal="true" aria-labelledby="modal-title"><header class="modal-header"><h2 id="modal-title">${e(title)}</h2><button type="button" class="icon-button" data-action="close-modal" aria-label="关闭弹窗">${icon("close", 18)}</button></header><form id="${formId}" ${attributes}><div class="modal-body stack">${body}</div><footer class="modal-footer"><button type="button" class="btn btn-secondary" data-action="close-modal">取消</button><button type="submit" class="btn btn-primary">${e(submitLabel)}</button></footer></form></section></div>`;
}

export function renderModal(modal, state, ui = {}) {
  if (!modal) return "";
  const { kind, id } = modal;
  const groups = state.groups.filter(group => group.id !== "group-admin");
  if (kind === "user-new") {
    const body = `${field("姓名", input("name", "", 'required maxlength="30" autocomplete="off" autofocus'))}${field("邮箱账号", input("account", "", 'type="email" required maxlength="80" autocomplete="off"'))}${field("初始密码", input("password", "", 'type="password" required minlength="8" autocomplete="new-password"'))}${field("所属用户组", `<select class="select" name="groupId">${groups.map(group => option(group.id, group.name, group.id === state.settings.defaultGroupId)).join("")}</select>`)}`;
    return dialog(kind, "新增用户", "user-new-form", body, "创建用户");
  }
  if (kind === "user-access") {
    const user = state.users.find(item => item.id === id && item.role !== "管理员");
    if (!user) return "";
    const access = effectiveAccess(user, state);
    const body = `<div class="field-row">${field("所属用户组", `<select class="select" name="groupId">${groups.map(group => option(group.id, group.name, group.id === user.groupId)).join("")}</select>`)}${field("当前有效配额", `<div class="quota-summary">GPU ${access.quota.gpu} 卡 · 并发 ${access.quota.jobs} 个</div>`)}</div><div class="form-divider">个人权限</div><div class="permission-grid">${PERMISSIONS.map(([key, label]) => field(e(label), `<select class="select" name="mode:${key}">${option("inherit", "继承用户组", !user.grants.includes(key) && !user.denies.includes(key))}${option("allow", "个人允许", user.grants.includes(key))}${option("deny", "个人禁用", user.denies.includes(key))}</select>`)).join("")}</div><div class="field-row">${field("个人 GPU 上限", input("gpu", user.quota.gpu ?? access.group?.quota.gpu ?? 0, 'type="number" min="0" max="32" required'))}${field("个人并发上限", input("jobs", user.quota.jobs ?? access.group?.quota.jobs ?? 0, 'type="number" min="0" max="100" required'))}</div>`;
    return dialog(kind, `${user.name} · 权限与配额`, "user-access-form", body, "保存更改", `data-user-id="${e(user.id)}"`, true);
  }
  if (kind === "group-new" || kind === "group-access") {
    const group = kind === "group-access" ? state.groups.find(item => item.id === id && item.id !== "group-admin") : null;
    if (kind === "group-access" && !group) return "";
    const body = `${kind === "group-new" ? field("用户组名称", input("name", "", 'required maxlength="30" autofocus')) : ""}<div class="form-divider">基础授权</div>${checks(group?.permissions || ["datasets.read", "resources.view"])}<div class="field-row">${field("GPU 上限", input("gpu", group?.quota.gpu ?? 1, 'type="number" min="0" max="32" required'))}${field("并发任务上限", input("jobs", group?.quota.jobs ?? 2, 'type="number" min="0" max="100" required'))}</div>`;
    return dialog(kind, group ? `${group.name} · 用户组配置` : "新建用户组", group ? "group-access-form" : "group-new-form", body, group ? "保存更改" : "创建用户组", group ? `data-group-id="${e(group.id)}"` : "", true);
  }
  if (kind === "api-key-new") {
    const body = `${field("名称", input("name", "", 'required maxlength="40" autofocus'))}${field("权限范围", `<select class="select" name="scope"><option value="inference">在线推理</option><option value="read">只读访问</option></select>`)}`;
    return dialog(kind, "创建 API KEY", "api-key-form", body, "创建密钥");
  }
  if (kind === "service-new") {
    const runs = state.runs.filter(run => run.status === "已完成");
    const body = `${field("服务名称", input("name", "", 'required maxlength="50" autofocus'))}${field("模型来源", `<select class="select" name="runId" required><option value="">选择已完成的训练任务</option>${runs.map(run => option(run.id, `${run.name} · ${run.metric} ${run.score}`, run.id === id)).join("")}</select>`)}${field("部署资源", `<select class="select" name="resource"><option>CPU · 2 核 4 GB</option><option>GPU · 1 卡 24 GB</option></select>`)}`;
    return dialog(kind, "创建推理服务", "service-form", body, "创建服务");
  }
  if (kind === "node-new") {
    const body = `${field("节点名称", input("name", "", 'required maxlength="40" autofocus'))}${field("地址标识", input("address", "", 'required maxlength="60"'))}${field("演示硬件配置", `<select class="select" name="profile"><option value="4090">RTX 4090 × 2 · 32 核 · 128 GB</option><option value="a100">A100 × 1 · 48 核 · 256 GB</option></select>`)}`;
    return dialog(kind, "登记演示节点", "node-form", body, "登记节点");
  }
  if (kind === "settings") {
    const settings = state.settings;
    const body = `<label class="check-item"><input name="registration" type="checkbox" ${settings.registration ? "checked" : ""}>允许自主注册</label><div class="field-row">${field("注册默认用户组", `<select class="select" name="defaultGroupId">${groups.map(group => option(group.id, group.name, settings.defaultGroupId === group.id)).join("")}</select>`)}${field("全局并发任务上限", input("jobLimit", settings.jobLimit, 'type="number" min="1" max="100" required'))}</div>${field("默认存储配额（GB）", input("storageLimit", settings.storageLimit, 'type="number" min="1" max="10000" required'))}`;
    return dialog(kind, "修改系统设置", "settings-form", body, "保存设置");
  }
  if (kind === "annotation-new") {
    const datasets = state.datasets.filter(item => ["图像", "文本"].includes(item.type));
    const body = `${field("数据集", `<select class="select" name="datasetId" required>${datasets.map(item => option(item.id, `${item.name} · ${taskById(item.taskId)?.name || "—"}`, false)).join("")}</select>`)}<div class="field-row">${field("标签名称", input("label", "", 'required maxlength="40" autofocus'))}${field("标注数量", input("count", 20, 'type="number" min="1" max="100000" required'))}</div>`;
    return dialog(kind, "新建标注批次", "annotation-form", body, "保存批次");
  }
  if (kind === "augmentation-new") {
    const methods = [["flip", "水平翻转", "图像"], ["crop", "随机裁剪", "图像"], ["synonym", "同义词替换", "文本"], ["back-translation", "回译", "文本"], ["noise", "数值扰动", "表格"]];
    const selected = state.datasets.find(item => item.id === ui.augmentationDataset) || state.datasets[0];
    const type = selected?.type === "大语言模型" ? "文本" : selected?.type;
    const available = methods.filter(([, , category]) => category === type);
    const body = `${field("源数据集", `<select class="select" name="datasetId" data-augmentation-dataset required>${state.datasets.map(item => option(item.id, `${item.name} · ${item.type}`, item.id === selected?.id)).join("")}</select>`)}<div class="field-row">${field("增强方式", `<select class="select" name="method">${available.map(([key, label]) => option(key, label, false)).join("")}</select>`)}${field("目标倍数", input("multiplier", 2, 'type="number" min="2" max="10" required'))}</div>`;
    return dialog(kind, "创建增强方案", "augmentation-form", body, "创建方案");
  }
  if (kind === "process-dataset") {
    const dataset = state.datasets.find(item => item.id === id);
    if (!dataset) return "";
    const options = taskById(dataset.taskId)?.processing || [];
    const body = `<div class="checklist">${options.map((value, index) => `<label class="check-item"><input type="checkbox" name="process" value="${e(value)}" ${index === 0 ? "checked" : ""}>${e(value)}</label>`).join("")}</div>${field("训练集比例", `<select class="select" name="split"><option value="80">80% 训练 / 20% 验证</option><option value="70">70% 训练 / 30% 验证</option><option value="90">90% 训练 / 10% 验证</option></select>`)}`;
    return dialog(kind, `处理 ${dataset.name}`, "process-dataset-form", body, "创建新版本", `data-dataset-id="${e(dataset.id)}"`);
  }
  return "";
}
