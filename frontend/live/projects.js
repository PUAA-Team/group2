import { badge, btn, can, date, description, e, fieldsInfo, input, link, pageHeader, table } from './components.js?v=stage15-1';

export function renderProjectDetail(ctx) {
  const item = ctx.data.project, write = can(ctx, 'training.write');
  const actions = write ? btn('修改资料', 'project-edit') + btn(item.archived ? '恢复项目' : '归档项目', 'project-archive') +
    (!item.archived ? `<a class="btn btn-primary" href="#/train/new?project=${e(item.id)}">新建训练</a>` : '') : '';
  return `<div class="breadcrumb">${link('训练项目', '/projects')}<span>/</span><span>${e(item.name)}</span></div>` + pageHeader(item.name, '', actions) +
    fieldsInfo([['状态', badge(item.archived ? '已归档' : '正常')], ['说明', e(item.description || '—')], ['训练次数', e(item.job_count)],
      ['活跃任务', e(item.active_count)], ['最高准确率', item.best_accuracy == null ? '—' : `${(item.best_accuracy * 100).toFixed(1)}%`], ['创建时间', date(item.created_at)]]) +
    `<div class="section-heading"><h2>最近实验</h2>${link('全部实验', '/runs?project=' + item.id)}</div>` +
    table(['训练任务', '模型', '状态', '创建时间'], (item.recent_jobs || []).map(job => [link(job.name, '/runs/' + job.id), e(job.model_name || '—'),
      badge(({ draft: '草稿', queued: '排队中', preparing: '准备中', running: '运行中', succeeded: '已完成', stopped: '已停止', failed: '失败', cancelled: '已取消', stopping: '停止中' })[job.status] || job.status), date(job.created_at)]));
}

export function projectDialog(modal) {
  const item = modal.item || {};
  if (['project-new', 'project-edit'].includes(modal.kind)) return { title: modal.kind === 'project-new' ? '新建项目' : '修改项目资料',
    fields: input('项目名称', 'name', item.name || '', 'required maxlength="100"') + description(item.description || '') };
  if (modal.kind === 'project-archive') return { title: item.archived ? '恢复项目' : '归档项目', submit: '确认', fields: `<div>${e(item.name)}</div>` };
  return null;
}

export async function projectAction(action, { ctx, openModal }) {
  if (!['project-edit', 'project-archive'].includes(action)) return false;
  openModal(action, ctx.data.project); return true;
}

export async function saveProject(api, modal, form) {
  if (!['project-new', 'project-edit', 'project-archive'].includes(modal.kind)) return null;
  const item = modal.item || {}, base = `/workspaces/${modal.workspaceId}/projects`;
  const archive = modal.kind === 'project-archive';
  const result = await api.request(base + (item.id ? '/' + item.id : '') + (archive ? '/archive' : ''), {
    method: item.id && !archive ? 'PATCH' : 'POST', revision: item.revision,
    body: archive ? { archived: !item.archived } : { name: form.get('name'), description: form.get('description') || '' } });
  return modal.kind === 'project-new' ? { destination: '/projects/' + result.data.id } : {};
}
