import { NAV_GROUPS } from "../js/ui.js?v=console-4";
const KEY = "model-platform-live-preferences";
export function loadPreferences(storage) {
  let saved = {};
  try { saved = JSON.parse(storage.getItem(KEY)) || {}; } catch { /* 偏好损坏时恢复默认值。 */ }
  return { navOpen: Object.fromEntries(NAV_GROUPS.map(group => [group.id, saved.navOpen?.[group.id] !== false])),
    sidebarCollapsed: saved.sidebarCollapsed === true, sidebarScroll: Math.max(0, Number(saved.sidebarScroll) || 0),
    workspaceId: typeof saved.workspaceId === "string" ? saved.workspaceId : "" };
}
export function savePreferences(storage, ui) {
  const value = { navOpen: ui.navOpen, sidebarCollapsed: !!ui.sidebarCollapsed, sidebarScroll: ui.sidebarScroll, workspaceId: ui.workspaceId };
  try { storage.setItem(KEY, JSON.stringify(value)); } catch { /* 不可写的浏览器存储不影响业务操作。 */ }
}
