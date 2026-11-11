import test from 'node:test';
import assert from 'node:assert/strict';
import { renderProjectDetail, projectDialog, saveProject } from '../live/projects.js';
import { queryDialog, saveQuery, auditExport } from '../live/query-controls.js';
import { renderKeys, keyExample, keyDialog, saveKey } from '../live/key-management.js';
import { renderEvaluationReport } from '../live/results.js';
import { renderAssetCatalog } from '../live/catalog.js';

test('项目详情保留历史任务，归档项目不提供新训练，资料用弹窗修改', async () => {
  const item = { id: 'p1', name: '<项目>', description: '真实说明', archived: true, revision: 2, recent_jobs: [{ id: 'j1', name: '历史', status: 'succeeded' }] };
  const ctx = { access: { actions: ['training.read', 'training.write'] }, data: { project: item } };
  const html = renderProjectDetail(ctx);
  assert.ok(html.includes('&lt;项目&gt;') && html.includes('#/runs/j1') && html.includes('恢复项目'));
  assert.ok(!html.includes('新建训练'));
  assert.ok(projectDialog({ kind: 'project-edit', item }).fields.includes('name="description"'));
  let request;
  const form = new FormData(); form.set('name', '新名'); form.set('description', '新说明');
  await saveProject({ async request(path, options) { request = { path, ...options }; return { data: item }; } }, { kind: 'project-edit', item, workspaceId: 'w1' }, form);
  assert.equal(request.revision, 2); assert.equal(request.method, 'PATCH'); assert.equal(request.body.description, '新说明');
});

test('筛选弹窗保持空间和搜索词，导出携带同一条件，日期反向拒绝', async () => {
  const item = { path: '/admin/audit', params: [['q', 'jobs'], ['space', 'w1'], ['page', '3']] };
  assert.ok(queryDialog({ kind: 'query-filter', item }).fields.includes('操作代码'));
  const form = new FormData(); form.set('creator', '李'); form.set('created_from', '2026-11-01'); form.set('created_to', '2026-11-02'); form.set('action', 'jobs.create');
  const result = await saveQuery(null, { kind: 'query-filter', item }, form);
  const params = new URLSearchParams(result.destination.split('?')[1]);
  assert.equal(params.get('space'), 'w1'); assert.equal(params.get('q'), 'jobs'); assert.equal(params.get('page'), null);
  const download = auditExport({ params, q: 'jobs' });
  assert.ok(download.includes('creator=') && download.includes('action=jobs.create') && download.includes('created_from=2026-11-01'));
  form.set('created_from', '2026-11-03'); await assert.rejects(saveQuery(null, { kind: 'query-filter', item }, form), /开始日期/);
});

test('密钥列表仅显示标识与实际记录数，示例不嵌入真实凭据', () => {
  const key = { id: 'key_12345678', name: '应用', job_id: 'j1', expires_at: '2030-01-01T00:00:00Z', recorded_calls: 0, key: 'do-not-show', token_digest: 'private-digest-4f78da' };
  const ctx = { origin: 'https://example.com', workspace: { id: 'w1' }, params: new URLSearchParams(), access: { actions: ['services.write'] }, data: { data: [key], services: [{ id: 'j1', name: '服务', snapshot: { task_type: 'text_classification' } }] } };
  const html = renderKeys(ctx); assert.ok(html.includes('已记录调用') && html.includes('••••12345678') && html.includes('有效期'));
  assert.ok(!html.includes('do-not-show') && !html.includes('private-digest-4f78da'));
  const sample = keyExample(ctx, key);
  assert.ok(sample.command.includes('${MT_API_KEY}') && sample.command.includes('${CALL_ID}') && !sample.command.includes('\n+'));
  assert.deepEqual(JSON.parse(sample.request), { text: '待推理文本' });
  assert.equal(keyDialog({ kind: 'keys-example', item: sample }).readOnly, true);
});

test('到期调整带revision，转换为有时区时间', async () => {
  let body;
  const form = new FormData(); form.set('expires_at', new Date(Date.now() + 86400000).toISOString().slice(0, 16));
  await saveKey({ async request(path, options) { body = options; } }, { kind: 'keys-expiry', workspaceId: 'w1', item: { id: 'k1', revision: 4 } }, form);
  assert.equal(body.revision, 4); assert.ok(body.body.expires_at.endsWith('Z'));
});

test('评估报告保留零和缺失分类指标，并提供两种下载', () => {
  const html = renderEvaluationReport({ workspace: { id: 'w1' }, data: { evaluationSummary: { job_id: 'j1', per_class: [{ label: '<类>', precision: 0, recall: null, f1: 0, support: 2 }] } } });
  assert.ok(html.includes('0.00%') && html.includes('—') && html.includes('&lt;类&gt;'));
  assert.ok(html.includes('format=json') && html.includes('format=csv'));
  const llm = renderEvaluationReport({ workspace: { id: 'w1' }, data: { evaluationSummary: { job_id: 'j2', per_class: null } } });
  assert.ok(!llm.includes('精确率'));
});

test('普通资产目录同时提供归档和最新数据状态筛选', () => {
  const ctx = { workspace: { id: 'w1' }, params: new URLSearchParams(), access: { actions: [] }, data: { data: [] }, templates: [] };
  const html = renderAssetCatalog('datasets', ctx);
  assert.ok(html.includes('data-query-filter="status"') && html.includes('data-query-filter="version_status"'));
});
