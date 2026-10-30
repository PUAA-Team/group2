export const e = value => String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const paths = {
  menu: '<path d="M4 6h16M4 12h16M4 18h16"/>', chevron: '<path d="m8 10 4 4 4-4"/>',
  plus: '<path d="M12 4v16M4 12h16"/>', search: '<circle cx="10" cy="10" r="6"/><path d="m15 15 6 6"/>',
  close: '<path d="m6 6 12 12M18 6 6 18"/>', refresh: '<path d="M20 10a8 8 0 1 0-2 8M20 3v7h-7"/>',
  back: '<path d="m10 5-7 7 7 7M3 12h18"/>', check: '<path d="m5 12 4 4L19 6"/>',
  server: '<rect x="3" y="4" width="18" height="6"/><rect x="3" y="14" width="18" height="6"/><path d="M7 7h.1M7 17h.1M15 7h3M15 17h3"/>',
  chart: '<path d="M3 3v18h18M6 16l5-7 4 4 5-8"/>', folder: '<path d="M3 6h7l2 3h9v11H3z"/>',
  box: '<path d="m12 3 9 5v9l-9 5-9-5V8zM3 8l9 5 9-5M12 13v9"/>', settings: '<path d="M3 7h18M3 17h18"/><circle cx="8" cy="7" r="3"/><circle cx="16" cy="17" r="3"/>',
  download: '<path d="M12 3v12m-5-5 5 5 5-5M4 17v4h16v-4"/>', bell: '<path d="M5 17h14l-2-4V8a5 5 0 0 0-10 0v5zM10 21h4"/>',
};
export const icon = (name, size = 18) => `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] || paths.box}</svg>`;
export const button = (text, action, kind = '', symbol = '', attrs = '') => `<button type="button" class="btn ${kind}" data-action="${action}" ${attrs}>${symbol ? icon(symbol) : ''}${e(text)}</button>`;
export const link = (text, action, attrs = '') => `<button type="button" class="text-btn" data-action="${action}" ${attrs}>${e(text)}</button>`;
export function status(text) {
  const kind = ['运行中', '使用中'].includes(text) ? 'running' : ['已完成', '空闲'].includes(text) ? 'success' : ['排队中', '待审核'].includes(text) ? 'waiting' : ['失败', '离线'].includes(text) ? 'error' : 'neutral';
  const symbol = kind === 'running' ? '<path d="m6 3 8 5-8 5Z"/>' : kind === 'success' ? '<path d="m3 8 3 3 7-7"/>' : kind === 'waiting' ? '<circle cx="8" cy="8" r="6"/><path d="M8 4v4l3 2"/>' : kind === 'error' ? '<path d="m4 4 8 8M12 4l-8 8"/>' : '<path d="M4 8h8"/>';
  return `<span class="status ${kind}"><svg class="status-symbol" width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${symbol}</svg>${e(text)}</span>`;
}
export function select(name, value, options, label = name) {
  return `<div class="select-wrap"><button type="button" class="select-control" role="combobox" aria-label="${e(label)}" aria-expanded="false" aria-controls="options-${e(name)}" aria-haspopup="listbox"><span class="select-value">${e(value)}</span>${icon('chevron', 16)}</button><input type="hidden" name="${e(name)}" value="${e(value)}"><div id="options-${e(name)}" class="options" role="listbox" aria-label="${e(label)}" hidden>${options.map((opt, i) => `<button type="button" role="option" aria-selected="${opt === value}" tabindex="-1" data-value="${e(opt)}" id="${e(name)}-opt-${i}">${e(opt)}</button>`).join('')}</div></div>`;
}
export function tabs(items, active, action = 'tab') {
  return `<div class="tabs" role="tablist">${items.map(([id, text]) => `<button class="tab" type="button" role="tab" aria-selected="${id === active}" data-action="${action}" data-value="${id}">${e(text)}</button>`).join('')}</div>`;
}
export function chart(metric = 'loss', score = .914) {
  const max = metric === 'loss' ? 1.5 : 1;
  const points = series => Array.from({ length: 25 }, (_, i) => {
    const f = (1 - Math.exp(-i / 7)) / (1 - Math.exp(-24 / 7));
    const value = metric === 'loss' ? 1.4 + ((series ? .387 : .342) - 1.4) * f : .3 + (score + (series ? 0 : .022) - .3) * f;
    return `${54 + i * 26},${218 - value / max * 174}`;
  }).join(' ');
  return `<svg class="metric-chart" viewBox="0 0 720 270" role="img" aria-label="${metric === 'loss' ? 'Loss' : '评估指标'}模拟曲线">${[0, 1, 2, 3].map(i => `<path class="grid-line" d="M54 ${44 + i * 58}H680"/><text x="42" y="${49 + i * 58}" text-anchor="end">${(max - i * max / 3).toFixed(1)}</text>`).join('')}${[0, 1, 2, 3, 4].map(i => `<text x="${54 + i * 156}" y="246" text-anchor="middle">${i * 200}</text>`).join('')}<polyline class="train-line" points="${points(0)}"/><polyline class="eval-line" points="${points(1)}"/><text x="648" y="266">Step</text></svg>`;
}
export const legend = () => '<div class="legend"><span><i></i>训练集</span><span><i></i>验证集</span></div>';
export const empty = (title = '没有匹配的任务') => `<div class="empty">${icon('folder', 38)}<strong>${e(title)}</strong>${button('重置筛选', 'reset')}</div>`;
export const progress = value => `<div class="progress"><i style="width:${Math.min(100, Math.max(0, value))}%"></i></div>`;
export function pagination(count) {
  return `<div class="pagination"><span>共 ${count} 条</span><span>每页 10 条</span><button class="page-btn" disabled aria-label="上一页">‹</button><button class="page-btn current" aria-current="page">1</button><button class="page-btn" disabled aria-label="下一页">›</button></div>`;
}
