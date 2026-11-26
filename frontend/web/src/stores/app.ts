import { reactive, ref } from "vue";
import { ApiClient, errorMessage } from "@/api/client";
import type { AccessPolicy, ModalState, SessionData, SetupState, UiPreferences, WorkspaceSummary } from "@/types/platform";
import { loadPreferences, savePreferences } from "@live/preferences.js";
import { installStatusTooltip } from "@live/ui/status-tooltip.js";
import { isComputePage, loadCompute } from "@live/compute.js";
import { isWorkflowPage, loadWorkflow } from "@live/workflows.js";
import { isManagementPage, loadManagement } from "@live/administration.js";
import { isDataPage, loadDataWorkflow } from "@live/data-workflows.js";
import { isAssistantPage, loadAssistant } from "@live/assistant.js";
import { installEvents } from "@live/events.js";

export const api = new ApiClient();

export interface AppContext {
  ui: UiPreferences;
  session: SessionData | null;
  setup: SetupState & Record<string, any>;
  workspace: WorkspaceSummary | null;
  workspaces: WorkspaceSummary[];
  templates: any[];
  groups: any[];
  platform?: Record<string, any>;
  access: AccessPolicy;
  data: Record<string, any>;
  error: string;
  loading: boolean;
  forbidden: boolean;
  epoch: number;
  origin: string;
  path: string;
  params: URLSearchParams;
  page: number;
  q: string;
  tab: string;
  kind: "models" | "datasets" | null;
  assetId: string;
  [key: string]: any;
}

export const ctx = reactive<AppContext>({
  ui: { ...loadPreferences(localStorage), modal: null, menuOpen: false },
  session: null,
  setup: {},
  workspace: null,
  workspaces: [],
  templates: [],
  groups: [],
  access: { actions: [], quota: { gpu_count: 0, concurrent_jobs: 0, storage_gib: 0 } },
  data: {},
  error: "",
  loading: true,
  forbidden: false,
  epoch: 0,
  origin: typeof location !== "undefined" ? location.origin : "",
  path: "/home",
  params: new URLSearchParams(),
  page: 1,
  q: "",
  tab: "users",
  kind: null,
  assetId: "",
});

// renderTick 用于通知依赖非响应式字段（如 wizard/importDraft/data 局部变更）的视图重算
export const renderTick = ref(0);
export const toastMessage = ref("");

let activeRequest: AbortController | null = null;
let toastTimer: ReturnType<typeof setTimeout> | null = null;
let initialized = false;
let refreshing = false;
let hideTip: (() => void) | null = null;

export function parseRoute() {
  const [path, query] = (location.hash.slice(1) || "/home").split("?");
  const params = new URLSearchParams(query);
  return {
    path,
    params,
    page: Math.max(1, Number(params.get("page")) || 1),
    q: params.get("q") || "",
    tab: params.get("tab") || "users",
  };
}

export function persist() {
  savePreferences(localStorage, ctx.ui);
}

export function triggerRender() {
  hideTip?.();
  renderTick.value += 1;
  if (typeof document !== "undefined") {
    document.body.classList.toggle("modal-open", !!ctx.ui.modal);
  }
}

export function toast(message: string) {
  if (toastTimer) clearTimeout(toastTimer);
  toastMessage.value = message;
  toastTimer = setTimeout(() => {
    toastMessage.value = "";
  }, 5000);
}

export function navigate(path: string) {
  if (location.hash === `#${path}`) {
    void load();
  } else {
    location.hash = `#${path}`;
  }
}

export function openModal(kind: string, item?: Record<string, any>) {
  if (toastTimer) clearTimeout(toastTimer);
  toastMessage.value = "";
  const active = document.activeElement as HTMLElement | null;
  ctx.returnFocus = { action: active?.dataset?.action, id: active?.dataset?.id };
  ctx.ui.modal = {
    kind,
    item: item ? structuredClone(item) : {},
    workspaceId: ctx.workspace?.id,
  } as ModalState;
  triggerRender();
}

export function closeModal() {
  ctx.ui.modal = null;
  triggerRender();
  const target = ctx.returnFocus;
  if (target?.action) {
    const selector = `[data-action="${CSS.escape(target.action)}"]${target.id ? `[data-id="${CSS.escape(target.id)}"]` : ""}`;
    (document.querySelector(selector) as HTMLElement | null)?.focus({ preventScroll: true });
  }
}

