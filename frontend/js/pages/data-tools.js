import { badge, card, escapeHtml as e, pageHeader } from "../ui.js?v=console-4";

export function renderAnnotation(state) {
  const datasets = state.datasets.filter(item => item.type === "图像" || item.type === "文本");
  const rows = state.annotations.map(item => {
    const dataset = state.datasets.find(dataset => dataset.id === item.datasetId);
    return `<tr><td>${e(dataset?.name || "—")}</td><td>${e(item.label)}</td><td>${e(item.count)}</td><td>${badge(item.status)}</td><td>${e(item.updated)}</td></tr>`;
  }).join("");
  return `${pageHeader("在线标注", "", `<button class="btn btn-primary" data-action="open-modal" data-modal="annotation-new" ${datasets.length ? "" : "disabled"}>新建标注批次</button>`)}${card(rows ? `<div class="table-scroll"><table class="table"><thead><tr><th>数据集</th><th>标签</th><th>数量</th><th>状态</th><th>更新</th></tr></thead><tbody>${rows}</tbody></table></div>` : `<span class="subtle">暂无标注批次</span>`)}`;
}

export function renderAugmentation(state, ui = {}) {
  const methods = [["flip", "水平翻转", "图像"], ["crop", "随机裁剪", "图像"], ["synonym", "同义词替换", "文本"], ["back-translation", "回译", "文本"], ["noise", "数值扰动", "表格"]];
  const rows = state.augmentations.map(item => `<tr><td>${e(state.datasets.find(dataset => dataset.id === item.datasetId)?.name || "—")}</td><td>${e(methods.find(([key]) => key === item.method)?.[1] || item.method)}</td><td>${e(item.multiplier)} 倍</td><td>${badge(item.status)}</td><td>${e(item.updated)}</td></tr>`).join("");
  return `${pageHeader("数据增强", "", `<button class="btn btn-primary" data-action="open-modal" data-modal="augmentation-new" ${state.datasets.length ? "" : "disabled"}>创建增强方案</button>`)}${card(rows ? `<div class="table-scroll"><table class="table"><thead><tr><th>源数据集</th><th>策略</th><th>目标倍数</th><th>状态</th><th>创建时间</th></tr></thead><tbody>${rows}</tbody></table></div>` : `<span class="subtle">暂无增强记录</span>`)}`;
}
