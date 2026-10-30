import { SEED_STATE, taskById } from "./data.js?v=console-4";

const KEY = "model-training-demo-v1";
const clone = value => JSON.parse(JSON.stringify(value));

function load() {
  try {
    const saved = JSON.parse(localStorage.getItem(KEY));
    if (saved && Array.isArray(saved.datasets) && Array.isArray(saved.runs)) {
      for (const key of ["groups", "apiKeys", "nodes", "annotations", "augmentations"]) saved[key] ||= clone(SEED_STATE[key]);
      saved.settings ||= clone(SEED_STATE.settings);
      saved.users ||= clone(SEED_STATE.users);
      saved.users.forEach(user => {
        user.groupId ||= user.role === "管理员" ? "group-admin" : user.role === "只读" ? "group-viewer" : "group-dev";
        user.grants ||= []; user.denies ||= []; user.quota ||= {};
      });
      return saved;
    }
  } catch { /* 浏览器禁用本地存储时仍可演示。 */ }
  return clone(SEED_STATE);
}

let state = load();
export const getState = () => state;

function save() {
  try { localStorage.setItem(KEY, JSON.stringify(state)); } catch { /* 本次会话仍可继续使用。 */ }
}

function id(prefix) { return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`; }
function now() {
  const date = new Date();
  return `${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")} ${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
}
function audit(action, target) {
  const current = state.users.find(user => user.id === getSessionUserId());
  state.audit.unshift({ time: now(), actor: current?.name || "演示用户", action, target, result: "成功" });
}

const SESSION_KEY = "model-training-demo-session";
export function getSessionUserId() { try { return sessionStorage.getItem(SESSION_KEY); } catch { return null; } }
export function setSessionUserId(userId) { try { if (userId) sessionStorage.setItem(SESSION_KEY, userId); else sessionStorage.removeItem(SESSION_KEY); } catch { /* 会话存储不可用时不保留登录。 */ } }
export function currentUser() { return state.users.find(user => user.id === getSessionUserId() && user.status === "启用"); }
export function findAccount(account) { return state.users.find(user => user.account.toLowerCase() === String(account).toLowerCase()); }
export function registerUser({ name, account, salt, passwordHash }) {
  if (findAccount(account)) return null;
  const user = { id: id("user"), name, account, role: "开发者", groupId: state.settings.defaultGroupId, status: "启用", grants: [], denies: [], quota: {}, salt, passwordHash };
  state.users.push(user); audit("注册用户", name); save(); return user;
}
export function addUser({ name, account, groupId, salt, passwordHash }) {
  if (findAccount(account)) return null;
  if (!state.groups.some(group => group.id === groupId && group.id !== "group-admin")) return null;
  const user = { id: id("user"), name, account, role: groupId === "group-viewer" ? "只读" : "开发者", groupId, status: "启用", grants: [], denies: [], quota: {}, salt, passwordHash };
  state.users.push(user); audit("创建用户", name); save(); return user;
}

export const PERMISSIONS = [
  ["datasets.read", "查看数据集"], ["datasets.write", "管理数据集"], ["train.submit", "提交训练"],
  ["models.manage", "管理模型"], ["services.deploy", "部署服务"], ["keys.manage", "管理 API KEY"], ["resources.view", "查看资源"]
];
export function effectiveAccess(user, source = state) {
  const group = source.groups.find(item => item.id === user.groupId);
  const permissions = new Set([...(group?.permissions || []), ...(user.grants || [])]);
  (user.denies || []).forEach(item => permissions.delete(item));
  const quota = Object.fromEntries(["gpu", "jobs"].map(key => [key, Math.min(Number(group?.quota?.[key] ?? 0), Number(user.quota?.[key] ?? Infinity))]));
  return { permissions, quota, group };
}
export function setUserAccess(userId, { groupId, modes, gpu, jobs }) {
  const user = state.users.find(item => item.id === userId && item.role !== "管理员");
  if (!user) return false;
  if (groupId && state.groups.some(item => item.id === groupId && item.id !== "group-admin")) { user.groupId = groupId; user.role = groupId === "group-viewer" ? "只读" : "开发者"; }
  if (modes) for (const [permission, mode] of Object.entries(modes)) if (PERMISSIONS.some(([key]) => key === permission)) {
    user.grants = user.grants.filter(item => item !== permission);
    user.denies = user.denies.filter(item => item !== permission);
    if (mode === "allow") user.grants.push(permission);
    if (mode === "deny") user.denies.push(permission);
  }
  if (gpu !== undefined) user.quota.gpu = Number(gpu);
  if (jobs !== undefined) user.quota.jobs = Number(jobs);
  audit("调整用户权限", user.name); save(); return true;
}
export function addGroup({ name, permissions, gpu, jobs }) {
  const group = { id: id("group"), name, permissions, quota: { gpu: Number(gpu), jobs: Number(jobs) } };
  state.groups.push(group); audit("创建用户组", name); save(); return group;
}
export function updateGroup(groupId, { permissions, gpu, jobs }) {
  const group = state.groups.find(item => item.id === groupId && item.id !== "group-admin");
  if (!group) return false;
  group.permissions = permissions; group.quota = { gpu: Number(gpu), jobs: Number(jobs) };
  audit("调整用户组", group.name); save(); return true;
}
export function addApiKey(name, scope) {
  const raw = `demo_${Math.random().toString(36).slice(2, 10)}${Math.random().toString(36).slice(2, 10)}`;
  const key = { id: id("key"), name, scope, ownerId: getSessionUserId(), preview: `${raw.slice(0, 9)}••••${raw.slice(-4)}`, created: now(), status: "启用" };
  state.apiKeys.unshift(key); audit("创建演示 API KEY", name); save(); return { key, raw };
}
export function revokeApiKey(keyId) {
  const key = state.apiKeys.find(item => item.id === keyId && item.ownerId === getSessionUserId());
  if (!key) return false;
  key.status = "停用"; audit("停用演示 API KEY", key.name); save(); return true;
}
export function addNode({ name, address, profile }) {
  const specs = profile === "a100" ? { gpus: "A100 × 1", cpu: "48 核", memory: "256 GB" } : { gpus: "RTX 4090 × 2", cpu: "32 核", memory: "128 GB" };
  const node = { id: id("node"), name, address, status: "待探测", ...specs, demo: true };
  state.nodes.unshift(node); audit("登记演示节点", name); save(); return node;
}
export function probeNode(nodeId) {
  const node = state.nodes.find(item => item.id === nodeId && item.demo);
  if (!node) return false;
  node.status = "已接入"; audit("模拟探测节点", node.name); save(); return true;
}
export function addAnnotation(datasetId, count, label) {
  const item = { id: id("annotation"), datasetId, count: Number(count), label, status: "已保存", updated: now() };
  state.annotations.unshift(item); audit("创建标注批次", label); save(); return item;
}
export function addAugmentation(datasetId, method, multiplier) {
  const item = { id: id("augmentation"), datasetId, method, multiplier: Number(multiplier), status: "已完成", updated: now() };
  state.augmentations.unshift(item); audit("创建增强方案", method); save(); return item;
}
export function updateSettings(values) { Object.assign(state.settings, values); audit("更新演示设置", "平台设置"); save(); }

export function addDataset({ name, taskId, files, count, sample }) {
  const task = taskById(taskId);
  const dataset = {
    id: id("ds"), name: name.trim(), type: task.group, taskId, format: task.format,
    count: Number(count) || files.length, size: files.length ? `${files.length} 个文件` : "待上传",
    version: 1, status: "待处理", updated: now().slice(0, 5), sample: sample || "待检查样本", files
  };
  state.datasets.unshift(dataset);
  audit("登记数据集", dataset.name);
  save();
  return dataset;
}

export function processDataset(datasetId, options) {
  const dataset = state.datasets.find(item => item.id === datasetId);
  if (!dataset) return;
  dataset.status = "可训练";
  dataset.version += 1;
  dataset.updated = now().slice(0, 5);
  dataset.processing = options;
  audit("处理数据集", dataset.name);
  save();
}

export function addRun(draft) {
  let project = state.projects.find(item => item.id === draft.projectId);
  if (!project) {
    project = { id: id("pr"), name: draft.projectName.trim(), taskId: draft.taskId, description: "", updated: now().slice(0, 5) };
    state.projects.unshift(project);
  }
  const task = taskById(draft.taskId);
  const run = {
    id: id("run"), name: draft.name.trim(), projectId: project.id, datasetId: draft.datasetId,
    taskId: draft.taskId, modelId: draft.modelId, status: "排队中", progress: 0,
    metric: task.metric, score: "—", duration: "—", started: now(), gpu: draft.gpu,
    epochs: Number(draft.epochs), batch: Number(draft.batch), lr: Number(draft.lr),
    ...(draft.modelId.startsWith("qwen25-") ? { finetune: draft.finetune, loraRank: Number(draft.loraRank), maxLength: Number(draft.maxLength) } : {}),
    ownerId: getSessionUserId(), demo: true
  };
  state.runs.unshift(run);
  audit("创建演示训练", run.name);
  save();
  return run;
}

export function advanceRun(runId) {
  const run = state.runs.find(item => item.id === runId);
  if (!run || !run.demo) return;
  if (run.status === "排队中") { run.status = "运行中"; run.progress = 46; run.duration = "8 分钟"; run.score = "0.684"; }
  else if (run.status === "运行中") { run.status = "已完成"; run.progress = 100; run.duration = "18 分钟"; run.score = "0.892"; }
  else return;
  audit("推进演示状态", run.name);
  save();
}

export function addService({ name, runId, resource }) {
  const service = { id: id("svc"), name: name.trim(), runId, status: "运行中", version: "v1", resource, calls: 0, created: now().slice(0, 5), history: [], demo: true };
  state.services.unshift(service);
  audit("创建演示服务", service.name);
  save();
  return service;
}

export function recordServiceTest(serviceId) {
  const service = state.services.find(item => item.id === serviceId);
  if (!service) return;
  service.calls += 1;
  service.history ||= [];
  service.history.unshift({ time: now(), result: "已完成", latency: "184 ms", source: "在线测试" });
  save();
}

export function toggleUser(userId) {
  const user = state.users.find(item => item.id === userId);
  if (!user || user.role === "管理员") return;
  user.status = user.status === "启用" ? "停用" : "启用";
  audit("调整用户状态", user.name);
  save();
}

export function resetDemo() {
  state = clone(SEED_STATE);
  save();
}
