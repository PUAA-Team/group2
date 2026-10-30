import { TASKS, taskById } from "./data.js?v=console-4";
import { addAnnotation, addApiKey, addAugmentation, addDataset, addGroup, addNode, addRun, addService, advanceRun, effectiveAccess, getState, PERMISSIONS, probeNode, processDataset, recordServiceTest, revokeApiKey, setUserAccess, toggleUser, updateGroup, updateSettings } from "./state.js?v=console-4";
import { createUser, currentUser, login, logout, register } from "./auth.js?v=console-4";
import { emptyState, linkButton, NAV_GROUPS, shell } from "./ui.js?v=console-4";
import { renderModal } from "./modals.js?v=console-4";
import { renderAuth } from "./pages/auth.js?v=console-4";
import { renderHome } from "./pages/home.js?v=console-4";
import { renderSpace, renderMonitor } from "./pages/workspace.js?v=console-4";
import { renderDatasetDetail, renderDatasetList, renderDatasetNew } from "./pages/datasets.js?v=console-4";
import { renderAnnotation, renderAugmentation } from "./pages/data-tools.js?v=console-4";
import { renderProjectDetail, renderProjectList } from "./pages/projects.js?v=console-4";
import { renderRunDetail, renderRunList, renderTrainWizard } from "./pages/training.js?v=console-4";
import { renderModelDetail, renderModelList } from "./pages/models.js?v=console-4";
import { renderEvaluation } from "./pages/evaluation.js?v=console-4";
import { renderServiceDetail, renderServiceList } from "./pages/services.js?v=console-4";
import { renderApiKeys } from "./pages/api-keys.js?v=console-4";
import { renderAudit, renderResources, renderUsers } from "./pages/admin.js?v=console-4";
import { renderAdminData, renderAdminJobs, renderAdminModels, renderSettings, renderStats } from "./pages/admin-overview.js?v=console-4";
import { JOIN_COMMAND } from "./pages/admin-resources.js?v=console-4";
import { installStatusTooltip } from "./status-tooltip.js?v=console-4";

const root = document.getElementById("app");
const NAV_KEY = "model-training-demo-nav";
const hideStatusTooltip = installStatusTooltip();
function loadNavOpen() {
  try {
    const saved = JSON.parse(localStorage.getItem(NAV_KEY)) || {};
    return Object.fromEntries(NAV_GROUPS.map(group => [group.id, saved[group.id] !== false]));
  } catch { return Object.fromEntries(NAV_GROUPS.map(group => [group.id, true])); }
}
const ui = { search: "", datasetType: "全部类型", runStatus: "全部状态", modelTab: "prebuilt", modelGroup: "全部类型", wizardGroup: "图像", wizardStep: 0, wizardError: "", datasetFiles: [], navOpen: loadNavOpen(), sidebarCollapsed: false, sidebarScroll: 0, modal: null, resourceTab: "devices", adminUsersTab: "users", authError: "" };
let draft = null;
let currentRoute = "";
let toastTimer = null;

function routeInfo() {
  const raw = location.hash.startsWith("#") ? location.hash.slice(1) : "/home";
  const [path, query = ""] = raw.split("?");
  return { path: path || "/home", params: new URLSearchParams(query), raw };
}

function makeDraft(params) {
  const state = getState();
  const dataset = state.datasets.find(item => item.id === params.get("dataset"));
  const project = state.projects.find(item => item.id === params.get("project")) || state.projects[0];
  const task = taskById(params.get("task") || dataset?.taskId || project?.taskId) || TASKS[0];
  const model = task.models.find(item => item.id === params.get("model")) || task.models[0];
  const compatible = state.datasets.find(item => item.taskId === task.id && item.status === "可训练");
  return { projectId: params.has("project") ? project.id : "new", projectName: "", name: "", taskId: task.id, modelId: model.id,
    datasetId: dataset?.id || compatible?.id || "", gpu: task.group === "表格" ? "CPU 队列" : "GPU 02",
    finetune: "LoRA", loraRank: 8, maxLength: 1024,
    ...Object.fromEntries(task.params.map(param => [param.name, param.value])) };
}

