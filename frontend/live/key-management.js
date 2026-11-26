import { badge, btn, can, date, e, fieldsInfo, input, link, options, pageHeader, raw, table } from './components.js?v=stage20a-2';

const localDate = value => { const item = new Date(value); return new Date(item.getTime() - item.getTimezoneOffset() * 60000).toISOString().slice(0, 16); };

export function keyExample(ctx, key) {
  const service = ctx.data.services?.find(row => row.id === key.job_id);
  const image = service?.snapshot?.task_type === 'image_classification';
  const request = JSON.stringify(image ? { image_base64: '<图片Base64>' } : { text: '待推理文本' }, null, 2);
  const base = `${ctx.origin}/api/inference/v1/services/${encodeURIComponent(key.job_id)}`;
  const authorization = 'Authorization: Bearer ${MT_API_KEY}', call = '${CALL_ID}';
  return { request, command: [`curl -X POST "${base}/predict" -H "${authorization}" -H "Content-Type: application/json" --data @request.json`, '',
    `curl "${base}/calls/${call}" -H "${authorization}"`].join('\n') };
}

export function renderKeys(ctx) {
  const write = can(ctx, 'services.write');
  const filters = `<select class="select filter-select" data-query-filter="key_service" aria-label="关联服务">${options([['', '全部服务'], ...(ctx.data.services || []).map(row => [row.id, row.name])], ctx.params?.get('key_service') || '')}</select>` +
    `<select class="select filter-select" data-query-filter="key_status" aria-label="密钥状态">${options([['', '全部状态'], ['active', '启用'], ['expired', '已过期'], ['revoked', '已撤销']], ctx.params?.get('key_status') || '')}</select>`;
  const generated = ctx.generatedKey ? `<div class="notice"><label for="one-time-key">新密钥（仅显示本次）</label><div class="heading-actions"><input id="one-time-key" class="input" readonly value="${e(ctx.generatedKey)}"/>${btn('复制', 'workflow-copy-key')}${btn('关闭', 'workflow-hide-key')}</div></div>` : '';
  const rows = (ctx.data.data || []).map(key => [key.name, key.masked_identifier || '••••' + key.id.slice(-8),
    raw(link(ctx.data.services?.find(service => service.id === key.job_id)?.name || key.job_id, '/runs/' + key.job_id)),
    raw(badge(key.revoked_at ? '停用' : new Date(key.expires_at) <= new Date() ? '已过期' : '启用')),
    key.recorded_calls ?? '—', date(key.last_called_at), date(key.expires_at),
    raw(`<div class="live-row-actions">${btn('接入示例', 'keys-example', key.id)}${write && !key.revoked_at ? btn('有效期', 'keys-expiry', key.id) +
      btn('轮换', 'workflow-rotate-key', key.id, 'secondary', new Date(key.expires_at) <= new Date()) + btn('撤销', 'workflow-revoke-key', key.id) : ''}</div>`) ]);
  return pageHeader('API KEY管理', '', write ? btn('创建密钥', 'modal', 'key-new', 'primary') : '') + generated +
    `<div class="toolbar"><div class="heading-actions">${filters}</div>${btn('刷新', 'refresh')}</div>` +
    table(['名称', '标识', '服务', '状态', '已记录调用', '最近调用', '到期时间', '操作'], rows);
}

export function keyDialog(modal) {
  const item = modal.item || {};
  if (modal.kind === 'keys-expiry') return { title: '调整有效期', fields: fieldsInfo([['密钥', e(item.name)]]) +
    input('到期时间', 'expires_at', localDate(item.expires_at), 'type="datetime-local" required') };
  if (modal.kind === 'keys-example') return { title: '接入示例', readOnly: true, wide: true,
    fields: `<div class="section-heading"><h3>request.json</h3>${btn('复制 JSON', 'keys-copy-json')}</div><pre class="template-preview">${e(item.request)}</pre>` +
      `<div class="section-heading"><h3>调用与查询</h3>${btn('复制示例', 'keys-copy-command')}</div><pre class="template-preview">${e(item.command)}</pre>` };
  return null;
}

export async function keyAction(action, id, { ctx, openModal, toast }) {
  if (!action.startsWith('keys-')) return false;
  if (action.startsWith('keys-copy-')) { await navigator.clipboard.writeText(ctx.ui.modal.item[action === 'keys-copy-json' ? 'request' : 'command']); toast('已复制'); return true; }
  const item = ctx.data.data.find(row => row.id === id);
  if (!item) throw new Error('请刷新密钥列表');
  openModal(action, action === 'keys-example' ? keyExample(ctx, item) : item); return true;
}

export async function saveKey(api, modal, form) {
  if (modal.kind !== 'keys-expiry') return null;
  const value = new Date(form.get('expires_at'));
  if (!Number.isFinite(value.getTime()) || value <= new Date()) throw new Error('请选择未来的到期时间');
  await api.request(`/workspaces/${modal.workspaceId}/service-keys/${modal.item.id}`, { method: 'PATCH', revision: modal.item.revision,
    body: { expires_at: value.toISOString() } });
  return {};
}
