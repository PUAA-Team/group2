import test from 'node:test';
import assert from 'node:assert/strict';
import { loadManagement, renderManagement } from '../live/administration.js';

test('作业管理数据处理与智能请求使用全局元数据查询', async () => {
  for (const view of ['operations', 'assistants']) {
    const ctx = { path: '/admin/jobs', params: new URLSearchParams({ job_view: view, space: 'w2' }), workspaces: [], data: { data: [] } };
    let endpoint;
    await loadManagement({ async request(path) { endpoint = path; return {}; } }, ctx);
    assert.ok(endpoint.startsWith(`/admin/workflow-catalog/${view}?`) && endpoint.includes('space=w2'));
    ctx.data.data = [{ id: 'a1', workspace_id: 'w2', name: '<unsafe>', type_name: '处理', status: 'queued', reported_tokens: 0, messages: 'hidden-message', result: 'hidden-result' }];
    const html = renderManagement(ctx);
    assert.ok(html.includes('&lt;unsafe&gt;') && !html.includes('hidden-'));
    assert.ok(html.includes('/admin/jobs?job_view=operations') && html.includes('/admin/jobs?job_view=assistants'));
    assert.ok(html.includes(`${view === 'operations' ? '/data-operations/' : '/assistants/'}a1?workspace=w2`));
  }
});

test('审计支持失败筛选，展示错误码与请求编号', () => {
  const ctx = { path: '/admin/audit', params: new URLSearchParams({ status: 'failure' }), workspaces: [], data: { data: [{
    id: 'a1', action: 'datasets.create', result: 'failure', error_code: 'STORAGE_LIMIT', request_id: 'request-123', body: 'hidden-request',
  }] } };
  const html = renderManagement(ctx);
  assert.ok(html.includes('STORAGE_LIMIT') && html.includes('request-123') && html.includes('value="failure" selected'));
  assert.ok(!html.includes('hidden-request'));
});
