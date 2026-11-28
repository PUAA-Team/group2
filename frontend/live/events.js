import { errorMessage } from "./api.js?v=stage29-1";
import { QUOTAS, options } from "./components.js?v=stage29-1";
import { addExamples, CSV_TEMPLATE, JSONL_TEMPLATE } from "./examples.js?v=stage29-1";
import { computeAction, saveCompute } from "./compute.js?v=stage29-1";
import { workflowAction, saveWorkflow, workflowModelChanged, workflowOutputModeChanged } from "./workflows.js?v=stage29-1";
import { pageAction, pageChanged, syncImport } from "./page-events.js?v=stage29-1";
import { captureDraft, ensureDraft, persistTraining } from "./training-wizard.js?v=stage29-1";
import { persistImport } from "./dataset-import.js?v=stage29-1";
import { administrationAction, saveAdministration } from "./administration.js?v=stage29-1";
import { captureAnnotation, dataAction, saveAnnotation, saveDataWorkflow, syncProcessing } from "./data-actions.js?v=stage29-1";
import { assistantAction, saveAssistant } from "./assistant.js?v=stage29-1";
import { governanceAction, saveGovernance } from './governance.js?v=stage29-1';
import { parameterTemplateAction, saveParameterTemplate } from './parameter-templates.js?v=stage29-1';
import { projectAction, saveProject } from './projects.js?v=stage29-1';
import { keyAction, saveKey } from './key-management.js?v=stage29-1';
import { queryAction, saveQuery } from './query-controls.js?v=stage29-1';
import { syncResourceNodes } from './resource-options.js?v=stage29-1';