function clearVolatileState() {
  ctx.resourceConnection = null;
  ctx.generatedKey = null;
  ctx.generatedInvite = null;
  ctx.generatedResetCode = null;
  ctx.pendingCall = null;
  ctx.callResult = null;
  ctx.wizard = null;
  ctx.importDraft = null;
  ctx.annotationDrafts = null;
  ctx.dataChoices = null;
  ctx.assistantOptions = null;
}

export async function load() {
  persist();
  const epoch = ++ctx.epoch;
  activeRequest?.abort();
  activeRequest = new AbortController();
  const signal = activeRequest.signal;
  const current = parseRoute();
  Object.assign(ctx, current, { loading: true, error: "", forbidden: false, data: {} });
  ctx.ui.modal = null;
  if (ctx.session) triggerRender();

  try {
    let session: SessionData | null = null;
    try {
      session = (await api.request<SessionData>("/auth/session", { signal, quietAuth: true })).data;
    } catch (error: any) {
      if (error?.status !== 401) throw error;
    }
    if (epoch !== ctx.epoch) return;
    if (ctx.session?.user.id !== session?.user.id) clearVolatileState();
    ctx.session = session || null;

    if (!session) {
      api.csrf = "";
      const [setup, branding] = await Promise.all([
        api.request("/setup", { signal }),
        api.request("/platform-info", { signal }),
      ]);
      ctx.setup = {
        ...setup.data,
        ...branding.data,
        registration: current.path === "/register",
        reset: current.path === "/reset-password",
        invitation: current.params.get("invitation") || "",
      };
      if (epoch !== ctx.epoch) return;
      if (!["/register", "/reset-password"].includes(current.path)) {
        history.replaceState(null, "", "#/login");
        ctx.path = "/login";
      }
      ctx.loading = false;
      triggerRender();
      return;
    }

    if (["/login", "/setup", "/register", "/reset-password"].includes(ctx.path)) {
      history.replaceState(null, "", "#/home");
      ctx.path = "/home";
    }
    if (ctx.path === "/join") {
      const code = current.params.get("code") || "";
      history.replaceState(null, "", "#/space");
      ctx.path = "/space";
      if (code) ctx.pendingJoinCode = code;
    }

    const [workspaces, templates, platform] = await Promise.all([
      api.all<WorkspaceSummary>("/workspaces", signal),
      api.request("/trainer-templates", { signal }),
      api.request("/platform-info", { signal }),
    ]);
    if (epoch !== ctx.epoch) return;
    ctx.workspaces = workspaces;
    ctx.templates = templates.data;
    ctx.platform = platform.data;
    ctx.workspace =
      workspaces.find(space => space.id === (current.params.get("workspace") || ctx.ui.workspaceId)) ||
      workspaces[0] ||
      null;
    ctx.ui.workspaceId = ctx.workspace?.id || "";
    persist();

    ctx.access = ctx.workspace
      ? (await api.request<AccessPolicy>(`/workspaces/${ctx.workspace.id}/access`, { signal })).data
      : { ...session.access, role: "member" };
    if (epoch !== ctx.epoch) return;

    ctx.kind =
      ctx.path.startsWith("/models") || ctx.path === "/admin/models"
        ? "models"
        : ctx.path.startsWith("/datasets") || ctx.path === "/admin/data"
          ? "datasets"
          : null;
    ctx.assetId = ctx.path.match(/^\/(models|datasets)\/([^/]+)$/)?.[2] || "";

    const adminPage = ctx.path.startsWith("/admin/");
    const managementAction = (
      {
        "/admin/stats": "audit.read",
        "/admin/settings": "settings.manage",
        "/admin/audit": "audit.read",
        "/admin/data": "datasets.read",
        "/admin/models": "models.read",
        "/admin/jobs":
          ctx.params.get("job_view") === "operations"
            ? "datasets.read"
            : ctx.params.get("job_view") === "assistants"
              ? "assistants.use"
              : ctx.params.get("job_kind") === "service" || !session.access.actions.includes("training.read")
                ? "services.read"
                : "training.read",
      } as Record<string, string>
    )[ctx.path];

    const needed =
      managementAction ||
      (isDataPage(ctx.path)
        ? "datasets.read"
        : ctx.path === "/train/new"
          ? "training.write"
          : ctx.path === "/datasets/new"
            ? "datasets.write"
            : ctx.path === "/admin/users"
              ? ctx.tab === "groups"
                ? "groups.manage"
                : "users.manage"
              : isAssistantPage(ctx.path)
                ? "assistants.use"
                : isComputePage(ctx.path)
                  ? "resources.read"
                  : ["/services", "/api-keys"].includes(ctx.path)
                    ? "services.read"
                    : ["/projects", "/runs", "/evaluation"].includes(ctx.path) ||
                        ctx.path.startsWith("/projects/") ||
                        ctx.path.startsWith("/evaluation/")
                      ? "training.read"
                      : ctx.kind
                        ? `${ctx.kind}.read`
                        : "");

    const policy = ctx.path === "/admin/users" ? session.access : ctx.access;
    ctx.forbidden = (adminPage && !session.user.is_admin) || !!(needed && !policy.actions.includes(needed));

    let data: Record<string, any> = {};
    const query = `page=${ctx.page}&page_size=20&q=${encodeURIComponent(ctx.q)}`;
    const base = ctx.workspace ? `/workspaces/${ctx.workspace.id}` : "";

    if (!ctx.forbidden && isManagementPage(ctx.path)) {
      data = await loadManagement(api, ctx, signal);
    } else if (!ctx.forbidden && isDataPage(ctx.path)) {
      data = await loadDataWorkflow(api, ctx, signal);
    } else if (!ctx.forbidden && isAssistantPage(ctx.path)) {
      data = await loadAssistant(api, ctx, signal);
    } else if (!ctx.forbidden && ctx.workspace && ctx.path === "/datasets/new") {
      const target = ctx.params.get("dataset");
      data = target ? { importTarget: (await api.request(`${base}/datasets/${encodeURIComponent(target)}`, { signal })).data } : {};
    } else if (!ctx.forbidden && isComputePage(ctx.path)) {
      data = await loadCompute(api, ctx, signal);
    } else if (!ctx.forbidden && isWorkflowPage(ctx.path)) {
      data = await loadWorkflow(api, ctx, signal);
    } else if (!ctx.forbidden && ctx.path === "/admin/users") {
      ctx.groups = session.access.actions.includes("groups.manage") ? await api.all("/admin/groups", signal) : [];
      const filters = new URLSearchParams();
      for (const key of ["group_id", "user_status"]) {
        if (ctx.params.get(key) && ctx.tab !== "groups") filters.set(key, ctx.params.get(key)!);
      }
      data = await api.request(`/admin/${ctx.tab === "groups" ? "groups" : "users"}?${query}&${filters}`, { signal });
    } else if (!ctx.forbidden && ctx.workspace && ctx.kind) {
      if (ctx.assetId) {
        const [item, versions] = await Promise.all([
          api.request(`${base}/${ctx.kind}/${ctx.assetId}`, { signal }),
          api.request(`${base}/${ctx.kind}/${ctx.assetId}/versions?page=${ctx.page}&page_size=20`, { signal }),
        ]);
        data = { item: item.data, versions };
      } else {
        const catalog = !ctx.path.startsWith("/admin/");
        const filters = new URLSearchParams();
        for (const key of ["task_type", "status", ...(ctx.kind === "models" ? ["category"] : ["version_status"])]) {
          if (ctx.params.get(key)) filters.set(key, ctx.params.get(key)!);
        }
        data = await api.request(
          `${base}/${catalog ? (ctx.kind === "models" ? "model-catalog" : "dataset-catalog") : ctx.kind}?${query}&${filters}`,
          { signal }
        );
      }
    } else if (!ctx.forbidden && ctx.workspace && ctx.path === "/space" && ctx.access.actions.includes("members.manage")) {
      const [members, invites, joinRequests, governanceSummary] = await Promise.all([
        api.request(`${base}/members?page=${ctx.page}&page_size=20`, { signal }),
        api.request(`${base}/invites`, { signal }),
        api.request(`${base}/join-requests`, { signal }),
        api.request(`${base}/governance/summary`, { signal }),
      ]);
      data.members = members;
      data.invites = invites.data;
      data.joinRequests = joinRequests.data;
      data.governanceSummary = governanceSummary.data;
    } else if (!ctx.forbidden && ctx.workspace && ctx.path === "/admin/audit") {
      data = await api.request(`${base}/audit?page=${ctx.page}&page_size=20`, { signal });
    } else if (!ctx.forbidden && ctx.workspace && ["/home", "/admin/stats"].includes(ctx.path)) {
      data = (await api.request(`${base}/overview`, { signal })).data;
    }

    if (!ctx.forbidden && ctx.workspace && ctx.path === "/space" && ctx.access.actions.includes("datasets.read")) {
      data.storage = (await api.request(`${base}/storage-usage`, { signal })).data;
    }
    if (!ctx.forbidden && ctx.workspace && ctx.path === "/space" && ctx.access.actions.includes("training.read")) {
      data.myJobs = (await api.request(`${base}/my-jobs?page=1&page_size=10`, { signal })).data;
    }
    if (!ctx.forbidden && ctx.path === "/space") {
      data.sessions = (await api.request("/auth/sessions", { signal })).data;
    }
    if (epoch !== ctx.epoch) return;

    ctx.data = data;
    ctx.loading = false;
    if (ctx.path === "/space" && ctx.pendingJoinCode) {
      ctx.ui.modal = { kind: "workspace-join", item: { code: ctx.pendingJoinCode }, workspaceId: ctx.workspace?.id };
      ctx.pendingJoinCode = null;
    }
    triggerRender();
  } catch (error: any) {
    if (epoch !== ctx.epoch || error?.name === "AbortError") return;
    ctx.loading = false;
    ctx.error = errorMessage(error);
    triggerRender();
  }
}

