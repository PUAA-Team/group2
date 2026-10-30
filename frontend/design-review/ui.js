import { navigation, adminNavigation, pages, schemes } from './data.js';

export const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

const symbols = {
  home: '<path d="m3 10 9-7 9 7v10H3z"/><path d="M9 20v-7h6v7"/>',
  data: '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 4 16 4 16 0V5M4 12c0 4 16 4 16 0"/>',
  training: '<path d="M4 17h3l3-9 4 12 3-7h3M4 4h16v16H4z"/>',
  model: '<path d="m12 3 9 5v9l-9 5-9-5V8zM3 8l9 5 9-5M12 13v9"/>',
  service: '<rect x="3" y="4" width="18" height="6" rx="2"/><rect x="3" y="14" width="18" height="6" rx="2"/><path d="M7 7h.1M7 17h.1M16 7h2M16 17h2"/>',
  chevron: '<path d="m9 5 7 7-7 7"/>',
  plus: '<path d="M12 4v16M4 12h16"/>',
  search: '<circle cx="10" cy="10" r="6"/><path d="m15 15 6 6"/>',
  menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
  close: '<path d="m6 6 12 12M18 6 6 18"/>',
  check: '<path d="m4 12 5 5L20 6"/>',
  arrow: '<path d="M4 12h16m-6-6 6 6-6 6"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 6v6l4 2"/>',
  cloud: '<path d="M7 18h12a4 4 0 0 0 0-8 7 7 0 0 0-13-1 5 5 0 0 0 1 9Z"/>',
  settings: '<path d="M4 7h16M4 17h16"/><circle cx="8" cy="7" r="3"/><circle cx="16" cy="17" r="3"/>',
};
export function icon(name, size = 18) {
  return `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${symbols[name] || symbols.model}</svg>`;
}

export function status(text) {
  const color = ['运行中', '使用中'].includes(text) ? 'active' : ['已完成', '空闲', '已就绪'].includes(text) ? 'success' : ['排队中', '待审核'].includes(text) ? 'waiting' : ['失败', '离线'].includes(text) ? 'error' : 'neutral';
  return `<span class="status ${color}"><i></i>${escapeHtml(text)}</span>`;
}

export function button(label, action, primary = false, symbol = '') {
  return `<button class="button ${primary ? 'primary' : ''}" data-action="${action}">${symbol ? icon(symbol, 16) : ''}${escapeHtml(label)}</button>`;
}

export function reviewBar(state) {
  return `<div class="review-bar"><a href="#/gallery" class="review-brand">界面审查</a><div class="scheme-switch" aria-label="切换设计方案">${schemes.map(s => `<a href="#/${s.id}/${state.page}" ${state.scheme === s.id ? 'aria-current="true"' : ''}>${s.code}<span>${s.name}</span></a>`).join('')}</div><span class="demo-flag">模拟数据</span><a class="back-original" href="http://127.0.0.1:8765/#/home" target="_blank" rel="noopener">原版</a></div>`;
}

export function sidebar(state) {
  const groups = navigation.map(group => `<section class="nav-group ${state.groups[group.id] !== false ? 'open' : ''}"><button class="nav-parent" data-action="toggle-group" data-group="${group.id}" aria-expanded="${state.groups[group.id] !== false}">${icon(group.icon)}<span>${group.name}</span>${icon('chevron', 13)}</button><div class="nav-children">${group.children.map(([name, page]) => `<a href="${page === 'scope' ? '#' : `#/${state.scheme}/${page}`}" ${page === 'scope' ? `data-action="scope" data-scope="${name}"` : ''} class="nav-child ${page === state.page && page !== 'resources' ? 'current' : ''}" ${page === state.page && page !== 'resources' ? 'aria-current="page"' : ''}>${name}${name === '训练任务' ? `<span class="nav-count">${state.runCount ?? 6}</span>` : ''}</a>`).join('')}</div></section>`).join('');
  return `<aside class="sidebar"><a class="brand" href="#/${state.scheme}/home"><span class="brand-symbol">${icon('model', 24)}</span><strong>模训平台</strong></a><div class="space-selector"><span class="space-avatar">研</span><div><strong>研发空间</strong><span>平台管理员</span></div>${icon('chevron', 12)}</div><nav class="sidebar-scroll" aria-label="主导航">${groups}<div class="admin-divider">管理</div>${adminNavigation.map((name, i) => `<a class="nav-admin ${name === '资源管理' && state.page === 'resources' ? 'current' : ''}" href="${name === '资源管理' ? `#/${state.scheme}/resources` : '#'}" ${name === '资源管理' ? '' : `data-action="scope" data-scope="${name}"`}>${icon(i === 1 ? 'service' : i === 7 ? 'settings' : 'model', 15)}<span>${name}</span></a>`).join('')}</nav><div class="sidebar-footer"><span class="user-avatar">管</span><span>平台管理员</span><button class="icon-button" data-action="collapse" aria-label="收窄或展开菜单">${icon('menu', 17)}</button></div></aside>`;
}

export function shell(state, body) {
  const page = pages.find(x => x.id === state.page);
  return `${reviewBar(state)}<div class="app-shell ${state.collapsed ? 'collapsed' : ''} ${state.mobileOpen ? 'menu-open' : ''}">${sidebar(state)}<button class="sidebar-overlay" aria-label="关闭菜单" data-action="mobile-menu"></button><main class="main"><header class="context-bar"><button class="icon-button mobile-menu" data-action="mobile-menu" aria-label="打开菜单">${icon('menu')}</button><div class="context-path"><span>研发空间</span>${icon('chevron', 12)}<strong>${page.name}</strong></div><a href="#/${state.scheme}/resources" class="connection"><i></i>计算资源已连接</a><button class="icon-button desktop-collapse" data-action="collapse" aria-label="收窄或展开菜单">${icon('menu', 17)}</button></header><div class="page-switch" aria-label="审查页面">${pages.map(p => `<a href="#/${state.scheme}/${p.id}" ${state.page === p.id ? 'aria-current="page"' : ''}>${p.name}</a>`).join('')}</div><div class="content" data-page="${state.page}">${body}</div></main></div>`;
}