function showError(selector, error) {
  const target = document.querySelector(selector);
  if (target) { target.textContent = typeof error === "string" ? error : errorMessage(error); target.hidden = false; target.scrollIntoView({ block: "nearest" }); }
}
function policy(form) {
  return { allow_actions: form.getAll("allow_actions"), deny_actions: form.getAll("deny_actions"), quota: Object.fromEntries(
    QUOTAS.filter(([key]) => String(form.get(key) || "").trim() !== "").map(([key]) => [key, Number(form.get(key))])) };
}
function template(task) {
  if (task === "image_classification") { const anchor = document.createElement("a"); anchor.href = "/api/v1/dataset-templates/image-classification"; anchor.download = "image-template.zip"; anchor.click(); return; }
  const sft = task === "llm_sft";
  const url = URL.createObjectURL(new Blob([sft ? JSONL_TEMPLATE : CSV_TEMPLATE], { type: "text/plain;charset=utf-8" }));
  const anchor = document.createElement("a"); anchor.href = url; anchor.download = sft ? "instruction-template.jsonl" : "classification-template.csv"; anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function installEvents({ api, ctx, load, render, persist, navigate, toast, openModal, closeModal }) {
  let busy = false;
  function changedQuery(changes) {
    const [path, query] = location.hash.slice(1).split("?");
    const params = new URLSearchParams(query);
    Object.entries(changes).forEach(([key, value]) => value ? params.set(key, String(value)) : params.delete(key));
    navigate(path + (params.size ? `?${params}` : ""));
  }
  // 点击动作分发表：先按顺序试各功能模块的动作处理器，命中即停；
  // 再查单动作路由表。新增动作只需在表里加一行，不改分发逻辑。
  const clickPipeline = [
    deps => pageAction(deps.action, deps.ctx, deps.api, deps.render),
    deps => projectAction(deps.action, { ctx: deps.ctx, openModal: deps.openModal }),
    deps => keyAction(deps.action, deps.id, { ctx: deps.ctx, openModal: deps.openModal, toast: deps.toast }),
    deps => queryAction(deps.action, { ctx: deps.ctx, openModal: deps.openModal, navigate: deps.navigate }),
    deps => parameterTemplateAction(deps.action, deps.id, { api: deps.api, ctx: deps.ctx, openModal: deps.openModal, render: deps.render, toast: deps.toast, form: deps.button.form }),
    deps => dataAction(deps.action, deps.id, { api: deps.api, ctx: deps.ctx, openModal: deps.openModal, load: deps.load, toast: deps.toast }),
    deps => assistantAction(deps.action, deps.id, { api: deps.api, ctx: deps.ctx, openModal: deps.openModal, load: deps.load, toast: deps.toast, form: deps.button.form }),
    // admin-test-connection：调用前后禁用/恢复按钮，避免重复测试。
    async deps => {
      if (deps.action !== "admin-test-connection") return false;
      const caption = deps.button.textContent;
      deps.button.disabled = true; deps.button.textContent = "正在测试…";
      try { await administrationAction(deps.action, deps.id, { api: deps.api, ctx: deps.ctx, openModal: deps.openModal, render: deps.render, load: deps.load, toast: deps.toast }); }
      finally { if (deps.button.isConnected) { deps.button.disabled = false; deps.button.textContent = caption; } }
      return true;
    },
    deps => administrationAction(deps.action, deps.id, { api: deps.api, ctx: deps.ctx, openModal: deps.openModal, render: deps.render, load: deps.load, toast: deps.toast }),
    deps => computeAction(deps.action, deps.id, { api: deps.api, ctx: deps.ctx, openModal: deps.openModal, toast: deps.toast, load: deps.load }),
    deps => governanceAction(deps.action, deps.id, { api: deps.api, ctx: deps.ctx, openModal: deps.openModal }),
    deps => workflowAction(deps.action, deps.id, { api: deps.api, ctx: deps.ctx, openModal: deps.openModal, toast: deps.toast, load: deps.load, render: deps.render, navigate: deps.navigate }),
  ];
  const clickActions = new Map([
    ["toggle-password", deps => { const field = document.getElementById("live-password"); field.type = field.type === "password" ? "text" : "password"; deps.button.setAttribute("aria-label", field.type === "text" ? "隐藏密码" : "显示密码"); }],
    ["toggle-nav", deps => { deps.ctx.ui.navOpen[deps.group] = !deps.ctx.ui.navOpen[deps.group]; deps.render(); deps.persist(); }],
    ["collapse-sidebar", deps => { deps.ctx.ui.sidebarCollapsed = !deps.ctx.ui.sidebarCollapsed; deps.render(); deps.persist(); }],
    ["open-menu", deps => { deps.ctx.ui.menuOpen = true; document.getElementById("shell")?.classList.toggle("menu-open", true); }],
    ["close-menu", deps => { deps.ctx.ui.menuOpen = false; document.getElementById("shell")?.classList.toggle("menu-open", false); }],
    ["logout", async deps => { await deps.api.request("/auth/logout", { method: "POST" }); deps.api.csrf = ""; deps.ctx.session = null; deps.ctx.ui.modal = null; deps.ctx.resourceConnection = null; deps.ctx.generatedKey = null; deps.ctx.generatedInvite = null; deps.ctx.pendingCall = null; deps.ctx.callResult = null; deps.ctx.wizard = null; deps.ctx.importDraft = null; deps.ctx.annotationDrafts = null; deps.ctx.dataChoices = null; deps.ctx.assistantOptions = null; deps.navigate("/login"); }],
    ["refresh", deps => deps.load()],
    ["go", deps => deps.navigate(deps.id)],
    ["modal", deps => deps.openModal(deps.id, ["model-version", "model-upload", "dataset-version"].includes(deps.id) ? deps.ctx.data.item : undefined)],
    ["close-modal", deps => deps.closeModal()],
    ["edit-asset", deps => deps.openModal("asset-edit", deps.ctx.data.item || deps.ctx.data.data.find(item => item.id === deps.id))],
    ["edit-group", deps => deps.openModal("group-edit", deps.ctx.data.data.find(item => item.id === deps.id))],
    ["edit-user", deps => deps.openModal("user-edit", deps.ctx.data.data.find(item => item.id === deps.id))],
    ["edit-member", deps => deps.openModal("member", deps.ctx.data.members.data.find(item => item.user_id === deps.id))],
    ["transfer-owner", deps => deps.openModal("transfer-owner", deps.ctx.data.members.data.find(item => item.user_id === deps.id))],
    ["toggle-user", deps => deps.openModal("toggle-user", deps.ctx.data.data.find(item => item.id === deps.id))],
    ["page", deps => changedQuery({ page: Number(deps.id) })],
    ["clear-search", () => changedQuery({ page: 1, q: "" })],
    ["template", deps => template(deps.id)],
    ["select-workspace", deps => { deps.ctx.ui.workspaceId = deps.id; deps.persist(); deps.navigate("/home"); }],
    ["preview", async deps => { const epoch = deps.ctx.epoch; const result = await deps.api.request(`/workspaces/${deps.ctx.workspace.id}/datasets/${deps.ctx.data.item.id}/versions/${deps.id}/preview?limit=20`); if (epoch === deps.ctx.epoch) { deps.ctx.data.preview = result.data; deps.render(); document.getElementById("samples")?.scrollIntoView({ block: "start", behavior: "smooth" }); } }],
    ["dataset-report", async deps => { const [datasetId, versionId] = String(deps.id).split(":"); const result = await deps.api.request(`/workspaces/${deps.ctx.workspace.id}/datasets/${datasetId}/versions/${versionId}/report`); deps.openModal("dataset-report", result.data); }],
    ["session-revoke", deps => { deps.openModal("session-revoke-own-confirm", (deps.ctx.data.sessions || []).find(s => s.id === deps.id)); }],
    ["session-revoke-others", deps => { const others = (deps.ctx.data.sessions || []).filter(s => !s.current); deps.openModal("session-revoke-others-confirm", { other_count: others.length }); }],
    ["admin-job-stop", async deps => { const [ws, jobId] = String(deps.id).split(":"); await deps.api.request(`/workspaces/${ws}/jobs/${jobId}/stop`, { method: "POST" }); deps.toast("已提交停止/取消"); await deps.load(); }],
    ["admin-job-retry", async deps => { const [ws, jobId] = String(deps.id).split(":"); const res = await deps.api.request(`/workspaces/${ws}/jobs/${jobId}/retry`, { method: "POST" }); deps.toast("已创建重跑草稿"); deps.navigate(`/runs/${res.data.id}?workspace=${ws}`); }],
  ]);

  document.addEventListener("click", async event => {
    const button = event.target.closest("[data-action]");
    if (!button || button.disabled || busy) return;
    const { action, id, group } = button.dataset;
    const deps = { api, ctx, load, render, persist, navigate, toast, openModal, closeModal, button, action, id, group };
    try {
      for (const handle of clickPipeline) if (await handle(deps)) return;
      await clickActions.get(action)?.(deps);
    } catch (error) { toast(errorMessage(error)); }
  });

  document.addEventListener("change", event => {
    captureAnnotation(event.target, ctx);
    if (event.target.matches("[data-processing-kind],[data-processing-version]")) syncProcessing(event.target.form, ctx);
    pageChanged(event.target, ctx, render);
    if (event.target.matches("[data-query-filter]")) changedQuery({ [event.target.dataset.queryFilter]: event.target.value, page: 1 });
    if (event.target.matches("[data-job-model]")) workflowModelChanged(event.target.form, ctx);
    if (event.target.matches("[data-resource-kind]")) syncResourceNodes(event.target, ctx.data.nodes || []);
    if (event.target.matches("[data-inference-mode]")) workflowOutputModeChanged(event.target.form);
    if (event.target.matches("[data-enroll-platform]")) {
      const form = event.target.form, mode = event.target.value;
      form.querySelector("[data-image-field]").hidden = mode !== "docker";
      form.elements.namedItem("image").required = mode === "docker";
      form.elements.namedItem("state_dir").value = mode === "windows" ? "D:/model-training-worker" : mode === "linux" ? "~/.local/share/model-training-worker" : "/opt/model-training-worker";
      form.elements.namedItem("training_python").value = mode === "windows" ? "python" : "python3";
    }
    if (event.target.matches("[data-auto-refresh]")) { ctx.ui.autoRefresh = event.target.checked; persist(); render(); }
    if (event.target.matches("[data-workspace-select]")) {
      ctx.ui.workspaceId = event.target.value; persist();
      ctx.assetId ? navigate(`/${ctx.kind}`) : /^\/runs\/[^/]+$/.test(ctx.path) ? navigate("/runs") : load();
    }
    if (event.target.matches("[data-task-choice]") && ctx.ui.modal?.kind === "model-new") {
      document.querySelector('[name="trainer_id"]').innerHTML = options(ctx.templates.filter(item => item.task_type === event.target.value).map(item => [item.id, item.name]));
    }
  });

  document.addEventListener("input", event => captureAnnotation(event.target, ctx));

  document.addEventListener("submit", async event => {
    const form = event.target.closest("[data-form]");
    if (!form) return;
    event.preventDefault();
    if (busy || ctx.pageBusy) return;
    const data = new FormData(form), type = form.dataset.form;
    if (type === "search") { changedQuery({ q: data.get("q"), page: 1 }); return; }
    if (type === "logs-search") { changedQuery({ log_q: data.get("log_q") }); return; }
    if (type === "evaluation-compare") {
      const ids = data.getAll("ids");
      if (ids.length < 2 || ids.length > 6) { toast("请选择2～6个已完成评估"); return; }
      const query = new URLSearchParams(); ids.forEach(id => query.append("ids", id));
      navigate(`/evaluation/compare?${query}`); return;
    }
    if (type === "training-wizard") {
      const draft = ensureDraft(ctx); captureDraft(draft, data);
      if (draft.step < 3) { draft.step++; render(); return; }
    }
    if (["setup", "register", "reset-password"].includes(type) && data.get("password") !== data.get("confirm")) { showError("[data-auth-error]", "两次输入的密码不一致"); return; }
    busy = true;
    const submit = event.submitter || form.querySelector('[type="submit"]'); submit.disabled = true; const caption = submit.textContent; submit.textContent = "正在保存…";
    try {
      if (type === "annotation-result") {
        await saveAnnotation(api, ctx, form, event.submitter?.value === "submit");
        toast("标注已保存"); await load(); return;
      }
      if (type === "training-wizard") {
        const destination = await persistTraining(api, ctx, event.submitter?.value === "submit");
        ctx.wizard = null; toast(event.submitter?.value === "submit" ? "训练已提交" : "草稿已保存"); navigate(destination); return;
      }
      if (type === "dataset-import") {
        const destination = await persistImport(api, syncImport(ctx, form));
        ctx.importDraft = null; ctx.annotationDrafts = null; ctx.dataChoices = null; toast("数据版本已导入"); navigate(destination); return;
      }
      if (type === "reset-password") {
        await api.request("/auth/password-reset", { method: "POST", body: { account: data.get("account"), code: String(data.get("code") || "").trim(), password: data.get("password") }, quietAuth: true });
        toast("密码已重置，请使用新密码登录"); navigate("/login"); return;
      }
      if (["setup", "login", "register"].includes(type)) {
        if (type === "register") await api.request("/auth/register", { method: "POST", body: { account: data.get("account"), display_name: data.get("display_name"), password: data.get("password"), invitation: String(data.get("invitation") || "").trim() || null }, quietAuth: true });
        if (type === "setup") await api.request("/setup", { method: "POST", body: { account: data.get("account"), display_name: data.get("display_name"), password: data.get("password") }, quietAuth: true });
        await api.request("/auth/login", { method: "POST", body: { account: data.get("account"), password: data.get("password") }, quietAuth: true });
        if (type === "setup") {
          const result = await api.request("/workspaces", { method: "POST", body: { name: data.get("workspace_name") || "研发工作空间" } });
          ctx.ui.workspaceId = result.data.id; persist();
        }
        history.replaceState(null, "", "#/home"); await load(); return;
      }
      const modal = ctx.ui.modal;
      if (!modal) return;
      const base = `/workspaces/${modal.workspaceId}`;
      const kind = ctx.kind;
      let destination = "";
      const feature = await saveProject(api, modal, data) || await saveKey(api, modal, data) || await saveQuery(api, modal, data) || await saveParameterTemplate(api, modal, data, ctx) || await saveGovernance(api, modal, data, ctx) || await saveAssistant(api, modal, data, ctx) || await saveDataWorkflow(api, modal, data, ctx) || await saveAdministration(api, modal, data, ctx) || await saveCompute(api, modal, data, ctx) || await saveWorkflow(api, modal, data, ctx);
      if (feature) destination = feature.destination || "";
      else switch (modal.kind) {
        case "workspace-new": {
          const result = await api.request("/workspaces", { method: "POST", body: { name: data.get("name") } });
          ctx.ui.workspaceId = result.data.id; persist(); destination = "/space"; break;
        }
        case "model-new": case "dataset-new": {
          const model = modal.kind === "model-new";
          const payload = { name: data.get("name"), task_type: data.get("task_type"), description: data.get("description") };
          if (model) Object.assign(payload, { trainer_id: data.get("trainer_id"), source_ref: data.get("source_ref") });
          const result = await api.request(`${base}/${model ? "models" : "datasets"}`, { method: "POST", body: payload });
          destination = `/${model ? "models" : "datasets"}/${result.data.id}`; break;
        }
        case "asset-edit": await api.request(`${base}/${kind}/${modal.item.id}`, { method: "PATCH", revision: modal.item.revision, body: { name: data.get("name"), description: data.get("description") } }); break;
        case "model-version": await api.request(`${base}/models/${modal.item.id}/versions`, { method: "POST", body: { version: data.get("version"), source_ref: data.get("source_ref") } }); break;
        case "model-upload": { const file = new FormData(); file.append("version", data.get("version")); file.append("file", data.get("file")); await api.request(`${base}/models/${modal.item.id}/versions/upload`, { method: "POST", body: file }); break; }
        case "dataset-version": { const file = new FormData(); file.append("file", data.get("file")); await api.request(`${base}/datasets/${modal.item.id}/versions`, { method: "POST", body: file }); break; }
        case "member": {
          const quota = Object.fromEntries(QUOTAS.filter(([k]) => String(data.get(`quota_${k}`) || "").trim() !== "").map(([k]) => [k, Number(data.get(`quota_${k}`))]));
          await api.request(`${base}/members`, { method: "POST", body: { ...(modal.item.user_id ? { user_id: modal.item.user_id } : { account: data.get("account") }), role: data.get("role"), quota } });
          break;
        }
        case "transfer-owner":
          await api.request(`${base}/transfer-owner`, { method: "POST", revision: ctx.workspace.revision, body: { user_id: modal.item.user_id } });
          break;
        case "group-new": case "group-edit": await api.request(`/admin/groups${modal.item.id ? `/${modal.item.id}` : ""}`, { method: modal.item.id ? "PATCH" : "POST", revision: modal.item.revision, body: { name: data.get("name"), ...policy(data) } }); break;
        case "user-new": case "user-edit": {
          const payload = { display_name: data.get("display_name"), group_id: data.get("group_id") || null, is_admin: data.get("is_admin") === "true", ...policy(data) };
          if (modal.kind === "user-new") Object.assign(payload, { account: data.get("account"), password: data.get("password") });
          await api.request(`/admin/users${modal.item.id ? `/${modal.item.id}` : ""}`, { method: modal.item.id ? "PATCH" : "POST", revision: modal.item.revision, body: payload }); break;
        }
        case "toggle-user": await api.request(`/admin/users/${modal.item.id}`, { method: "PATCH", revision: modal.item.revision, body: { active: !modal.item.active } }); break;
        case "examples": if (!data.getAll("examples").length) throw new Error("请选择示例资产"); else await addExamples(api, modal.workspaceId, data.getAll("examples")); break;
      }
      if (ctx.ui.modal === modal) { ctx.ui.modal = null; toast(feature?.toast || "已保存"); destination ? navigate(destination) : await load(); }
    } catch (error) {
      if (type === "training-wizard") ctx.wizard.error = errorMessage(error);
      if (type === "dataset-import") ctx.importDraft.error = errorMessage(error);
      showError(type === "dialog" ? "[data-modal-error]" : type === "annotation-result" ? "[data-annotation-error]" : type === "training-wizard" ? "[data-wizard-error]" : type === "dataset-import" ? "[data-import-error]" : "[data-auth-error]", error);
    }
    finally { busy = false; if (submit.isConnected) { submit.disabled = false; submit.textContent = caption; } }
  });

  document.addEventListener("keydown", event => {
    const dialog = document.querySelector('[role="dialog"]');
    if (!dialog) return;
    if (event.key === "Escape" && !busy) { closeModal(); return; }
    if (event.key === "Tab") {
      const elements = [...dialog.querySelectorAll('button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),a[href]')].filter(item => item.getClientRects().length);
      const first = elements[0], last = elements.at(-1);
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    }
  });
}
