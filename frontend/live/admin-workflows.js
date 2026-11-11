import { badge, date, e, link, options, pageHeader, pager, table, tag, toolbar } from './components.js?v=stage15-1';
import { filterControls } from './query-controls.js?v=stage15-1';

export const extraJobView = ctx => ctx.path === '/admin/jobs' && ['operations', 'assistants'].includes(ctx.params.get('job_view'));
export const jobTabs = ctx => `<div class="tabs">${[['', '训练与服务'], ['operations', '数据处理'], ['assistants', '智能请求']].map(([key, text]) => `<a class="tab ${(ctx.params.get('job_view') || '') === key ? 'active' : ''}" href="#/admin/jobs${key ? '?job_view=' + key : ''}">${text}</a>`).join('')}</div>`;
const STATES = { preview: '预览待确认', queued: '排队中', running: '运行中', review: '待发布', published: '已发布', succeeded: '已完成', applied: '已采纳', failed: '失败', cancelled: '已取消' };

export function renderExtraJobs(ctx, spaceFilter) {
  const assistants = ctx.params.get('job_view') === 'assistants';
  const choices = assistants ? ['preview', 'queued', 'running', 'succeeded', 'applied', 'failed', 'cancelled'] : ['queued', 'running', 'review', 'published', 'failed', 'cancelled'];
  const status = `<select class="select filter-select" data-query-filter="status" aria-label="处理状态">${options([['', '全部状态'], ...choices.map(key => [key, STATES[key]])], ctx.params.get('status') || '')}</select>`;
  return pageHeader('作业管理') + jobTabs(ctx) + toolbar(ctx.q, spaceFilter + status + filterControls(ctx)) +
    table(['任务', '类型', '工作空间', '创建人', '状态', ...(assistants ? ['已报告 Token', '错误码'] : []), '创建时间'], (ctx.data.data || []).map(item => [
      link(item.name, `/${assistants ? 'assistants' : 'data-operations'}/${item.id}?workspace=${item.workspace_id}`), tag(item.type_name),
      e(item.workspace_name), e(item.actor_name), badge(STATES[item.status] || item.status),
      ...(assistants ? [e(item.reported_tokens ?? '—'), e(item.error_code || '—')] : []), date(item.created_at)])) + pager(ctx.data.pagination);
}
