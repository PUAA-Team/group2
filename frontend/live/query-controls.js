import { btn, e, input, tag } from './components.js?v=stage15-1';

const KEYS = ['creator', 'created_from', 'created_to', 'action'];
const LABELS = { creator: '创建人', created_from: '开始日期', created_to: '结束日期', action: '操作代码' };

export function filterControls(ctx) {
  const values = KEYS.filter(key => ctx.params?.get(key)).map(key => tag(`${key === 'creator' && ctx.path === '/admin/audit' ? '操作者' : LABELS[key]}：${ctx.params.get(key)}`)).join('');
  return btn('筛选', 'query-filter') + values + (values ? btn('清除筛选', 'query-clear') : '');
}

export function queryDialog(modal) {
  if (modal.kind !== 'query-filter') return null;
  const item = modal.item;
  return { title: '筛选条件', submit: '应用筛选', fields: input(item.path === '/admin/audit' ? '操作者名称' : '创建人名称', 'creator', item.creator || '', 'maxlength="100"') +
    `<div class="live-field-grid">${input('开始日期', 'created_from', item.created_from || '', 'type="date"')}${input('结束日期', 'created_to', item.created_to || '', 'type="date"')}</div>` +
    (item.path === '/admin/audit' ? input('操作代码', 'action', item.action || '', 'maxlength="100"') : '') };
}

function destination(item, form) {
  const params = new URLSearchParams(item.params);
  for (const key of KEYS) {
    const value = String(form.get(key) || '').trim(); value ? params.set(key, value) : params.delete(key);
  }
  if (params.get('created_from') && params.get('created_to') && params.get('created_from') > params.get('created_to')) throw new Error('开始日期不能晚于结束日期');
  params.delete('page'); return item.path + (params.size ? '?' + params : '');
}

export async function queryAction(action, { ctx, openModal, navigate }) {
  if (!['query-filter', 'query-clear'].includes(action)) return false;
  const item = { path: ctx.path, params: [...ctx.params], ...Object.fromEntries(KEYS.map(key => [key, ctx.params.get(key) || ''])) };
  if (action === 'query-filter') openModal('query-filter', item);
  else navigate(destination(item, new FormData()));
  return true;
}

export async function saveQuery(api, modal, form) {
  return modal.kind === 'query-filter' ? { destination: destination(modal.item, form) } : null;
}

export function auditExport(ctx) {
  const params = new URLSearchParams();
  for (const key of ['q', 'space', 'status', ...KEYS]) if (ctx.params?.get(key)) params.set(key, ctx.params.get(key));
  if (ctx.q) params.set('q', ctx.q);
  return `<a class="btn btn-secondary" href="/api/v1/admin/audit-export?${e(params.toString())}">导出 CSV</a>`;
}