function render() {
  hideStatusTooltip();
  const currentNav = document.querySelector(".sidebar-nav");
  if (currentNav && !document.getElementById("shell")?.classList.contains("sidebar-collapsed")) ui.sidebarScroll = currentNav.scrollTop;
  const previousModal = document.getElementById("demo-modal")?.dataset.modal;
  const { path, params, raw } = routeInfo();
  const menuOpen = document.getElementById("shell")?.classList.contains("menu-open");
  const preserveMenu = menuOpen && raw === currentRoute;
  const state = getState();
  const user = currentUser();
  if (!user && !["/login", "/register"].includes(path)) { location.hash = "#/login"; return; }
  if (user && ["/login", "/register"].includes(path)) { location.hash = "#/home"; return; }
  if (["/login", "/register"].includes(path)) {
    ui.modal = null;
    root.innerHTML = renderAuth(path.slice(1), ui.authError);
    document.title = `${path === "/login" ? "登录" : "注册"} · 模训平台`;
    currentRoute = raw;
    return;
  }
  if (raw !== currentRoute) {
    ui.modal = null;
    if (path !== currentRoute.split("?")[0]) { ui.search = ""; ui.serviceResult = ""; }
    if (path !== "/api-keys") ui.newKey = "";
    if (path === "/train/new") { draft = makeDraft(params); ui.wizardStep = 0; ui.wizardError = ""; ui.wizardGroup = taskById(draft.taskId)?.group || "图像"; }
    if (path === "/datasets/new") { ui.datasetTask = params.get("task") || TASKS[0].id; ui.datasetFiles = []; ui.datasetPreview = ""; ui.datasetName = ""; ui.datasetCount = ""; }
    if (path === "/models") ui.modelTab = params.get("tab") || "prebuilt";
    if (path === "/services/new") ui.modal = { kind: "service-new", id: params.get("run") || "" };
    currentRoute = raw;
  }
  let content, title;
  const access = effectiveAccess(user, state).permissions;
  const required = path === "/datasets/new" || path === "/annotation" || path === "/augmentation" ? "datasets.write"
    : path.startsWith("/datasets") ? "datasets.read"
    : path.startsWith("/train") || path.startsWith("/projects") || path.startsWith("/runs") ? "train.submit"
    : path.startsWith("/models") || path === "/evaluation" ? "models.manage"
    : path.startsWith("/services") ? "services.deploy" : path === "/api-keys" ? "keys.manage" : path === "/monitor" ? "resources.view" : "";
  if (path.startsWith("/admin/") && user.role !== "管理员") { content = emptyState("无权访问", "此页面仅对管理员开放。", linkButton("返回工作台", "#/home")); title = "无权访问"; }
  else if (required && !access.has(required)) { content = emptyState("无权访问", "请联系管理员调整权限。", linkButton("返回工作台", "#/home")); title = "无权访问"; }
  else if (path === "/home") { content = renderHome(state, user, access); title = "工作台"; }
  else if (path === "/space") { content = renderSpace(state, user); title = "用户空间"; }
  else if (path === "/monitor") { content = renderMonitor(state); title = "资源监控"; }
  else if (path === "/datasets") { content = renderDatasetList(state, ui); title = "数据集"; }
  else if (path === "/datasets/new") { content = renderDatasetNew(ui); title = "导入数据集"; }
  else if (path.startsWith("/datasets/")) { content = renderDatasetDetail(state, path.split("/")[2]); title = "数据集详情"; }
  else if (path === "/annotation") { content = renderAnnotation(state); title = "在线标注"; }
  else if (path === "/augmentation") { content = renderAugmentation(state, ui); title = "数据增强"; }
  else if (path === "/projects") { content = renderProjectList(state, ui); title = "训练项目"; }
  else if (path.startsWith("/projects/")) { content = renderProjectDetail(state, path.split("/")[2]); title = "项目详情"; }
  else if (path === "/train/new") { if (!draft) draft = makeDraft(params); content = renderTrainWizard(state, draft, ui.wizardStep, ui); title = "新建训练"; }
  else if (path === "/runs") { content = renderRunList(state, ui); title = "训练任务"; }
  else if (path.startsWith("/runs/")) { content = renderRunDetail(state, path.split("/")[2], params.get("tab") || "overview"); title = "任务详情"; }
  else if (path === "/models") { content = renderModelList(state, ui); title = "模型仓库"; }
  else if (path.startsWith("/models/")) { content = renderModelDetail(state, path.split("/")[2]); title = "模型详情"; }
  else if (path === "/evaluation") { content = renderEvaluation(state, ui); title = "模型评估"; }
  else if (path === "/services") { content = renderServiceList(state); title = "在线服务"; }
  else if (path === "/services/new") { content = renderServiceList(state); title = "在线服务"; }
  else if (path.startsWith("/services/")) { content = renderServiceDetail(state, path.split("/")[2], ui); title = "服务详情"; }
  else if (path === "/api-keys") { content = renderApiKeys(state, user, ui); title = "API KEY管理"; }
  else if (path === "/admin/stats") { content = renderStats(state); title = "统计面板"; }
  else if (path === "/admin/resources") { content = renderResources(state, ui); title = "资源管理"; }
  else if (path === "/admin/data") { content = renderAdminData(state); title = "数据管理"; }
  else if (path === "/admin/models") { content = renderAdminModels(state); title = "模型管理"; }
  else if (path === "/admin/jobs") { content = renderAdminJobs(state); title = "作业管理"; }
  else if (path === "/admin/users") { content = renderUsers(state, ui); title = "用户管理"; }
  else if (path === "/admin/audit") { content = renderAudit(state); title = "操作记录"; }
  else if (path === "/admin/settings") { content = renderSettings(state); title = "系统设置"; }
  else { content = emptyState("页面不存在", "请从左侧导航选择页面。", linkButton("返回工作台", "#/home", "primary")); title = "页面不存在"; }
  root.innerHTML = shell(path, content, title, user, ui, access) + renderModal(ui.modal, state, ui);
  if (preserveMenu) document.getElementById("shell")?.classList.add("menu-open");
  const sidebarNav = document.querySelector(".sidebar-nav");
  if (sidebarNav) sidebarNav.scrollTop = ui.sidebarScroll;
  if (ui.modal && previousModal !== ui.modal.kind) document.querySelector("#demo-modal [autofocus], #demo-modal input, #demo-modal select")?.focus();
  document.title = `${title} · 模训平台`;
}

