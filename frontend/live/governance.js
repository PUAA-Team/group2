import { btn, date, e, fieldsInfo, input, options, select } from './components.js?v=stage15-1';
import { devicePurposes } from './labels.js?v=stage15-1';

export const reviewButton = (ctx, job) => ctx.session?.user?.is_admin && ctx.session?.access?.actions?.includes('resources.manage') && job.execution ?
  btn(job.execution.finished_at ? '核查记录' : '执行核查', 'gov-review', job.execution.id) : '';

export function historyHtml(history, kind = 'cpu') {
  const points = history?.points || [];
  if (!points.length) return '<div class="empty-state">暂无历史采样</div>';
  const times = points.map(p => Date.parse(p.at)), start = times[0], end = times.at(-1);
  const gap = history.sampling_seconds * (history.stride || 1) * 2000;
  const colors = ['#1664c0', '#276d62'];
  const series = [p => p.utilization, p => p.used_memory_mb == null || !p.memory_mb ? null : p.used_memory_mb / p.memory_mb * 100];
  const lines = series.map((value, index) => {
    const segments = []; let segment = [], previous = null;
    for (let i = 0; i < points.length; i++) {
      const val = value(points[i]);
      if (previous !== null && times[i] - previous > gap || !Number.isFinite(val)) {
        if (segment.length) segments.push(segment); segment = [];
      }
      if (Number.isFinite(val)) segment.push({ x: 48 + (times[i] - start) / Math.max(1, end - start) * 520,
        y: 178 - Math.max(0, Math.min(100, val)) * 1.5, val, at: points[i].at });
      previous = times[i];
    }
    if (segment.length) segments.push(segment);
    return segments.map(part => `<polyline fill="none" stroke="${colors[index]}" stroke-width="2" points="${part.map(p => `${p.x},${p.y}`).join(' ')}"/>` + part.map(p => `<circle cx="${p.x}" cy="${p.y}" r="3" fill="${colors[index]}"><title>${e(date(p.at))} ${p.val.toFixed(1)}%</title></circle>`).join('')).join('');
  }).join('');
  return `<section class="execution-chart"><div class="section-heading"><h2>历史监控</h2><div class="heading-actions"><span class="chart-legend" style="--line:${colors[0]}">利用率</span><span class="chart-legend" style="--line:${colors[1]}">${kind === 'cuda' ? '显存' : '内存'}</span></div></div><svg viewBox="0 0 600 210" role="img" aria-label="真实资源历史采样">${[0, 50, 100].map(n => `<text x="40" y="${183 - n * 1.5}" text-anchor="end">${n}%</text><line x1="48" x2="568" y1="${178 - n * 1.5}" y2="${178 - n * 1.5}" stroke="#e6eaf0"/>`).join('')}${lines}<text x="48" y="203">${e(new Date(start).toLocaleTimeString('zh-CN'))}</text><text x="568" y="203" text-anchor="end">${e(new Date(end).toLocaleTimeString('zh-CN'))}</text></svg></section>`;
}

