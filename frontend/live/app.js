import { shell } from "../js/ui.js?v=console-4";
import { installStatusTooltip } from "../js/status-tooltip.js?v=console-4";
import { ApiClient, errorMessage } from "./api.js?v=stage13-3a";
import { btn, options, pageHeader, pageTitle, workspaceRequired } from "./components.js?v=stage13-3a";
import { renderDialog } from "./dialogs.js?v=stage13-3a";
import { loadPreferences, savePreferences } from "./preferences.js?v=stage13-3a";
import { renderAuth } from "./pages/auth.js?v=stage13-3a";
import { renderAssets, renderAssetDetail } from "./pages/assets.js?v=stage13-3a";
import { renderAudit, renderUsers } from "./pages/admin.js?v=stage13-3a";
import { renderHome, renderPending, renderSpace } from "./pages/overview.js?v=stage13-3a";
import { installEvents } from "./events.js?v=stage13-3a";
import { isComputePage, loadCompute, renderCompute } from "./compute.js?v=stage13-3a";
import { isWorkflowPage, loadWorkflow, renderWorkflow } from "./workflows.js?v=stage13-3a";
import { renderDatasetImport } from "./dataset-import.js?v=stage13-3a";
import { isManagementPage, loadManagement, renderManagement } from "./administration.js?v=stage13-3a";
import { isDataPage, loadDataWorkflow, renderDataWorkflow } from "./data-workflows.js?v=stage13-3a";

const root = document.getElementById("app");
const api = new ApiClient();
const hideTip = installStatusTooltip();
const ctx = { ui: { ...loadPreferences(localStorage), modal: null, menuOpen: false }, session: null,
  setup: {}, workspace: null, workspaces: [], templates: [], groups: [], access: {}, data: {}, error: "", loading: true, epoch: 0, origin: location.origin };
let activeRequest, toastTimer;

function route() {
  const [path, query] = (location.hash.slice(1) || "/home").split("?");
  const params = new URLSearchParams(query);
  return { path, params, page: Math.max(1, Number(params.get("page")) || 1), q: params.get("q") || "", tab: params.get("tab") || "users" };
}
function persist() { savePreferences(localStorage, ctx.ui); }
function navigate(path) { if (location.hash === `#${path}`) load(); else location.hash = `#${path}`; }
function snapshotNav() {
  const nav = root.querySelector(".sidebar-nav");
  if (nav && !root.querySelector("#shell")?.classList.contains("sidebar-collapsed")) ctx.ui.sidebarScroll = nav.scrollTop;
}
function render() {
  hideTip(); snapshotNav();
  if (!ctx.session) {
    root.innerHTML = ctx.loading ? '<div class="live-loading" role="status">正在连接平台…</div>' : renderAuth(ctx.setup, ctx.error);
    document.title = `${ctx.setup.initialized ? "登录" : "首次设置"} · 模训平台`;
    return;
  }
  let content;
  if (ctx.loading) content = '<div class="live-loading" role="status">正在加载…</div>';
  else if (ctx.error) content = pageHeader(ctx.error, "", btn("重试", "refresh"));
  else if (ctx.forbidden) content = pageHeader("无权访问") + '<a class="btn btn-secondary" href="#/home">返回工作台</a>';
  else if (isManagementPage(ctx.path)) content = renderManagement(ctx);
  else if (ctx.path === "/home") content = renderHome(ctx);
  else if (ctx.path === "/space") content = renderSpace(ctx);
  else if (ctx.path === "/datasets/new") content = renderDatasetImport(ctx);
  else if (isDataPage(ctx.path)) content = renderDataWorkflow(ctx);
  else if (ctx.path === "/admin/users") content = renderUsers(ctx);
  else if (isComputePage(ctx.path)) content = renderCompute(ctx);
  else if (isWorkflowPage(ctx.path)) content = renderWorkflow(ctx);
  else if (!ctx.workspace && (ctx.kind || ctx.path === "/admin/audit")) content = pageHeader("工作空间") + workspaceRequired(ctx);
  else if (ctx.path === "/admin/audit") content = renderAudit(ctx);
  else if (ctx.kind) content = ctx.assetId ? renderAssetDetail(ctx.kind, ctx) : renderAssets(ctx.kind, ctx);
  else content = renderPending(ctx.path);
  const workspaceControl = `<select class="select live-workspace-select" data-workspace-select aria-label="当前工作空间">${options(ctx.workspaces.length ? ctx.workspaces.map(space => [space.id, space.name]) : [["", "暂无工作空间"]], ctx.ui.workspaceId)}</select>`;
  const html = shell(ctx.path || "/home", content, pageTitle(ctx.path || "/home"), { name: ctx.session.user.display_name, role: ctx.session.user.is_admin ? "管理员" : "成员" },
    { ...ctx.ui, platformName: ctx.platform?.platform_name, environmentLabel: ["localhost", "127.0.0.1", "::1", "[::1]"].includes(location.hostname) ? "本机环境" : "服务器环境", workspaceControl });
  root.innerHTML = (ctx.ui.modal ? html.replace('id="shell"', 'id="shell" inert') : html) + renderDialog(ctx.ui.modal, ctx);
  const nav = root.querySelector(".sidebar-nav");
  if (nav) nav.scrollTop = ctx.ui.sidebarScroll;
  root.querySelector("#shell")?.classList.toggle("menu-open", ctx.ui.menuOpen);
  document.body.classList.toggle("modal-open", !!ctx.ui.modal);
  if (ctx.ui.modal) root.querySelector('[role="dialog"] input:not([readonly]),[role="dialog"] select,[role="dialog"] button')?.focus({ preventScroll: true });
  document.title = `${root.querySelector(".page-heading h1")?.textContent || "工作台"} · 模训平台`;
}