function notify(message) {
  document.querySelector(".toast")?.remove();
  const element = document.createElement("div");
  element.className = "toast";
  element.setAttribute("role", "status");
  element.textContent = message;
  document.body.append(element);
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => element.remove(), 3200);
}

function changeTask(taskId) {
  const task = taskById(taskId);
  if (!task) return;
  draft.taskId = task.id;
  draft.modelId = task.models[0].id;
  draft.datasetId = getState().datasets.find(item => item.taskId === task.id && item.status === "可训练")?.id || "";
  draft.gpu = task.group === "表格" ? "CPU 队列" : "GPU 02";
  task.params.forEach(param => { draft[param.name] = param.value; });
  if (draft.projectId !== "new" && getState().projects.find(item => item.id === draft.projectId)?.taskId !== task.id) draft.projectId = "new";
  ui.wizardGroup = task.group;
  ui.wizardError = "";
  render();
}

function readVisibleDraft() {
  if (ui.wizardStep === 0) {
    draft.name = document.getElementById("run-name")?.value.trim() || "";
    if (draft.projectId === "new") draft.projectName = document.getElementById("project-name")?.value.trim() || "";
  }
  if (ui.wizardStep === 2) {
    for (const key of ["epochs", "batch", "lr", "finetune", "loraRank", "maxLength"]) draft[key] = document.querySelector(`[name="${key}"]`)?.value || draft[key];
  }
}

function validateStep(step) {
  if (step === 0) {
    if (!draft.name) return "请填写训练任务名称。";
    if (draft.projectId === "new" && !draft.projectName) return "请填写项目名称。";
    if (!draft.taskId || !draft.modelId) return "请选择任务和模型。";
  }
  if (step === 1 && !draft.datasetId) return "请选择已处理完成的数据集。";
  if (step === 2) {
    const task = taskById(draft.taskId);
    const invalid = task.params.find(param => !Number.isFinite(Number(draft[param.name])) || Number(draft[param.name]) < param.min || Number(draft[param.name]) > param.max);
    if (invalid) return `${invalid.label}须在 ${invalid.min}–${invalid.max} 之间。`;
    if (!draft.gpu) return "请选择计算资源。";
    if (draft.modelId?.startsWith("qwen25-")) {
      if (draft.gpu === "CPU 队列") return "此演示模型请选择 GPU 资源。";
      if (Number(draft.maxLength) < 128 || Number(draft.maxLength) > 4096 || Number(draft.loraRank) < 4 || Number(draft.loraRank) > 64) return "序列长度须为 128–4096，LoRA 秩须为 4–64。";
    }
  }
  return "";
}

