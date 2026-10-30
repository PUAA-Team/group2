export function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, character => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[character]);
}

const paths = {
  home: '<path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1z"/>',
  data: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9h18M8 9v11"/>',
  training: '<path d="M4 19V5m0 14h16M7 15l4-4 3 2 5-6"/>',
  models: '<path d="m12 2 8.7 5v10L12 22l-8.7-5V7zM3.3 7 12 12l8.7-5M12 12v10"/>',
  service: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M7 9h10M7 13h6M7 17h4"/>',
  resources: '<rect x="3" y="7" width="18" height="10" rx="2"/><path d="M7 4v3m5-3v3m5-3v3M7 17v3m5-3v3m5-3v3M8 12h8"/>',
  users: '<circle cx="9" cy="8" r="3"/><path d="M3 20v-2a6 6 0 0 1 12 0v2M17 11a3 3 0 1 0-1-6M21 20v-2a5 5 0 0 0-4-4.9"/>',
  audit: '<path d="M8 3h8l4 4v14H4V3zM16 3v5h4M8 12h8M8 16h8"/>',
  eye: '<path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
  panel: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 9v12"/>',
  layers: '<path d="m12 2 9 5-9 5-9-5 9-5zM3 12l9 5 9-5M3 17l9 5 9-5"/>',
  key: '<circle cx="8" cy="15" r="4"/><path d="m11 12 9-9 2 2-3 3 1 2-2 2-2-1-2 2"/>',
  settings: '<circle cx="12" cy="12" r="3"/><path d="M12 2v3m0 14v3M2 12h3m14 0h3M4.9 4.9 7 7m10 10 2.1 2.1M19.1 4.9 17 7M7 17l-2.1 2.1"/>',
  menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
  close: '<path d="M5 5l14 14M19 5 5 19"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  chevron: '<path d="m9 18 6-6-6-6"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m16 16 5 5"/>',
  download: '<path d="M12 3v12m-4-4 4 4 4-4M4 17v4h16v-4"/>',
  check: '<path d="m4 12 5 5L20 6"/>',
  arrow: '<path d="M5 12h14m-6-6 6 6-6 6"/>'
};
export const icon = (name, size = 18) => `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] || paths.chevron}</svg>`;

export function badge(label) {
  const tones = { "连接成功": "success", "连接失败": "danger", "未测试": "muted", "准备中": "info", "停止中": "warning", "正常": "success", "已完成": "success", "已保存": "success", "已登记": "success", "可训练": "success", "待标注": "warning", "运行中": "info", "排队中": "warning", "待处理": "warning", "待探测": "warning", "已接入": "success", "失败": "danger", "维护中": "warning", "空闲": "success", "使用中": "info", "启用": "success", "停用": "muted" };
  const tone = tones[label] || ({ "在线": "success", "等待连接": "warning", "待审核": "warning", "失联占用": "warning", "正在启动": "info", "已通过": "success", "已发布": "success", "进行中": "info", "待发布": "warning", "已退回": "danger" })[label] || "muted";
  const marks = { success: '<path d="m7.5 12 3 3 6-6"/>', info: '<path d="m10 8 6 4-6 4z" fill="currentColor" stroke="none"/>', warning: '<path d="M12 7v5l3 2"/>', danger: '<path d="m9 9 6 6m0-6-6 6"/>', muted: '<path d="M8 12h8"/>' };
  const mark = label === "已停止" ? '<rect x="9" y="9" width="6" height="6" fill="currentColor" stroke="none"/>' : label === "已取消" ? '<path d="m8.5 8.5 7 7"/>' : marks[tone];
  return `<span class="badge badge-${tone}" data-status="${escapeHtml(label)}" role="img" aria-label="${escapeHtml(label)}" tabindex="0"><svg class="status-symbol" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/>${mark}</svg><span class="status-label" aria-hidden="true">${escapeHtml(label)}</span></span>`;
}

export const linkButton = (label, href, kind = "secondary", symbol = "") => `<a class="btn btn-${kind} rounded-lg text-sm font-medium transition-colors" href="${href}">${symbol ? icon(symbol, 16) : ""}${escapeHtml(label)}</a>`;
export const card = (inner, extra = "") => `<section class="card ${extra}">${inner}</section>`;
export const pageHeader = (title, _subtitle = "", actions = "") => `<div class="page-heading"><h1>${escapeHtml(title)}</h1><div class="heading-actions">${actions}</div></div>`;

export const NAV_GROUPS = [
  { id: "overview", label: "概览", icon: "home", children: [["工作台", "/home"], ["用户空间", "/space"], ["资源监控", "/monitor"]] },
  { id: "data", label: "数据管理", icon: "data", children: [["数据集", "/datasets"], ["在线标注", "/annotation"], ["数据增强", "/augmentation"]] },
  { id: "training", label: "模型训练", icon: "training", children: [["训练项目", "/projects"], ["训练任务", "/runs"]] },
  { id: "models", label: "模型管理", icon: "models", children: [["模型仓库", "/models"], ["模型评估", "/evaluation"]] },
  { id: "services", label: "部署服务", icon: "service", children: [["在线服务", "/services"], ["API KEY管理", "/api-keys"]] }
];
export const ADMIN_NAV = [
  ["统计面板", "/admin/stats", "panel"], ["资源管理", "/admin/resources", "resources"],
  ["数据管理", "/admin/data", "data"], ["模型管理", "/admin/models", "models"],
  ["作业管理", "/admin/jobs", "training"], ["用户管理", "/admin/users", "users"],
  ["操作记录", "/admin/audit", "audit"], ["系统设置", "/admin/settings", "settings"]
];