async function load() {
  snapshotNav(); persist();
  const epoch = ++ctx.epoch;
  activeRequest?.abort(); activeRequest = new AbortController();
  const signal = activeRequest.signal;
  const current = route(); Object.assign(ctx, current, { loading: true, error: "", forbidden: false, data: {} });
  ctx.ui.modal = null;
  if (ctx.session) render();
  try {
    let session;
    try { session = (await api.request("/auth/session", { signal, quietAuth: true })).data; }
    catch (error) { if (error.status !== 401) throw error; }
    if (epoch !== ctx.epoch) return;
    if (ctx.session?.user.id !== session?.user.id) { ctx.resourceConnection = null; ctx.generatedKey = null; ctx.generatedInvite = null; ctx.pendingCall = null; ctx.callResult = null; ctx.wizard = null; ctx.importDraft = null; ctx.annotationDrafts = null; ctx.dataChoices = null; }
    ctx.session = session || null;
    if (!session) {
      api.csrf = "";
      const [setup, branding] = await Promise.all([api.request("/setup", { signal }), api.request("/platform-info", { signal })]);
      ctx.setup = { ...setup.data, ...branding.data, registration: current.path === "/register", invitation: current.params.get("invitation") || "" };
      if (epoch !== ctx.epoch) return;
      if (current.path !== "/register") { history.replaceState(null, "", "#/login"); ctx.path = "/login"; }
      ctx.loading = false; render(); return;
    }
    if (["/login", "/setup", "/register"].includes(ctx.path)) { history.replaceState(null, "", "#/home"); ctx.path = "/home"; }
    const [workspaces, templates, platform] = await Promise.all([api.all("/workspaces", signal), api.request("/trainer-templates", { signal }), api.request("/platform-info", { signal })]);
    if (epoch !== ctx.epoch) return;
    ctx.workspaces = workspaces; ctx.templates = templates.data; ctx.platform = platform.data;
    ctx.workspace = workspaces.find(space => space.id === (current.params.get("workspace") || ctx.ui.workspaceId)) || workspaces[0] || null;
    ctx.ui.workspaceId = ctx.workspace?.id || ""; persist();
    ctx.access = ctx.workspace ? (await api.request(`/workspaces/${ctx.workspace.id}/access`, { signal })).data : { ...session.access, role: "member" };
    if (epoch !== ctx.epoch) return;
    ctx.kind = ctx.path.startsWith("/models") || ctx.path === "/admin/models" ? "models" : ctx.path.startsWith("/datasets") || ctx.path === "/admin/data" ? "datasets" : null;
    ctx.assetId = ctx.path.match(/^\/(models|datasets)\/([^/]+)$/)?.[2] || "";
    const adminPage = ctx.path.startsWith("/admin/");
    const managementAction = { "/admin/stats": "audit.read", "/admin/settings": "settings.manage", "/admin/audit": "audit.read", "/admin/data": "datasets.read", "/admin/models": "models.read", "/admin/jobs": ctx.params.get("job_kind") === "service" || !session.access.actions.includes("training.read") ? "services.read" : "training.read" }[ctx.path];
    const needed = managementAction || (isDataPage(ctx.path) ? "datasets.read" : ctx.path === "/train/new" ? "training.write" : ctx.path === "/datasets/new" ? "datasets.write" : ctx.path === "/admin/users" ? (ctx.tab === "groups" ? "groups.manage" : "users.manage") : isComputePage(ctx.path) ? "resources.read" : ["/services", "/api-keys"].includes(ctx.path) ? "services.read" : ["/projects", "/runs", "/evaluation"].includes(ctx.path) ? "training.read" : ctx.kind ? `${ctx.kind}.read` : "");
    const policy = ctx.path === "/admin/users" ? session.access : ctx.access;
    ctx.forbidden = (adminPage && !session.user.is_admin) || !!(needed && !policy.actions.includes(needed));
    let data = {};
    const query = `page=${ctx.page}&page_size=20&q=${encodeURIComponent(ctx.q)}`;
    const base = ctx.workspace ? `/workspaces/${ctx.workspace.id}` : "";
    if (!ctx.forbidden && isManagementPage(ctx.path)) {
      data = await loadManagement(api, ctx, signal);
    } else if (!ctx.forbidden && isDataPage(ctx.path)) {
      data = await loadDataWorkflow(api, ctx, signal);
    } else if (!ctx.forbidden && ctx.workspace && ctx.path === "/datasets/new") {
      const target = ctx.params.get("dataset");
      data = target ? { importTarget: (await api.request(`${base}/datasets/${encodeURIComponent(target)}`, { signal })).data } : {};
    } else if (!ctx.forbidden && isComputePage(ctx.path)) {
      data = await loadCompute(api, ctx, signal);
    } else if (!ctx.forbidden && isWorkflowPage(ctx.path)) {
      data = await loadWorkflow(api, ctx, signal);
    } else if (!ctx.forbidden && ctx.path === "/admin/users") {
      if (session.access.actions.includes("groups.manage")) ctx.groups = await api.all("/admin/groups", signal); else ctx.groups = [];
      const filters = new URLSearchParams();
      for (const key of ["group_id", "user_status"]) if (ctx.params.get(key) && ctx.tab !== "groups") filters.set(key, ctx.params.get(key));
      data = await api.request(`/admin/${ctx.tab === "groups" ? "groups" : "users"}?${query}&${filters}`, { signal });
    } else if (!ctx.forbidden && ctx.workspace && ctx.kind) {
      if (ctx.assetId) {
        const [item, versions] = await Promise.all([api.request(`${base}/${ctx.kind}/${ctx.assetId}`, { signal }), api.request(`${base}/${ctx.kind}/${ctx.assetId}/versions?page=${ctx.page}&page_size=20`, { signal })]);
        data = { item: item.data, versions };
      } else {
        const catalog = !ctx.path.startsWith("/admin/");
        const filters = new URLSearchParams();
        for (const key of ["task_type", ...(ctx.kind === "models" ? ["category"] : [])]) if (ctx.params.get(key)) filters.set(key, ctx.params.get(key));
        data = await api.request(`${base}/${catalog ? ctx.kind === "models" ? "model-catalog" : "dataset-catalog" : ctx.kind}?${query}&${filters}`, { signal });
      }
    } else if (!ctx.forbidden && ctx.workspace && ctx.path === "/space" && ctx.access.actions.includes("members.manage")) {
      data.members = await api.request(`${base}/members?page=${ctx.page}&page_size=20`, { signal });
    } else if (!ctx.forbidden && ctx.workspace && ctx.path === "/admin/audit") {
      data = await api.request(`${base}/audit?page=${ctx.page}&page_size=20`, { signal });
    } else if (!ctx.forbidden && ctx.workspace && ["/home", "/admin/stats"].includes(ctx.path)) {
      data = (await api.request(`${base}/overview`, { signal })).data;
    }
    if (epoch !== ctx.epoch) return;
    ctx.data = data; ctx.loading = false; render();
  } catch (error) {
    if (epoch !== ctx.epoch || error.name === "AbortError") return;
    ctx.loading = false; ctx.error = errorMessage(error); render();
  }
}

