import { annotationKey } from "./annotation-view.js?v=stage13-3a";

export function syncProcessing(form, ctx) {
  if (!form?.elements.namedItem("kind")) return;
  const kind = form.elements.namedItem("kind").value;
  const version = ctx.dataChoices?.versions.find(item => item.id === form.elements.namedItem("version_id").value);
  form.querySelectorAll("[data-processing-section]").forEach(section => { section.hidden = section.dataset.processingSection !== kind; });
  form.querySelectorAll("[data-augment-method]").forEach(label => {
    const supported = version?.task_type === "image_classification" ? label.dataset.augmentMethod !== "punctuation" : version?.task_type === "text_classification" && label.dataset.augmentMethod === "punctuation";
    label.hidden = !supported;
    label.querySelector("input").disabled = !supported;
    if (!supported) label.querySelector("input").checked = false;
  });
}

export async function dataAction(action, id, { api, ctx, openModal, load, toast }) {
  const base = `/workspaces/${ctx.workspace?.id}`;
  if (["data-new-annotation", "data-new-operation"].includes(action)) {
    ctx.dataChoices = (await api.request(`${base}/data-options`)).data;
    if (!ctx.dataChoices.versions.length) throw new Error("请先导入数据版本");
    const [kind, chosen] = action === "data-new-operation" ? id.split(":") : ["", id];
    const versionId = chosen || ctx.dataChoices.versions[0].id;
    let labels = [];
    if (action === "data-new-annotation") {
      const samples = (await api.request(`${base}/dataset-versions/${versionId}/samples?page_size=1`)).data;
      labels = Object.keys(samples.labels || {}).filter(value => value !== "未标注");
    }
    openModal(action === "data-new-annotation" ? "data-annotation-new" : "data-operation-new", { version_id: versionId, kind: kind || "clean", labels });
    syncProcessing(document.querySelector('[role="dialog"] form'), ctx);
    return true;
  }
  const confirmations = { "data-confirm-cancel": "data-cancel", "data-confirm-publish": "data-publish", "annotation-confirm-publish": "annotation-publish" };
  if (confirmations[action]) { openModal(confirmations[action], ctx.data.item || ctx.data); return true; }
  if (["annotation-approve", "annotation-reject", "annotation-review-page"].includes(action)) {
    const indices = action === "annotation-review-page" ? ctx.data.samples.filter(sample => sample.result?.state === "submitted").map(sample => sample.index) : [Number(id)];
    await api.request(`${base}/annotation-batches/${ctx.data.id}/review`, { method: "POST", body: { indices, decision: action === "annotation-reject" ? "rejected" : "approved", revision: ctx.data.revision } });
    toast("审核已保存"); await load(); return true;
  }
  return false;
}

export async function saveDataWorkflow(api, modal, form, ctx) {
  const base = `/workspaces/${modal.workspaceId}`;
  if (modal.kind === "data-annotation-new") {
    const result = await api.request(`${base}/annotation-batches`, { method: "POST", body: {
      name: form.get("name"), version_id: form.get("version_id"), labels: String(form.get("labels") || "").split(/\r?\n/).map(value => value.trim()).filter(Boolean),
      limit: Number(form.get("limit")), assigned_to: form.get("assigned_to") || null } });
    return { destination: `/annotation/${result.data.id}` };
  }
  if (modal.kind === "data-operation-new") {
    const entries = String(form.get("label_map") || "").split(/\r?\n/).filter(line => line.trim()).map(line => {
      const equal = line.indexOf("=");
      if (equal < 1 || !line.slice(equal + 1).trim()) throw new Error("标签映射请使用旧标签=新标签");
      return [line.slice(0, equal).trim(), line.slice(equal + 1).trim()];
    });
    const result = await api.request(`${base}/data-operations`, { method: "POST", body: {
      name: form.get("name"), version_id: form.get("version_id"), kind: form.get("kind"), options: {
        seed: Number(form.get("seed")), deduplicate: form.has("deduplicate"), trim: form.has("trim"), drop_unlabeled: form.has("drop_unlabeled"),
        label_map: Object.fromEntries(entries), methods: form.getAll("methods"), train_ratio: Number(form.get("train_ratio")), validation_ratio: Number(form.get("validation_ratio")) } } });
    return { destination: `/data-operations/${result.data.id}` };
  }
  if (["data-publish", "data-cancel", "annotation-publish"].includes(modal.kind)) {
    const annotation = modal.kind === "annotation-publish";
    await api.request(`${base}/${annotation ? "annotation-batches" : "data-operations"}/${modal.item.id}/${modal.kind === "data-cancel" ? "cancel" : "publish"}`, { method: "POST" });
    return {};
  }
  return null;
}

export async function saveAnnotation(api, ctx, form, submit) {
  const index = Number(form.dataset.sampleIndex);
  await api.request(`/workspaces/${ctx.workspace.id}/annotation-batches/${ctx.data.id}/results/${index}`, { method: "POST", body: {
    value: new FormData(form).get("value"), revision: Number(form.dataset.revision), submit } });
  if (ctx.annotationDrafts) delete ctx.annotationDrafts[annotationKey(ctx, index)];
}

export function captureAnnotation(target, ctx) {
  const form = target.closest('[data-form="annotation-result"]');
  if (!form) return;
  ctx.annotationDrafts ||= {};
  ctx.annotationDrafts[annotationKey(ctx, Number(form.dataset.sampleIndex))] = { value: form.elements.namedItem("value").value, revision: Number(form.dataset.revision) };
}
