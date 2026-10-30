import { errorMessage } from "./api.js?v=stage13-3a";
import { QUOTAS, options } from "./components.js?v=stage13-3a";
import { addExamples, CSV_TEMPLATE, JSONL_TEMPLATE } from "./examples.js?v=stage13-3a";
import { computeAction, saveCompute } from "./compute.js?v=stage13-3a";
import { workflowAction, saveWorkflow, workflowModelChanged, workflowOutputModeChanged } from "./workflows.js?v=stage13-3a";
import { pageAction, pageChanged, syncImport } from "./page-events.js?v=stage13-3a";
import { captureDraft, ensureDraft, persistTraining } from "./training-wizard.js?v=stage13-3a";
import { persistImport } from "./dataset-import.js?v=stage13-3a";
import { administrationAction, saveAdministration } from "./administration.js?v=stage13-3a";
import { captureAnnotation, dataAction, saveAnnotation, saveDataWorkflow, syncProcessing } from "./data-actions.js?v=stage13-3a";

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
  document.addEventListener("click", async event => {
    const button = event.target.closest("[data-action]");
    if (!button || button.disabled || busy) return;
    const { action, id, group } = button.dataset;
    try {
      if (await pageAction(action, ctx, api, render)) return;
      if (await dataAction(action, id, { api, ctx, openModal, load, toast })) return;
      if (action === "admin-test-connection") {
        const caption = button.textContent;
        button.disabled = true; button.textContent = "正在测试…";
        try { await administrationAction(action, id, { api, ctx, openModal, render, load, toast }); }
        finally { if (button.isConnected) { button.disabled = false; button.textContent = caption; } }
        return;
      }
      if (await administrationAction(action, id, { api, ctx, openModal, render, load, toast })) return;
      if (await computeAction(action, id, { api, ctx, openModal, toast, load })) return;
      if (await workflowAction(action, id, { api, ctx, openModal, toast, load, render, navigate })) return;
      if (action === "toggle-password") { const field = document.getElementById("live-password"); field.type = field.type === "password" ? "text" : "password"; button.setAttribute("aria-label", field.type === "text" ? "隐藏密码" : "显示密码"); }
      if (action === "toggle-nav") { ctx.ui.navOpen[group] = !ctx.ui.navOpen[group]; render(); persist(); }
      if (action === "collapse-sidebar") { ctx.ui.sidebarCollapsed = !ctx.ui.sidebarCollapsed; render(); persist(); }
      if (action === "open-menu" || action === "close-menu") { ctx.ui.menuOpen = action === "open-menu"; document.getElementById("shell")?.classList.toggle("menu-open", ctx.ui.menuOpen); }
      if (action === "logout") { await api.request("/auth/logout", { method: "POST" }); api.csrf = ""; ctx.session = null; ctx.ui.modal = null; ctx.resourceConnection = null; ctx.generatedKey = null; ctx.generatedInvite = null; ctx.pendingCall = null; ctx.callResult = null; ctx.wizard = null; ctx.importDraft = null; ctx.annotationDrafts = null; ctx.dataChoices = null; navigate("/login"); }
      if (action === "refresh") await load();
      if (action === "go") navigate(id);
      if (action === "modal") openModal(id, ["model-version", "dataset-version"].includes(id) ? ctx.data.item : undefined);
      if (action === "close-modal") closeModal();
      if (action === "edit-asset") openModal("asset-edit", ctx.data.item || ctx.data.data.find(item => item.id === id));
      if (action === "edit-group") openModal("group-edit", ctx.data.data.find(item => item.id === id));
      if (action === "edit-user") openModal("user-edit", ctx.data.data.find(item => item.id === id));
      if (action === "edit-member") openModal("member", ctx.data.members.data.find(item => item.user_id === id));
      if (action === "toggle-user") openModal("toggle-user", ctx.data.data.find(item => item.id === id));
      if (action === "page") changedQuery({ page: Number(id) });
      if (action === "clear-search") changedQuery({ page: 1, q: "" });
      if (action === "template") template(id);
      if (action === "select-workspace") { ctx.ui.workspaceId = id; persist(); navigate("/home"); }
      if (action === "preview") {
        const epoch = ctx.epoch;
        const result = await api.request(`/workspaces/${ctx.workspace.id}/datasets/${ctx.data.item.id}/versions/${id}/preview?limit=20`);
        if (epoch === ctx.epoch) { ctx.data.preview = result.data; render(); document.getElementById("samples")?.scrollIntoView({ block: "start", behavior: "smooth" }); }
      }
    } catch (error) { toast(errorMessage(error)); }
  });

  document.addEventListener("change", event => {
    captureAnnotation(event.target, ctx);
    if (event.target.matches("[data-processing-kind],[data-processing-version]")) syncProcessing(event.target.form, ctx);
    pageChanged(event.target, ctx, render);
    if (event.target.matches("[data-query-filter]")) changedQuery({ [event.target.dataset.queryFilter]: event.target.value, page: 1 });
    if (event.target.matches("[data-job-model]")) workflowModelChanged(event.target.form, ctx);
    if (event.target.matches("[data-inference-mode]")) workflowOutputModeChanged(event.target.form);
    if (event.target.matches("[data-enroll-platform]")) {
      const form = event.target.form, mode = event.target.value;
      form.querySelector("[data-image-field]").hidden = mode !== "docker";
      form.elements.namedItem("image").required = mode === "docker";
      form.elements.namedItem("state_dir").value = mode === "windows" ? "D:/model-training-worker" : mode === "linux" ? "~/.local/share/model-training-worker" : "/opt/model-training-worker";
      form.elements.namedItem("training_python").value = mode === "windows" ? "python" : "python3";
    }
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
    if (type === "training-wizard") {
      const draft = ensureDraft(ctx); captureDraft(draft, data);
      if (draft.step < 3) { draft.step++; render(); return; }
    }
    if (["setup", "register"].includes(type) && data.get("password") !== data.get("confirm")) { showError("[data-auth-error]", "两次输入的密码不一致"); return; }
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
      if (["setup", "login", "register"].includes(type)) {
        if (type === "register") await api.request("/auth/register", { method: "POST", body: { account: data.get("account"), display_name: data.get("display_name"), password: data.get("password"), invitation: data.get("invitation") }, quietAuth: true });
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
      const feature = await saveDataWorkflow(api, modal, data, ctx) || await saveAdministration(api, modal, data, ctx) || await saveCompute(api, modal, data, ctx) || await saveWorkflow(api, modal, data, ctx);
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
        case "dataset-version": { const file = new FormData(); file.append("file", data.get("file")); await api.request(`${base}/datasets/${modal.item.id}/versions`, { method: "POST", body: file }); break; }
        case "member": await api.request(`${base}/members`, { method: "POST", body: { ...(modal.item.user_id ? { user_id: modal.item.user_id } : { account: data.get("account") }), role: data.get("role") } }); break;
        case "group-new": case "group-edit": await api.request(`/admin/groups${modal.item.id ? `/${modal.item.id}` : ""}`, { method: modal.item.id ? "PATCH" : "POST", revision: modal.item.revision, body: { name: data.get("name"), ...policy(data) } }); break;
        case "user-new": case "user-edit": {
          const payload = { display_name: data.get("display_name"), group_id: data.get("group_id") || null, is_admin: data.get("is_admin") === "true", ...policy(data) };
          if (modal.kind === "user-new") Object.assign(payload, { account: data.get("account"), password: data.get("password") });
          await api.request(`/admin/users${modal.item.id ? `/${modal.item.id}` : ""}`, { method: modal.item.id ? "PATCH" : "POST", revision: modal.item.revision, body: payload }); break;
        }
        case "toggle-user": await api.request(`/admin/users/${modal.item.id}`, { method: "PATCH", revision: modal.item.revision, body: { active: !modal.item.active } }); break;
        case "examples": if (!data.getAll("examples").length) throw new Error("请选择示例资产"); else await addExamples(api, modal.workspaceId, data.getAll("examples")); break;
      }
      if (ctx.ui.modal === modal) { ctx.ui.modal = null; toast("已保存"); destination ? navigate(destination) : await load(); }
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