function toast(message) {
  clearTimeout(toastTimer); document.getElementById("live-toast")?.remove();
  const element = document.createElement("div"); element.id = "live-toast"; element.className = "live-toast"; element.role = "status"; element.textContent = message; document.body.append(element);
  toastTimer = setTimeout(() => element.remove(), 5000);
}
function openModal(kind, item) {
  clearTimeout(toastTimer); document.getElementById("live-toast")?.remove();
  ctx.returnFocus = { action: document.activeElement?.dataset.action, id: document.activeElement?.dataset.id };
  ctx.ui.modal = { kind, item: item ? structuredClone(item) : {}, workspaceId: ctx.workspace?.id };
  render();
}
function closeModal() {
  ctx.ui.modal = null; render();
  const target = ctx.returnFocus;
  if (target?.action) document.querySelector(`[data-action="${CSS.escape(target.action)}"]${target.id ? `[data-id="${CSS.escape(target.id)}"]` : ""}`)?.focus({ preventScroll: true });
}
api.onExpired = () => { ctx.session = null; ctx.ui.modal = null; ctx.resourceConnection = null; ctx.generatedKey = null; ctx.generatedInvite = null; ctx.pendingCall = null; ctx.callResult = null; ctx.wizard = null; ctx.importDraft = null; ctx.annotationDrafts = null; ctx.dataChoices = null; document.body.classList.remove("modal-open"); navigate("/login"); };
installEvents({ api, ctx, load, render, persist, navigate, toast, openModal, closeModal });
window.addEventListener("hashchange", () => { ctx.ui.menuOpen = false; load(); });
render(); load();
let refreshing = false;
setInterval(async () => {
  const editing = ["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement?.tagName);
  if (refreshing || !ctx.session || ctx.loading || ctx.ui.modal || editing || isManagementPage(ctx.path) || ctx.path === "/train/new" || !(isComputePage(ctx.path) || isWorkflowPage(ctx.path) || ctx.path.startsWith("/data-operations")) || ctx.forbidden) return;
  refreshing = true; const epoch = ctx.epoch;
  try {
    const session = (await api.request("/auth/session")).data;
    if (epoch !== ctx.epoch || ctx.ui.modal) return;
    if (session.user.id !== ctx.session?.user.id || JSON.stringify(session.access) !== JSON.stringify(ctx.session.access)) { await load(); return; }
    if (ctx.pendingCall) {
      const pending = ctx.pendingCall;
      const call = (await api.request(`/workspaces/${pending.workspaceId}/calls/${pending.id}`)).data;
      ctx.callResult = call.status === "pending" ? { ...call, result: { 状态: "等待推理" } } : call;
      if (call.status !== "pending") ctx.pendingCall = null;
    }
    const data = isDataPage(ctx.path) ? await loadDataWorkflow(api, ctx) : isComputePage(ctx.path) ? await loadCompute(api, ctx) : await loadWorkflow(api, ctx);
    const access = ctx.workspace ? (await api.request(`/workspaces/${ctx.workspace.id}/access`)).data : ctx.access;
    if (epoch === ctx.epoch && !ctx.ui.modal && !["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement?.tagName)) { ctx.data = data; ctx.access = access; ctx.error = ""; render(); }
  } catch (error) {
    if (epoch === ctx.epoch && !ctx.ui.modal) { ctx.error = errorMessage(error); render(); }
  } finally { refreshing = false; }
}, 3000);
