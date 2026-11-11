import test from 'node:test';
import assert from 'node:assert/strict';
import { inspectImport, previewImport, persistImport } from '../live/dataset-import.js';
import { applyTemplateValues, parameterTemplateDialog, saveParameterTemplate } from '../live/parameter-templates.js';
import { ensureDraft, renderWizard } from '../live/training-wizard.js';

test('字段识别及预览上传使用同一映射，正式上传保留原文件', async () => {
  const file = new File(['body,category\nhello,yes\n'], 'raw.csv');
  const draft = { file, task_type: 'text_classification', workspaceId: 'w1', name: '映射测试' };
  const requests = [];
  const api = { async request(path, options) {
    requests.push({ path, ...options });
    if (path.endsWith('inspection')) return { data: { columns: ['body', 'category'], suggested_mapping: { text: null, label: null } } };
    if (path.endsWith('previews')) return { data: { sha256: 'normalized', samples: [{ text: 'hello', label: 'yes' }] } };
    return { data: { id: 'dat1' } };
  } };
  await inspectImport(api, draft);
  assert.equal(draft.preview, null);
  draft.columnMapping = { text: 'body', label: 'category' };
  await previewImport(api, draft); await persistImport(api, draft);
  const preview = requests.find(row => row.path.endsWith('previews'));
  const upload = requests.find(row => row.path.endsWith('/versions'));
  assert.equal(preview.body.get('column_mapping'), upload.body.get('column_mapping'));
  assert.equal(upload.body.get('file'), file);
});

test('预览返回前修改映射或文件，不采纳过时结果', async () => {
  const draft = { file: new File(['body\na'], 'raw.csv'), workspaceId: 'w1', task_type: 'text_classification', columnMapping: { text: 'body' } };
  let resolve;
  const pending = previewImport({ request() { return new Promise(done => { resolve = done; }); } }, draft);
  draft.columnMapping.text = 'other'; resolve({ data: { samples: [{ text: '过时' }] } });
  await assert.rejects(pending, /重新预览/); assert.equal(draft.preview, undefined);
});

test('模板只应用参数，保留草稿名称、数据、模型和节点', () => {
  const values = { name: '任务', task_type: 'text_classification', model_version_id: 'm1', dataset_version_id: 'd1', node_id: 'n1', priority: 6, epochs: 1 };
  const draft = { values, created: { id: 'j1' } };
  applyTemplateValues(draft, { config: { epochs: 3, learning_rate: 0.02, name: '不能覆盖', node_id: '不能覆盖', max_length: 512 } });
  assert.equal(values.epochs, 3); assert.equal(values.name, '任务'); assert.equal(values.node_id, 'n1');
  assert.equal(values.model_version_id, 'm1'); assert.equal(values.dataset_version_id, 'd1'); assert.equal(values.max_length, undefined);
  assert.equal(draft.created.id, 'j1'); assert.equal(draft.dirty, true);
});

test('模板编辑与归档通过弹窗、版本号及空间限定接口保存', async () => {
  const modal = { kind: 'parameter-template-edit', workspaceId: 'w1', item: { id: 't1', name: '<b>模板</b>', revision: 3, task_type: 'text_classification', trainer_id: 'text-classifier-v1', config: { epochs: 3 } } };
  const dialog = parameterTemplateDialog(modal);
  assert.ok(dialog.fields.includes('&lt;b&gt;模板&lt;/b&gt;') && dialog.fields.includes('name="epochs"'));
  const form = new FormData();
  for (const [key, value] of Object.entries({ name: '更新', epochs: 2, batch_size: 4, learning_rate: 0.01, validation_ratio: 0.2, seed: 42 })) form.set(key, value);
  let request;
  const api = { async request(path, options) { request = { path, ...options }; return { data: { ...modal.item, config: options.body.config } }; } };
  await saveParameterTemplate(api, modal, form, {});
  assert.equal(request.path, '/workspaces/w1/training-parameter-templates/t1'); assert.equal(request.revision, 3);
  assert.equal(request.body.config.epochs, 2); assert.equal(request.body.config.max_length, undefined);
  assert.equal(parameterTemplateDialog({ kind: 'parameter-template-list', item: { rows: [] } }).readOnly, true);
  const list = parameterTemplateDialog({ kind: 'parameter-template-list', item: { rows: [{ ...modal.item, archived: false }] } });
  assert.ok(list.fields.includes('badge-success'), '启用模板使用已确认的成功状态符号');
});

test('模板弹窗参数与底层向导不重复使用输入框ID，标签指向各自字段', () => {
  const ctx = { workspace: { id: 'w1' }, params: new URLSearchParams(), access: { actions: ['training.write'] },
    data: { options: { models: [{ id: 'm1', name: '模型', version: 'v1', task_type: 'text_classification', trainer_id: 'text-classifier-v1' }], datasets: [] } } };
  ensureDraft(ctx).step = 2;
  const page = renderWizard(ctx);
  const modal = parameterTemplateDialog({ kind: 'parameter-template-new', item: { task_type: 'text_classification', config: ctx.wizard.values } });
  const pageIds = new Set([...page.matchAll(/\bid="([^"]+)"/g)].map(match => match[1]));
  const modalIds = [...modal.fields.matchAll(/\bid="([^"]+)"/g)].map(match => match[1]);
  assert.ok(modalIds.every(id => !pageIds.has(id)));
  assert.ok(modalIds.every(id => modal.fields.includes(`for="${id}"`)));
});