export function bootstrapApp() {
  if (initialized) return;
  initialized = true;
  hideTip = installStatusTooltip();

  api.onExpired = () => {
    ctx.session = null;
    ctx.ui.modal = null;
    clearVolatileState();
    document.body.classList.remove("modal-open");
    navigate("/login");
  };

  installEvents({
    api,
    ctx,
    load,
    render: triggerRender,
    persist,
    navigate,
    toast,
    openModal,
    closeModal,
  });

  window.addEventListener("hashchange", () => {
    ctx.ui.menuOpen = false;
    void load();
  });

  void load();

  setInterval(async () => {
    const editing = ["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement?.tagName || "");
    if (
      refreshing ||
      !ctx.session ||
      ctx.loading ||
      ctx.ui.modal ||
      editing ||
      isManagementPage(ctx.path) ||
      ctx.path === "/train/new" ||
      !(isComputePage(ctx.path) || isWorkflowPage(ctx.path) || isAssistantPage(ctx.path) || ctx.path.startsWith("/data-operations")) ||
      ctx.forbidden
    ) {
      return;
    }
    refreshing = true;
    const epoch = ctx.epoch;
    try {
      const session = (await api.request<SessionData>("/auth/session")).data;
      if (epoch !== ctx.epoch || ctx.ui.modal) return;
      if (session.user.id !== ctx.session?.user.id || JSON.stringify(session.access) !== JSON.stringify(ctx.session.access)) {
        await load();
        return;
      }
      if (ctx.pendingCall) {
        const pending = ctx.pendingCall;
        const call = (await api.request(`/workspaces/${pending.workspaceId}/calls/${pending.id}`)).data;
        ctx.callResult = call.status === "pending" ? { ...call, result: { 状态: "等待推理" } } : call;
        if (call.status !== "pending") ctx.pendingCall = null;
      }
      const data = isAssistantPage(ctx.path)
        ? await loadAssistant(api, ctx)
        : isDataPage(ctx.path)
          ? await loadDataWorkflow(api, ctx)
          : isComputePage(ctx.path)
            ? await loadCompute(api, ctx)
            : await loadWorkflow(api, ctx);
      const access = ctx.workspace ? (await api.request<AccessPolicy>(`/workspaces/${ctx.workspace.id}/access`)).data : ctx.access;
      if (epoch === ctx.epoch && !ctx.ui.modal && !["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement?.tagName || "")) {
        ctx.data = data;
        ctx.access = access;
        ctx.error = "";
        triggerRender();
      }
    } catch {
      // 后台轮询静默忽略网络抖动
    } finally {
      refreshing = false;
    }
  }, 5000);
}
