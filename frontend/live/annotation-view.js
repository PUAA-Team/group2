import { badge, btn, can, e, link, options, pageHeader, pager, tag } from "./components.js?v=stage13-3a";

const states = { draft: "草稿", submitted: "待审核", approved: "已通过", rejected: "已退回" };
export function annotationKey(ctx, index) { return `${ctx.workspace.id}/${ctx.data.id}/${index}`; }

export function renderAnnotation(ctx) {
  const data = ctx.data, selected = data.samples.find(sample => sample.index === Number(ctx.params.get("sample"))) || data.samples[0];
  const mutable = data.status === "open" && can(ctx, "datasets.write");
  const reviewed = data.samples.filter(sample => sample.result?.state === "submitted").map(sample => sample.index);
  const actions = btn("刷新", "refresh") + (mutable && data.can_review && reviewed.length ? btn("审核本页", "annotation-review-page") : "") + (mutable && data.can_review ? btn("发布版本", "annotation-confirm-publish", data.id, "primary", (data.counts.approved || 0) !== data.counts.total) : "");
  const header = `<div class="breadcrumb">${link("在线标注", "/annotation")} / ${e(data.name)}</div>` + pageHeader(data.name, "", actions) + `<div class="toolbar"><div class="heading-actions">${tag(data.dataset.name)}${tag(`v${data.source_version.number}`)}${tag(`已审核 ${data.counts.approved || 0}/${data.counts.total}`)}${data.output_version_id ? link("已发布版本", `/datasets/${data.dataset.id}/samples?version=${data.output_version_id}`) : ""}</div></div>`;
  if (!selected) return header + '<div class="empty-state">当前页暂无样本</div>' + pager(data.pagination);
  const result = selected.result, key = annotationKey(ctx, selected.index), draft = ctx.annotationDrafts?.[key];
  const value = draft?.value ?? result?.value ?? selected.source.label ?? selected.source.output ?? "";
  const image = data.dataset.task_type === "image_classification";
  const sft = data.dataset.task_type === "llm_sft";
  const queue = data.samples.map(sample => `<a class="annotation-queue-item ${sample.index === selected.index ? "is-active" : ""}" href="#/annotation/${data.id}?page=${ctx.page}&sample=${sample.index}"><span>样本 ${sample.index + 1}</span>${sample.result ? badge(states[sample.result.state]) : tag("未标注")}</a>`).join("");
  const content = image ? `<div class="annotation-image"><img src="/api/v1/workspaces/${ctx.workspace.id}/dataset-versions/${data.version_id}/images/${selected.index}" alt="样本${selected.index + 1}"/></div>` : sft ? `<h3>指令</h3><div class="annotation-text">${e(selected.source.instruction)}</div><h3>输入</h3><div class="annotation-text">${e(selected.source.input)}</div>` : `<div class="annotation-text">${e(selected.source.text)}</div>`;
  const disabled = !mutable || !data.can_edit;
  const editor = sft ? `<label for="annotation-value">期望输出</label><textarea id="annotation-value" class="textarea" name="value" rows="10" required maxlength="16000" ${disabled ? "disabled" : ""}>${e(value)}</textarea>` : `<label for="annotation-value">标签</label><select id="annotation-value" class="select" name="value" required ${disabled ? "disabled" : ""}>${options([["", "请选择标签"], ...data.labels.map(label => [label, label])], value)}</select>`;
  return header + `<div class="annotation-workbench"><nav class="annotation-queue" aria-label="样本列表">${queue}</nav><section class="annotation-content"><div class="section-heading"><h2>样本 ${selected.index + 1}</h2>${tag(result ? states[result.state] : "未标注")}</div>${content}</section><section class="annotation-editor"><form data-form="annotation-result" data-sample-index="${selected.index}" data-revision="${draft?.revision ?? result?.revision ?? 0}"><div class="field">${editor}</div><div class="notice notice-danger" data-annotation-error role="alert" hidden></div>${disabled ? "" : `<div class="annotation-save-actions"><button class="btn btn-secondary" type="submit" value="draft">保存草稿</button><button class="btn btn-primary" type="submit" value="submit">提交审核</button></div>`}</form>${mutable && data.can_review && result?.state === "submitted" ? `<div class="annotation-review-actions">${btn("通过", "annotation-approve", selected.index, "primary")}${btn("退回", "annotation-reject", selected.index)}</div>` : ""}</section></div>` + pager(data.pagination);
}
