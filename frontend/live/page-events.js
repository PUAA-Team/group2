import { errorMessage } from "./api.js?v=stage20a-2";
import { captureDraft, ensureDraft, updateTask } from "./training-wizard.js?v=stage20a-2";
import { ensureImport, inspectImport, previewImport } from "./dataset-import.js?v=stage20a-2";

export function syncImport(ctx, form) {
  const draft = ensureImport(ctx);
  draft.name = form.elements.name.value;
  for (const target of draft.inspection?.targets || []) {
    const field = form.elements.namedItem('column_' + target.name);
    if (field && draft.columnMapping[target.name] !== (field.value || null)) { draft.columnMapping[target.name] = field.value || null; draft.preview = null; }
  }
  return draft;
}

export function pageChanged(target, ctx, render) {
  if (target.form?.dataset.form === "training-wizard") {
    const draft = ensureDraft(ctx), previousTask = draft.values.task_type;
    captureDraft(draft, new FormData(target.form));
    if (target.matches('[data-parameter-template]')) { draft.templateId = target.value; render(); }
    if (target.matches("[data-wizard-task],[data-wizard-model]")) {
      const task = draft.values.task_type, selected = draft.values.model_version_id;
      draft.values.task_type = previousTask;
      updateTask(draft, ctx.data.options, task, selected); draft.preview = null; render();
    }
    if (target.matches("[data-wizard-dataset]")) { draft.preview = null; render(); }
    if (target.name === 'project_id') render();
  }
  if (target.form?.dataset.form === "dataset-import") {
    const draft = syncImport(ctx, target.form);
    if (target.matches("[data-import-task]")) { draft.task_type = target.value; draft.preview = null; draft.file = null; draft.inspection = null; draft.columnMapping = null; draft.error = ""; render(); }
    if (target.matches("[data-import-file]")) { draft.file = target.files[0] || null; draft.preview = null; draft.inspection = null; draft.columnMapping = null; draft.error = ""; render(); }
    if (target.matches('[data-import-column]')) { draft.preview = null; draft.error = ''; render(); }
  }
}

export async function pageAction(action, ctx, api, render) {
  if (!["wizard-next", "wizard-back", "wizard-preview", "import-preview", "import-inspect"].includes(action)) return false;
  if (ctx.pageBusy) return true;
  if (["import-preview", "import-inspect"].includes(action)) {
    const form = document.querySelector('[data-form="dataset-import"]'), draft = syncImport(ctx, form);
    ctx.pageBusy = true;
    try { draft.error = ""; if (action === 'import-inspect') await inspectImport(api, draft); else await previewImport(api, draft); }
    catch (error) { draft.error = errorMessage(error); }
    finally { ctx.pageBusy = false; render(); }
    return true;
  }
  const form = document.querySelector('[data-form="training-wizard"]'), draft = ensureDraft(ctx);
  if (action === "wizard-next" && !form.reportValidity()) return true;
  captureDraft(draft, new FormData(form)); draft.error = "";
  if (action === "wizard-next") draft.step = Math.min(3, draft.step + 1);
  if (action === "wizard-back") draft.step = Math.max(0, draft.step - 1);
  if (action === "wizard-preview") {
    const dataset = ctx.data.options.datasets.find(item => item.id === draft.values.dataset_version_id);
    if (dataset) {
      ctx.pageBusy = true;
      try { draft.preview = (await api.request(`/workspaces/${ctx.workspace.id}/datasets/${dataset.dataset_id}/versions/${dataset.id}/preview?limit=10`)).data; }
      catch (error) { draft.error = errorMessage(error); }
      finally { ctx.pageBusy = false; }
    }
  }
  render();
  return true;
}