export function governanceDialog(modal) {
  const item = modal.item || {};
  if (modal.kind === 'gov-device-policy') {
    const policy = item.policy;
    const controls = (field, title, items) => `<fieldset class="live-check-field"><legend>${title}</legend><div class="live-checks">${items.map(p => `<label><input type="checkbox" name="${field}" value="${e(p.id)}" ${policy[field].includes(p.id) ? 'checked' : ''}/>${e(p.name)}</label>`).join('') || '暂无对象'}</div></fieldset>`;
    return { title: '设备策略', wide: true, fields: select('设备用途', 'purpose', options(Object.entries(devicePurposes), policy.purpose || 'shared')) +
      `<label class="check-item"><input type="checkbox" name="enabled" ${policy.enabled ? 'checked' : ''}/>允许新任务使用</label>` +
      controls('allow_users', '允许用户', item.principals.users) + controls('allow_groups', '允许用户组', item.principals.groups) +
      controls('deny_users', '禁止用户', item.principals.users) + controls('deny_groups', '禁止用户组', item.principals.groups) };
  }
  if (modal.kind === 'gov-group-budget') return { title: '用户组共享预算', fields:
    [['gpu_count', 'GPU 数量'], ['concurrent_jobs', '并发任务'], ['storage_gib', '存储 GiB']].map(([key, text]) =>
      input(text, key, item.budget[key] ?? '', 'type="number" min="0" step="1" placeholder="不另设上限"')).join('') +
      fieldsInfo([['已占并发', e(item.budget.usage.concurrent_jobs)], ['已占 GPU', e(item.budget.usage.gpu_count)], ['已存文件', `${(item.budget.usage.storage_bytes / 1048576).toFixed(2)} MiB`]]) };
  if (modal.kind === 'gov-archive') return { title: item.archived ? '恢复资产' : '归档资产', fields: `<div>${e(item.name)}</div>`, submit: item.archived ? '恢复' : '归档' };
  if (modal.kind === 'gov-delete') return { title: '彻底删除资产', fields: `<div class="notice">将永久删除已归档资产「${e(item.name)}」及其版本文件，且不可恢复。</div>`, submit: '确认删除' };
  if (modal.kind === 'gov-review') {
    const blocked = item.review || item.execution.finished_at || item.node.enabled || item.node.online && item.node.active_executions.includes(item.execution.id);
    return { title: '执行核查', wide: true, readOnly: !!blocked, submit: '确认结案', fields:
      fieldsInfo([['任务', e(item.job.name)], ['节点', e(item.node.name)], ['最近心跳', date(item.node.last_seen_at)], ['接收任务', item.node.enabled ? '启用' : '暂停'], ['上报执行', item.node.active_executions.map(e).join(' / ') || '无']]) +
      (blocked ? `<div class="notice">${item.review ? e(item.review.reason) : item.execution.finished_at ? '执行已结束' : item.node.enabled ? '请先暂停节点接收任务' : '在线节点仍上报该执行，请先核查并停止进程'}</div>` :
        '<div class="notice">结案会释放设备占用。请先在目标机器确认训练或服务进程已经退出。</div>' +
        select('结案状态', 'outcome', options([['failed', '失败'], ['stopped', '已停止']])) +
        '<div class="field"><label for="review-reason">核查原因</label><textarea id="review-reason" class="textarea" name="reason" required minlength="5" maxlength="1000" rows="3"></textarea></div><label class="check-item"><input type="checkbox" name="process_exit_confirmed" required/>已在目标机器核实进程退出</label>') };
  }
  return null;
}

export async function saveGovernance(api, modal, form) {
  const item = modal.item || {}; let path, body;
  if (modal.kind === 'gov-device-policy') {
    path = `/resources/devices/${item.id}/policy`;
    body = { revision: item.policy.revision, enabled: form.has('enabled'),
      ...(form.has('purpose') ? { purpose: form.get('purpose') } : {}),
      ...Object.fromEntries(['allow_users', 'allow_groups', 'deny_users', 'deny_groups'].map(key => [key, form.getAll(key)])) };
  } else if (modal.kind === 'gov-group-budget') {
    path = `/admin/groups/${item.id}/budget`;
    body = { revision: item.budget.revision, ...Object.fromEntries(['gpu_count', 'concurrent_jobs', 'storage_gib'].map(key => [key, String(form.get(key) ?? '').trim() === '' ? null : Number(form.get(key))])) };
  } else if (modal.kind === 'gov-archive') {
    path = `/workspaces/${item.workspace_id}/${item.assetKind}/${item.id}/archive`;
    body = { revision: item.revision, archived: !item.archived };
  } else if (modal.kind === 'gov-delete') {
    await api.request(`/workspaces/${item.workspace_id}/${item.assetKind}/${item.id}`, { method: 'DELETE' });
    return { destination: `/${item.assetKind}` };
  } else if (modal.kind === 'gov-review') {
    if (!form.has('process_exit_confirmed')) throw new Error('请先核实目标机器上的进程已经退出');
    path = `/admin/executions/${item.execution.id}/reconcile`;
    body = { revision: item.job.revision, outcome: form.get('outcome'), reason: form.get('reason'), process_exit_confirmed: true };
  } else return null;
  await api.request(path, { method: 'POST', body }); return {};
}

export async function governanceAction(action, id, { api, ctx, openModal }) {
  if (!action.startsWith('gov-')) return false;
  if (action === 'gov-device-policy') {
    const [policy, principals] = await Promise.all([api.request(`/resources/devices/${id}/policy`), api.request('/admin/resource-principals')]);
    openModal(action, { id, policy: policy.data, principals: principals.data });
  } else if (action === 'gov-group-budget') openModal(action, { id, budget: (await api.request(`/admin/groups/${id}/budget`)).data });
  else if (action === 'gov-review') openModal(action, (await api.request(`/admin/executions/${id}/review`)).data);
  else if (action === 'gov-archive' || action === 'gov-delete') openModal(action, { ...ctx.data.item, assetKind: ctx.path.startsWith('/models/') ? 'models' : 'datasets' });
  else return false;
  return true;
}