export function heading(title, actions = '') {
  return `<div class="page-heading"><h1>${escapeHtml(title)}</h1><div class="heading-actions">${actions}</div></div>`;
}

export function summaryStrip(items) {
  return `<div class="summary-strip">${items.map(([name, value, suffix = '']) => `<div><span>${name}</span><strong>${value}<small>${suffix}</small></strong></div>`).join('')}</div>`;
}

export function runTable(runs, scheme, compact = false) {
  return `<div class="table-scroll"><table class="data-table ${compact ? 'compact' : ''}"><thead><tr><th>训练任务</th><th>状态</th><th>进度</th><th>指标</th><th>资源</th><th>时长</th><th></th></tr></thead><tbody>${runs.map(run => `<tr><td><a class="run-name" href="#/${scheme}/run" data-run="${run.id}">${escapeHtml(run.name)}</a><span class="row-meta">${escapeHtml(run.model)}<span>${run.id}</span></span></td><td>${status(run.status)}</td><td><div class="progress-label"><span>${run.progress}%</span><div class="progress"><i style="width:${run.progress}%"></i></div></div></td><td><strong class="number">${run.score}</strong><span class="row-meta">${run.metric}</span></td><td>${run.gpu}</td><td class="nowrap">${run.duration}</td><td><a class="row-open" href="#/${scheme}/run" data-run="${run.id}" aria-label="查看${escapeHtml(run.name)}">${icon('chevron', 16)}</a></td></tr>`).join('') || '<tr><td colspan="7" class="empty-cell">没有匹配的训练任务</td></tr>'}</tbody></table></div>`;
}

export function runFilters(state) {
  return `<div class="list-toolbar"><div class="filter-tabs" aria-label="任务状态筛选">${['全部', '运行中', '排队中', '已完成', '失败'].map(filter => `<button data-action="filter" data-filter="${filter}" class="${state.filter === filter ? 'selected' : ''}" aria-pressed="${state.filter === filter}">${filter}</button>`).join('')}</div><label class="search">${icon('search', 16)}<input id="run-search" aria-label="搜索任务" placeholder="搜索任务或模型" value="${escapeHtml(state.query)}" /></label></div>`;
}

export function sparkline(seed = 0, rising = false) {
  const points = Array.from({ length: 24 }, (_, i) => `${i * 4.9},${rising ? 36 - i * 1.1 + Math.sin(i + seed) * 4 : 9 + i * .8 + Math.sin(i * 1.4 + seed) * 4}`).join(' ');
  return `<svg class="sparkline" viewBox="0 0 118 45" aria-hidden="true"><polyline points="${points}" fill="none" stroke="currentColor" stroke-width="1.8"/></svg>`;
}

export function chart(metric = 'loss', compare = false, metricLabel = 'F1', finalScore = .914) {
  const rising = metric !== 'loss';
  const x = i => 48 + i * (662 * .85 / 28);
  const y = (i, secondary) => {
    const fraction = (1 - Math.exp(-i / 9)) / (1 - Math.exp(-28 / 9));
    const noise = i === 0 || i === 28 ? 0 : Math.sin(i * 1.9) * .035 * (1 - i / 28);
    const end = rising ? finalScore + (secondary ? -.012 : compare ? 0 : .022) : secondary ? compare ? .4058 : .3868 : .3418;
    const value = rising ? .31 + (end - .31) * fraction + noise : 1.45 + (end - 1.45) * fraction + noise;
    return rising ? 200 - (value - .25) / .75 * 150 : 200 - value / 1.5 * 150;
  };
  const points = offset => Array.from({ length: 29 }, (_, i) => `${x(i).toFixed(1)},${y(i, offset).toFixed(1)}`).join(' ');
  return `<svg class="line-chart" viewBox="0 0 750 280" role="img" aria-label="${rising ? escapeHtml(metricLabel) : 'Loss'}演示曲线"><g>${[50, 100, 150, 200].map((line, i) => `<path d="M48 ${line}H710" class="chart-grid"/><text x="31" y="${line + 4}" text-anchor="end">${rising ? [1, .75, .5, .25][i] : [1.5, 1, .5, 0][i]}</text>`).join('')}${[0, 1, 2, 3, 4].map((n, i) => `<text x="${48 + i * 165}" y="246" text-anchor="middle">${n * 200}</text>`).join('')}<text x="690" y="269">Step</text></g><polyline points="${points(false)}" class="chart-primary" fill="none" stroke-width="2.6"/><polyline points="${points(true)}" class="chart-secondary" fill="none" stroke-width="2" stroke-dasharray="${compare ? '0' : '5 4'}"/><circle cx="${x(28)}" cy="${y(28, false)}" r="4" class="chart-end"/></svg>`;
}

export function legend(compare = false) {
  return `<div class="chart-legend"><span><i class="primary-line"></i>${compare ? 'LoRA 04' : '训练集'}</span><span><i class="secondary-line"></i>${compare ? 'LoRA 03' : '验证集'}</span></div>`;
}

export function meter(value, label = '') {
  return `<div class="meter"><i style="width:${Math.min(100, Math.max(0, value))}%"></i></div>${label ? `<span class="meter-caption">${label}</span>` : ''}`;
}