function download(name, content, mime = "text/plain;charset=utf-8") {
  const url = URL.createObjectURL(new Blob([content], { type: mime }));
  const anchor = document.createElement("a");
  anchor.href = url; anchor.download = name; anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

document.addEventListener("click", event => {
  const button = event.target.closest("[data-action]");
  if (!button) return;
  const action = button.dataset.action;
  if (action === "open-menu") { document.getElementById("shell")?.classList.add("menu-open"); return; }
  if (action === "close-menu") { document.getElementById("shell")?.classList.remove("menu-open"); return; }
  if (action === "collapse-sidebar") { ui.sidebarCollapsed = !ui.sidebarCollapsed; render(); return; }
  if (action === "toggle-nav") { if (ui.sidebarCollapsed && window.innerWidth >= 1024) { ui.sidebarCollapsed = false; render(); return; } const group = button.dataset.group; ui.navOpen[group] = button.getAttribute("aria-expanded") !== "true"; try { localStorage.setItem(NAV_KEY, JSON.stringify(ui.navOpen)); } catch { /* 仍保留本次会话状态。 */ } render(); return; }
  if (action === "open-modal") { ui.modal = { kind: button.dataset.modal, id: button.dataset.id || "" }; render(); return; }
  if (action === "close-modal") { ui.modal = null; if (routeInfo().path === "/services/new") location.hash = "#/services"; else render(); return; }
  if (action === "logout") { logout(); ui.authError = ""; location.hash = "#/login"; return; }
  if (action === "toggle-password") { const input = document.getElementById("auth-password"); if (input) input.type = input.type === "password" ? "text" : "password"; return; }
  if (action === "demo-login") { login(button.dataset.account, button.dataset.password).then(result => { if (result.ok) location.hash = "#/home"; else { ui.authError = result.message; render(); } }); return; }
  if (action === "resource-tab") { ui.resourceTab = button.dataset.tab; render(); return; }
  if (action === "admin-users-tab") { ui.adminUsersTab = button.dataset.tab; render(); return; }
  if (action === "probe-node") { probeNode(button.dataset.nodeId); ui.resourceTab = "nodes"; render(); notify("已生成模拟探测结果"); return; }
  if (action === "copy-join-command") { navigator.clipboard.writeText(JOIN_COMMAND).then(() => notify("已复制不可执行的示意命令"), () => notify("复制失败，请手动选择命令文本")); return; }
  if (action === "copy-key") { navigator.clipboard.writeText(ui.newKey || "").then(() => notify("已复制演示密钥"), () => notify("复制失败，请手动选择密钥")); return; }
  if (action === "revoke-key") { revokeApiKey(button.dataset.keyId); render(); notify("演示密钥已停用"); return; }
  if (action === "download-template") {
    const task = taskById(button.dataset.taskId);
    if (task) download(`${task.id}-template.${task.template.trim().startsWith("{") ? "json" : "csv"}`, task.template);
    return;
  }
  if (action === "wizard-group") { changeTask(TASKS.find(item => item.group === button.dataset.group)?.id); return; }
  if (action === "wizard-back") { if (ui.wizardStep > 0) { readVisibleDraft(); ui.wizardStep--; ui.wizardError = ""; render(); } return; }
  if (action === "wizard-next") {
    readVisibleDraft(); ui.wizardError = validateStep(ui.wizardStep);
    if (!ui.wizardError) ui.wizardStep++;
    render(); window.scrollTo({ top: 0, behavior: "smooth" }); return;
  }
  if (action === "wizard-submit") {
    readVisibleDraft();
    for (let step = 0; step < 3; step++) { const error = validateStep(step); if (error) { ui.wizardStep = step; ui.wizardError = error; render(); return; } }
    const run = addRun(draft); location.hash = `#/runs/${run.id}`; notify("演示任务已创建"); return;
  }
  if (action === "advance-run") { advanceRun(button.dataset.runId); render(); notify("演示状态已更新"); return; }
  if (action === "download-logs") {
    const run = getState().runs.find(item => item.id === button.dataset.runId);
    if (run) download(`${run.id}.log`, `${run.name}\n状态：${run.status}\n开始时间：${run.started}\n训练轮次：${run.epochs}\n`);
    return;
  }
  if (action === "toggle-user") { toggleUser(button.dataset.userId); render(); notify("用户状态已更新"); }
});

document.addEventListener("input", event => {
  const target = event.target;
  if (target.dataset.filter === "search") {
    const position = target.selectionStart;
    ui.search = target.value; render();
    const next = document.querySelector('[data-filter="search"]');
    next?.focus(); try { next?.setSelectionRange(position, position); } catch { /* 搜索框不支持光标控制时忽略。 */ }
  }
  if (target.id === "dataset-name") ui.datasetName = target.value;
  if (target.id === "sample-count") ui.datasetCount = target.value;
  if (routeInfo().path === "/train/new" && draft && target.name && ["name", "projectName", "epochs", "batch", "lr"].includes(target.name)) draft[target.name] = target.value;
});

document.addEventListener("change", async event => {
  const target = event.target;
  if (target.hasAttribute("data-augmentation-dataset")) { ui.augmentationDataset = target.value; render(); return; }
  if (target.dataset.filter && target.dataset.filter !== "search") { ui[target.dataset.filter] = target.value; render(); return; }
  if (target.hasAttribute("data-dataset-task")) { ui.datasetTask = target.value; ui.datasetFiles = []; ui.datasetPreview = ""; render(); return; }
  if (target.hasAttribute("data-dataset-files")) {
    ui.datasetFiles = Array.from(target.files || []);
    const first = ui.datasetFiles[0];
    ui.datasetPreview = first && /\.(csv|tsv|txt|jsonl|json)$/i.test(first.name) ? (await first.text()).slice(0, 420) : "";
    render(); return;
  }
  if (routeInfo().path !== "/train/new" || !draft) return;
  if (target.hasAttribute("data-wizard-project")) {
    draft.projectId = target.value;
    if (target.value !== "new") changeTask(getState().projects.find(item => item.id === target.value)?.taskId);
    else render();
  } else if (target.hasAttribute("data-wizard-task")) changeTask(target.value);
  else if (target.hasAttribute("data-wizard-model")) { draft.modelId = target.value; render(); }
  else if (target.hasAttribute("data-wizard-dataset")) { draft.datasetId = target.value; render(); }
  else if (target.hasAttribute("data-wizard-gpu")) { draft.gpu = target.value; render(); }
});

document.addEventListener("submit", event => {
  const form = event.target;
  if (!form.id) return;
  event.preventDefault();
  const values = new FormData(form);
  if (form.id === "user-new-form") {
    createUser({ name: String(values.get("name") || "").trim(), account: String(values.get("account") || "").trim(), password: String(values.get("password") || ""), groupId: String(values.get("groupId")) }).then(result => {
      if (!result.ok) { notify(result.message); return; }
      ui.modal = null; render(); notify("用户已创建");
    });
    return;
  }
  if (form.id === "login-form") {
    login(String(values.get("account") || "").trim(), String(values.get("password") || "")).then(result => {
      if (result.ok) { ui.authError = ""; location.hash = "#/home"; }
      else { ui.authError = result.message; render(); }
    });
    return;
  }
  if (form.id === "register-form") {
    const name = String(values.get("name") || "").trim(), account = String(values.get("account") || "").trim(), password = String(values.get("password") || "");
    if (password !== values.get("confirm")) { ui.authError = "两次输入的密码不一致"; render(); return; }
    if (!getState().settings.registration) { ui.authError = "当前已关闭自主注册"; render(); return; }
    register({ name, account, password }).then(result => {
      if (result.ok) { ui.authError = ""; location.hash = "#/home"; }
      else { ui.authError = result.message; render(); }
    });
    return;
  }
  if (form.id === "annotation-form") {
    addAnnotation(String(values.get("datasetId")), values.get("count"), String(values.get("label") || "").trim());
    ui.modal = null; render(); notify("演示标注批次已保存"); return;
  }
  if (form.id === "augmentation-form") {
    const dataset = getState().datasets.find(item => item.id === values.get("datasetId"));
    const methods = { 图像: ["flip", "crop"], 文本: ["synonym", "back-translation"], 表格: ["noise"], 大语言模型: ["synonym", "back-translation"] };
    if (!methods[dataset?.type]?.includes(values.get("method"))) { notify("增强方式与数据集类型不匹配"); return; }
    addAugmentation(dataset.id, String(values.get("method")), values.get("multiplier")); ui.modal = null; render(); notify("演示增强方案已创建"); return;
  }
  if (form.id === "api-key-form") {
    const result = addApiKey(String(values.get("name") || "").trim(), String(values.get("scope")));
    ui.newKey = result.raw; ui.modal = null; render(); notify("演示密钥已创建"); return;
  }
  if (form.id === "node-form") {
    addNode({ name: String(values.get("name") || "").trim(), address: String(values.get("address") || "").trim(), profile: String(values.get("profile")) });
    ui.resourceTab = "nodes"; ui.modal = null; render(); notify("节点已登记，可模拟自动探测"); return;
  }
  if (form.id === "user-access-form") {
    const modes = Object.fromEntries(PERMISSIONS.map(([key]) => [key, String(values.get(`mode:${key}`) || "inherit")]));
    setUserAccess(form.dataset.userId, { groupId: String(values.get("groupId")), modes, gpu: values.get("gpu"), jobs: values.get("jobs") });
    ui.modal = null; render(); notify("个人权限已更新"); return;
  }
  if (form.id === "group-new-form") {
    const name = String(values.get("name") || "").trim();
    if (getState().groups.some(item => item.name === name)) { notify("用户组名称已存在"); return; }
    const group = addGroup({ name, permissions: values.getAll("permission").map(String), gpu: values.get("gpu"), jobs: values.get("jobs") });
    ui.adminGroupId = group.id; ui.modal = null; render(); notify("用户组已创建"); return;
  }
  if (form.id === "group-access-form") {
    updateGroup(form.dataset.groupId, { permissions: values.getAll("permission").map(String), gpu: values.get("gpu"), jobs: values.get("jobs") });
    ui.modal = null; render(); notify("用户组已更新"); return;
  }
  if (form.id === "settings-form") {
    updateSettings({ registration: values.has("registration"), defaultGroupId: String(values.get("defaultGroupId")), jobLimit: Number(values.get("jobLimit")), storageLimit: Number(values.get("storageLimit")) });
    ui.modal = null; render(); notify("演示设置已保存"); return;
  }
  if (form.id === "dataset-form") {
    const name = String(values.get("name") || "").trim();
    if (!name) { notify("请填写数据集名称"); return; }
    const dataset = addDataset({ name, taskId: String(values.get("taskId")), files: ui.datasetFiles.map(file => file.name), count: values.get("count"), sample: ui.datasetPreview ? "已读取本地文件预览" : "等待样本检查" });
    location.hash = `#/datasets/${dataset.id}`; notify("数据集已登记，请检查并处理"); return;
  }
  if (form.id === "process-dataset-form") {
    const options = values.getAll("process").map(String);
    processDataset(form.dataset.datasetId, [...options, `训练集 ${values.get("split")}%`]);
    ui.modal = null; render(); notify("已创建数据集演示版本"); return;
  }
  if (form.id === "service-form") {
    const name = String(values.get("name") || "").trim(), runId = String(values.get("runId") || "");
    if (!name || !runId) { notify("请填写服务名称并选择模型来源"); return; }
    const service = addService({ name, runId, resource: String(values.get("resource")) });
    location.hash = `#/services/${service.id}`; notify("演示服务已创建"); return;
  }
  if (form.id === "service-test-form") {
    const input = String(values.get("input") || "").trim();
    if (!input) { notify("请填写测试输入"); return; }
    recordServiceTest(form.dataset.serviceId);
    ui.serviceResult = JSON.stringify({ label: "演示预测", confidence: 0.92, input: input.slice(0, 80) }, null, 2);
    render(); notify("演示测试已完成");
  }
});

document.addEventListener("keydown", event => { if (event.key === "Escape" && ui.modal) { ui.modal = null; if (routeInfo().path === "/services/new") location.hash = "#/services"; else render(); } });
window.addEventListener("hashchange", () => { render(); window.scrollTo(0, 0); });
if (!location.hash) location.hash = "#/home";
render();
