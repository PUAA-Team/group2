// 提示层挂在页面根部，避免被表格横向滚动容器裁切。
export function installStatusTooltip() {
  let active = null;
  const tip = document.createElement("div");
  tip.id = "status-tooltip";
  tip.className = "status-tooltip";
  tip.role = "tooltip";
  tip.hidden = true;
  document.body.append(tip);
  function hide() {
    active?.removeAttribute("aria-describedby");
    active = null;
    tip.hidden = true;
  }
  function show(target) {
    const badge = target.closest?.("[data-status]");
    const label = badge?.querySelector(".status-label");
    if (!label || getComputedStyle(label).display !== "none") return;
    hide();
    active = badge;
    tip.textContent = badge.dataset.status;
    tip.hidden = false;
    badge.setAttribute("aria-describedby", tip.id);
    const rect = badge.getBoundingClientRect();
    const left = Math.max(8, Math.min(rect.left + rect.width / 2 - tip.offsetWidth / 2, innerWidth - tip.offsetWidth - 8));
    const top = rect.top > tip.offsetHeight + 10 ? rect.top - tip.offsetHeight - 6 : rect.bottom + 6;
    tip.style.left = `${left}px`;
    tip.style.top = `${top}px`;
  }
  document.addEventListener("pointerover", event => show(event.target));
  document.addEventListener("focusin", event => show(event.target));
  document.addEventListener("pointerout", event => {
    if (active?.contains(event.relatedTarget) || tip.contains(event.relatedTarget)) return;
    if (document.activeElement !== active) hide();
  });
  tip.addEventListener("pointerleave", () => { if (document.activeElement !== active) hide(); });
  document.addEventListener("focusout", event => { if (event.target === active) hide(); });
  document.addEventListener("keydown", event => { if (event.key === "Escape") hide(); });
  document.addEventListener("scroll", hide, true);
  window.addEventListener("resize", hide);
  return hide;
}