const navPermission = { "/monitor": "resources.view", "/datasets": "datasets.read", "/annotation": "datasets.write", "/augmentation": "datasets.write", "/projects": "train.submit", "/runs": "train.submit", "/models": "models.manage", "/evaluation": "models.manage", "/services": "services.deploy", "/api-keys": "keys.manage" };

export function shell(route, content, title = "模训平台", user, ui = {}, permissions) {
  const activePath = route === "/train/new" ? "/projects" : route;
  const groupItems = NAV_GROUPS.map(group => {
    const children = group.children.filter(([, href]) => !permissions || !navPermission[href] || permissions.has(navPermission[href]));
    if (!children.length) return "";
    const active = children.some(([, href]) => activePath === href || activePath.startsWith(`${href}/`));
    const open = ui.navOpen?.[group.id] ?? true;
    return `<div class="nav-section ${open ? "open" : ""}"><button type="button" class="nav-parent ${active ? "current" : ""}" data-action="toggle-nav" data-group="${group.id}" aria-expanded="${open}" aria-label="${group.label}" title="${group.label}">${icon(group.icon)}<span class="nav-label">${group.label}</span>${icon("chevron", 14)}</button><div class="nav-children">${children.map(([label, href]) => `<a class="nav-child ${activePath === href || activePath.startsWith(`${href}/`) ? "active" : ""}" href="#${href}" ${activePath === href ? 'aria-current="page"' : ""}>${escapeHtml(label)}</a>`).join("")}</div></div>`;
  }).join("");
  const adminItems = user?.role === "管理员" ? `<div class="nav-divider"><span>管理端</span></div>${ADMIN_NAV.map(([label, href, symbol]) => `<a class="nav-link ${activePath === href ? "active" : ""}" href="#${href}" ${activePath === href ? 'aria-current="page"' : ""} title="${label}">${icon(symbol)}<span class="nav-label">${label}</span></a>`).join("")}` : "";
  const initial = escapeHtml(user?.name?.slice(0, 1) || "用");
  const breadcrumb = content.trimStart().startsWith('<div class="breadcrumb">') ? "" : `<div class="console-crumb"><a href="#/home">研发空间</a><span>/</span><span>${escapeHtml(title)}</span></div>`;
  return `<div class="app-shell ${ui.sidebarCollapsed ? "sidebar-collapsed" : ""}" id="shell">
    <header class="topbar"><div class="topbar-left"><button class="icon-button mobile-menu" aria-label="打开菜单" data-action="open-menu">${icon("menu")}</button><a class="console-brand" href="#/home"><span class="brand-mark">${icon("models", 22)}</span><strong>${escapeHtml(ui.platformName || "模训平台")}</strong></a><span class="product-name">AI 开发控制台</span></div><div class="topbar-right">${ui.workspaceControl || ""}<span class="environment-badge">${escapeHtml(ui.environmentLabel || "前端演示")}</span><span class="topbar-user">${escapeHtml(user?.name || "用户")}</span><span class="avatar avatar-small">${initial}</span><button class="icon-button" title="退出登录" aria-label="退出登录" data-action="logout">${icon("arrow", 16)}</button></div></header>
    <div class="sidebar-overlay" data-action="close-menu"></div>
    <aside class="sidebar" aria-label="主导航"><div class="nav-product"><strong>模型开发</strong><button class="icon-button desktop-collapse" title="展开或收起侧栏" aria-label="展开或收起侧栏" aria-expanded="${!ui.sidebarCollapsed}" data-action="collapse-sidebar">${icon("menu", 17)}</button><button class="icon-button mobile-close" aria-label="关闭菜单" data-action="close-menu">${icon("close")}</button></div>
      <nav class="sidebar-nav">${groupItems}${adminItems}</nav><a class="sidebar-bottom" href="#/space" title="用户空间">${icon("users", 17)}<span class="nav-label">用户空间</span></a>
    </aside>
    <main class="main-area"><div class="content">${breadcrumb}<div class="page-surface">${content}</div></div></main>
  </div>`;
}

export function emptyState(title, _detail, action = "") {
  return `<div class="empty-state"><div class="empty-icon">${icon("data", 24)}</div><h3>${escapeHtml(title)}</h3>${action}</div>`;
}

export function lineChart(values, labels = [], color = "var(--blue)") {
  const width = 720, height = 210, left = 24, right = 16, top = 20, bottom = 32;
  const min = Math.min(...values), max = Math.max(...values), span = max - min || 1;
  const points = values.map((value, index) => {
    const x = left + index * (width - left - right) / (values.length - 1);
    const y = top + (max - value) * (height - top - bottom) / span;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  return `<div class="chart"><svg viewBox="0 0 ${width} ${height}" role="img" aria-label="指标变化折线图" preserveAspectRatio="none"><path d="M${left} ${top}H${width - right}M${left} ${(top + height - bottom) / 2}H${width - right}M${left} ${height - bottom}H${width - right}" class="chart-grid"/><polyline fill="none" stroke="${color}" stroke-width="2.5" points="${points}" stroke-linecap="round" stroke-linejoin="round"/></svg><div class="chart-labels"><span>${escapeHtml(labels[0] || "开始")}</span><span>${escapeHtml(labels[1] || "训练轮次")}</span><span>${escapeHtml(labels[2] || "当前")}</span></div></div>`;
}
