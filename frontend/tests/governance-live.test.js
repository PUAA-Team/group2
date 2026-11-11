import test from 'node:test';
import assert from 'node:assert/strict';
import { governanceDialog, historyHtml, saveGovernance } from '../live/governance.js';

test('共享预算区分空值与零，保存版本号', async () => {
  let request;
  const api = { async request(path, value) { request = { path, ...value }; } };
  const form = new FormData(); form.set('gpu_count', '0'); form.set('concurrent_jobs', ''); form.set('storage_gib', '5');
  await saveGovernance(api, { kind: 'gov-group-budget', item: { id: 'g1', budget: { revision: 3 } } }, form);
  assert.deepEqual(request.body, { revision: 3, gpu_count: 0, concurrent_jobs: null, storage_gib: 5 });
});

test('归档使用所属空间及资产版本', async () => {
  let body, path;
  await saveGovernance({ async request(p, options) { path = p; body = options.body; } },
    { kind: 'gov-archive', item: { id: 'm1', workspace_id: 'w2', assetKind: 'models', revision: 7, archived: false } }, new FormData());
  assert.equal(path, '/workspaces/w2/models/m1/archive'); assert.deepEqual(body, { revision: 7, archived: true });
});

test('执行核查不自动确认，节点未暂停时不提供提交', async () => {
  const item = { execution: { id: 'e1' }, job: { revision: 2 }, node: { enabled: false, online: false, active_executions: [] } };
  const dialog = governanceDialog({ kind: 'gov-review', item });
  assert.ok(!dialog.fields.includes('checked')); assert.equal(dialog.readOnly, false);
  assert.equal(governanceDialog({ kind: 'gov-review', item: { ...item, node: { ...item.node, enabled: true } } }).readOnly, true);
  await assert.rejects(() => saveGovernance({}, { kind: 'gov-review', item }, new FormData()), /进程已经退出/);
});

test('历史采样缺失和间隔会断线，零利用率正常保留', () => {
  const html = historyHtml({ sampling_seconds: 30, points: [
    { at: '2026-10-31T00:00:00Z', utilization: 0 }, { at: '2026-10-31T00:00:30Z', utilization: null },
    { at: '2026-10-31T00:01:00Z', utilization: 50 }, { at: '2026-10-31T00:10:00Z', utilization: 80 },
  ] });
  assert.equal((html.match(/<polyline/g) || []).length, 3); assert.ok(html.includes('0.0%'));
  assert.match(historyHtml({ points: [] }), /暂无历史采样/);
});
