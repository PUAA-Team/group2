import { badge, btn, can, card, e, fieldsInfo, input, options, pageHeader, raw, select, STATUS, table, tag, TASKS, workspaceRequired } from "./components.js?v=stage20a-2";

const formats = { text_classification: ["CSV", ".csv", "text,label\n示例文本,类别A"], image_classification: ["ZIP", ".zip", "labels.csv\nfilename,label\nimages/sample.png,类别A"], llm_sft: ["JSONL", ".jsonl", '{"instruction":"任务指令","input":"输入内容","output":"预期输出"}'] };

export function ensureImport(ctx) {
  const target = ctx.params?.get("dataset") || "new";
  if (!ctx.importDraft || ctx.importDraft.workspaceId !== ctx.workspace.id || ctx.importDraft.key !== target) {
    const dataset = ctx.data.importTarget;
    ctx.importDraft = { key: target, workspaceId: ctx.workspace.id, datasetId: dataset?.id || null, name: dataset?.name || "", task_type: dataset?.task_type || "text_classification", description: "", file: null, preview: null, inspection: null, columnMapping: null, error: "" };
  }
  return ctx.importDraft;
}

export function renderDatasetImport(ctx) {
  if (!ctx.workspace) return pageHeader("导入数据集") + workspaceRequired(ctx);
  if (!can(ctx, "datasets.write")) return pageHeader("无权导入数据");
  if (ctx.data.importTarget?.archived) return pageHeader('导入数据版本') + `<div class="notice">数据集已归档，请先恢复。</div><a class="entity-link" href="#/datasets/${e(ctx.data.importTarget.id)}">查看数据集</a>`;
  const draft = ensureImport(ctx), [format, accept, template] = formats[draft.task_type];
  const preview = draft.preview;
  const mapping = mappingFields(draft);
  const keys = Object.keys(preview?.samples[0] || {});
  return `<div class="breadcrumb"><a href="#/datasets">数据集</a><span>/</span><span>导入数据集</span></div>` + pageHeader(draft.datasetId ? "导入数据版本" : "导入数据集") +
    `<form data-form="dataset-import"><div class="notice notice-danger" data-import-error role="alert" ${draft.error ? "" : "hidden"}>${e(draft.error || "")}</div><div class="console-import-layout"><div class="stack">${card(`<div class="card-header"><h2>基本信息</h2></div><div class="stack">${input("数据集名称", "name", draft.name, `required maxlength="100" ${draft.datasetId ? "readonly" : ""}`)}${select("任务类型", "task_type", options(Object.entries(TASKS), draft.task_type), `data-import-task ${draft.datasetId ? "disabled" : ""}`)}</div>`)}${card(`<div class="card-header"><h2>上传文件</h2>${tag(format)}</div><label class="console-upload-zone"><strong>${draft.file ? e(draft.file.name) : "选择数据文件"}</strong><input class="input live-file" type="file" name="file" accept="${accept}" data-import-file aria-label="选择数据文件" /></label>${draft.file ? fieldsInfo([["文件大小", `${(draft.file.size / 1024).toFixed(1)} KiB`]]) : ""}<div class="heading-actions">${btn("校验并预览", "import-preview", "", "secondary", !draft.file)}</div>`)}</div><aside class="stack">${card(`<div class="card-header"><h2>格式模板</h2>${btn("下载模板", "template", draft.task_type)}</div><pre class="template-preview">${e(template)}</pre>`)}${preview ? card(`<div class="card-header"><h2>校验结果</h2>${badge(STATUS[preview.status] || preview.status)}</div>${fieldsInfo([["样本数", e(preview.sample_count)], ["格式", tag(preview.format.toUpperCase())], ["SHA256", `<span class="live-break">${e(preview.sha256)}</span>`]])}`) : ""}</aside></div>` +
    `<div class="heading-actions">${btn('字段映射', 'import-inspect', '', 'secondary', !draft.file)}</div>${mapping}` +
    (preview ? `<div class="section-heading"><h2>样本预览</h2>${tag(`前 ${preview.samples.length} 条`)}</div>${table(keys, preview.samples.map(row => keys.map(key => raw(`<div class="live-sample">${e(row[key])}</div>`))))}` : "") +
    `<div class="console-wizard-footer"><a class="btn btn-secondary" href="#/datasets">取消</a><button class="btn btn-primary" type="submit">导入并创建版本</button></div></form>`;
}

function mappingFields(draft) {
  if (!draft.inspection) return '';
  const labels = { text: '文本', label: '标签', filename: '图片路径', instruction: '指令', input: '输入', output: '输出' };
  const ignored = draft.inspection.columns.filter(column => !Object.values(draft.columnMapping || {}).includes(column));
  return `<div class="section-heading"><h2>字段映射</h2></div><div class="live-field-grid">${draft.inspection.targets.map(target =>
    select(labels[target.name], 'column_' + target.name, options([['', target.required ? '请选择原字段' : '不提供'], ...draft.inspection.columns.map(name => [name, name])], draft.columnMapping?.[target.name] || ''), `data-import-column="${target.name}" ${target.required ? 'required' : ''}`)).join('')}</div>` +
    (ignored.length ? `<div class="heading-actions">${tag('未导入字段')}${ignored.map(tag).join('')}</div>` : '');
}

export async function inspectImport(api, draft) {
  const file = draft.file, task = draft.task_type;
  if (!file) throw new Error('请选择数据文件');
  const form = new FormData(); form.set('file', file); form.set('task_type', task);
  const result = (await api.request(`/workspaces/${draft.workspaceId}/dataset-column-inspection`, { method: 'POST', body: form })).data;
  if (draft.file !== file || draft.task_type !== task) throw new Error('文件已变化，请重新识别字段');
  draft.inspection = result; draft.columnMapping = result.suggested_mapping; draft.preview = null;
}

export async function previewImport(api, draft) {
  if (!draft.file) throw new Error("请选择数据文件");
  const file = draft.file, task = draft.task_type, mapping = JSON.stringify(draft.columnMapping ?? null);
  const form = new FormData(); form.set("file", draft.file); form.set("task_type", draft.task_type);
  if (draft.columnMapping) form.set('column_mapping', mapping);
  const result = (await api.request(`/workspaces/${draft.workspaceId}/dataset-previews`, { method: "POST", body: form })).data;
  if (draft.file !== file || draft.task_type !== task || JSON.stringify(draft.columnMapping ?? null) !== mapping) throw new Error('文件或映射已变化，请重新预览');
  draft.preview = result;
  return draft.preview;
}

export async function persistImport(api, draft) {
  if (!draft.file) throw new Error("请选择数据文件");
  if (!draft.name.trim()) throw new Error("请填写数据集名称");
  if (!draft.preview) await previewImport(api, draft);
  const base = `/workspaces/${draft.workspaceId}`;
  // 保留已创建的资产ID，网络或上传失败后可重试同一资产。
  if (!draft.datasetId) draft.datasetId = (await api.request(base + "/datasets", { method: "POST", body: { name: draft.name, task_type: draft.task_type, description: draft.description || "" } })).data.id;
  const form = new FormData(); form.set("file", draft.file);
  if (draft.columnMapping) form.set('column_mapping', JSON.stringify(draft.columnMapping));
  await api.request(base + `/datasets/${draft.datasetId}/versions`, { method: "POST", body: form });
  return `/datasets/${draft.datasetId}`;
}
