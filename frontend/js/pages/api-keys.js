import { badge, card, escapeHtml as e, pageHeader } from "../ui.js?v=console-4";

export function renderApiKeys(state, user, ui) {
  const keys = state.apiKeys.filter(item => item.ownerId === user.id);
  return `${pageHeader("API KEY管理", "", '<button class="btn btn-primary" data-action="open-modal" data-modal="api-key-new">创建密钥</button>')}
    ${ui.newKey ? `<div class="notice notice-warning key-once" role="status"><strong>仅此一次显示演示密钥</strong><div class="key-reveal"><code>${e(ui.newKey)}</code><button class="btn btn-secondary btn-small" data-action="copy-key">复制</button></div></div>` : ""}
    ${card(keys.length ? `<div class="table-scroll"><table class="table"><thead><tr><th>名称</th><th>标识</th><th>范围</th><th>创建</th><th>状态</th><th>操作</th></tr></thead><tbody>${keys.map(item => `<tr><td>${e(item.name)}</td><td class="mono">${e(item.preview)}</td><td>${item.scope === "inference" ? "在线推理" : "只读访问"}</td><td>${e(item.created)}</td><td>${badge(item.status)}</td><td>${item.status === "启用" ? `<button class="btn btn-danger btn-small" data-action="revoke-key" data-key-id="${e(item.id)}">停用</button>` : "—"}</td></tr>`).join("")}</tbody></table></div>` : `<span class="subtle">暂无密钥</span>`)}`;
}
