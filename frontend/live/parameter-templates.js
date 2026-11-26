import { badge, btn, e, input, raw, table, tag, TASKS } from './components.js?v=stage20a-2';
import { captureDraft, ensureDraft, parameterFields } from './training-wizard.js?v=stage20a-2';

const common = ['epochs', 'batch_size', 'learning_rate', 'validation_ratio', 'seed'];
export function templateConfig(values, task) {
  return Object.fromEntries([...common, ...(task === 'llm_sft' ? ['max_length', 'lora_rank'] : [])].map(key => [key, Number(values[key])]));
}

export function applyTemplateValues(draft, result) {
  const keys = [...common, ...(draft.values.task_type === 'llm_sft' ? ['max_length', 'lora_rank'] : [])];
  for (const key of keys) if (Object.hasOwn(result.config, key)) draft.values[key] = result.config[key];
  draft.dirty = true;
}

export function parameterTemplateDialog(modal) {
  const item = modal.item || {};
  if (modal.kind === 'parameter-template-list') return { title: '参数模板', readOnly: true, wide: true,
    fields: table(['模板', '任务', '状态', '操作'], (item.rows || []).map(row => [row.name, raw(tag(TASKS[row.task_type])),
      raw(badge(row.archived ? '已归档' : '启用')), raw(btn('修改', 'param-edit', row.id) + btn(row.archived ? '恢复' : '归档', 'param-archive', row.id))])) };
  if (['parameter-template-new', 'parameter-template-edit'].includes(modal.kind)) return {
    title: modal.kind === 'parameter-template-new' ? '另存参数模板' : '修改参数模板', wide: true,
    fields: (input('模板名称', 'name', item.name || '', 'required maxlength="100"') + `<div class="heading-actions">${tag(TASKS[item.task_type])}</div>` + parameterFields(item.config, item.task_type === 'llm_sft')).replace(/(for|id)="live-/g, '$1="template-') };
  if (modal.kind === 'parameter-template-archive') return { title: item.archived ? '恢复参数模板' : '归档参数模板',
    fields: `<div>${e(item.name)}</div>`, submit: '确认' };
  return null;
}

export async function parameterTemplateAction(action, id, { api, ctx, openModal, render, toast, form }) {
  if (!action.startsWith('param-')) return false;
  if (ctx.pageBusy) return true;
  const draft = ensureDraft(ctx), base = `/workspaces/${draft.workspaceId}/training-parameter-templates`;
  if (form?.dataset.form === 'training-wizard') captureDraft(draft, new FormData(form));
  const model = ctx.data.options.models.find(item => item.id === draft.values.model_version_id);
  if (action === 'param-new') {
    if (!model) throw new Error('请先选择模型');
    if (!form.reportValidity()) return true;
    openModal('parameter-template-new', { task_type: model.task_type, trainer_id: model.trainer_id, config: templateConfig(draft.values, model.task_type) });
  } else if (action === 'param-manage') {
    const rows = await api.all(base + '?status=all'); ctx.data.parameterTemplates = rows;
    openModal('parameter-template-list', { rows });
  } else if (['param-edit', 'param-archive'].includes(action)) {
    const item = ctx.ui.modal?.item.rows?.find(row => row.id === id);
    if (!item) throw new Error('请重新打开模板管理');
    openModal(action === 'param-edit' ? 'parameter-template-edit' : 'parameter-template-archive', item);
  } else if (action === 'param-apply') {
    const item = ctx.data.parameterTemplates?.find(row => row.id === draft.templateId);
    if (!item || !model) throw new Error('请选择兼容的参数模板');
    ctx.pageBusy = true;
    try {
      const result = (await api.request(base + '/' + item.id + '/resolve', { method: 'POST', revision: item.revision, body: { model_version_id: model.id } })).data;
      if (ctx.wizard !== draft || ctx.workspace?.id !== draft.workspaceId || draft.values.model_version_id !== model.id || draft.templateId !== item.id) throw new Error('训练配置已变化，请重新应用模板');
      applyTemplateValues(draft, result); render(); toast('参数已应用');
    } finally { ctx.pageBusy = false; }
  }
  return true;
}

export async function saveParameterTemplate(api, modal, form, ctx) {
  if (!['parameter-template-new', 'parameter-template-edit', 'parameter-template-archive'].includes(modal.kind)) return null;
  const item = modal.item, base = `/workspaces/${modal.workspaceId}/training-parameter-templates`;
  let result;
  if (modal.kind === 'parameter-template-archive') result = await api.request(base + '/' + item.id + '/archive', {
    method: 'POST', revision: item.revision, body: { archived: !item.archived } });
  else {
    const config = templateConfig(Object.fromEntries(form), item.task_type);
    result = await api.request(base + (item.id ? '/' + item.id : ''), { method: item.id ? 'PATCH' : 'POST', revision: item.revision,
      body: { name: form.get('name'), config, ...(!item.id ? { task_type: item.task_type, trainer_id: item.trainer_id } : {}) } });
  }
  if (ctx.wizard?.workspaceId === modal.workspaceId && !result.data.archived) {
    const model = ctx.data.options?.models.find(row => row.id === ctx.wizard.values.model_version_id);
    if (model?.task_type === result.data.task_type && model.trainer_id === result.data.trainer_id) ctx.wizard.templateId = result.data.id;
  }
  if (result.data.archived && ctx.wizard?.templateId === result.data.id) ctx.wizard.templateId = '';
  return { saved: true };
}
