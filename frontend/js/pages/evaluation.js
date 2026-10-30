import { modelById, taskById } from "../data.js?v=console-4";
import { badge, card, escapeHtml as e, lineChart, pageHeader } from "../ui.js?v=console-4";

export function renderEvaluation(state, ui) {
  const runs = state.runs.filter(item => item.status === "已完成");
  const selected = ui.evaluationRun || runs[0]?.id;
  const run = runs.find(item => item.id === selected) || runs[0];
  const comparable = runs.filter(item => item.taskId === run?.taskId);
  const comparison = comparable.map(item => `<tr><td><a class="row-link" href="#/runs/${e(item.id)}">${e(item.name)}</a></td><td>${e(modelById(item.modelId)?.name || "—")}</td><td>${e(item.metric)}</td><td><strong>${e(item.score)}</strong></td><td>${e(item.duration)}</td><td>${badge(item.status)}</td></tr>`).join("");
  return `${pageHeader("模型评估", "按任务查看训练结果与版本对比")}
    <div class="toolbar"><div class="toolbar-left"><label class="field"><span>选择训练结果</span><select class="select" data-filter="evaluationRun">${runs.map(item => `<option value="${e(item.id)}" ${item.id === selected ? "selected" : ""}>${e(item.name)}</option>`).join("")}</select></label></div></div>
    ${run ? `<div class="grid-3">${card(`<div class="metric-label">任务类型</div><div class="metric-value compact">${e(taskById(run.taskId)?.name || "—")}</div>`, "metric-card")}${card(`<div class="metric-label">${e(run.metric)}</div><div class="metric-value green">${e(run.score)}</div>`, "metric-card")}${card(`<div class="metric-label">训练模型</div><div class="metric-value compact">${e(modelById(run.modelId)?.name || "—")}</div>`, "metric-card")}</div><div class="section-heading"><h2>指标趋势</h2></div>${card(`${lineChart([.38,.46,.52,.59,.65,.73,.77,.82,Number(run.score) || .85],["开始","训练轮次","当前"],"#16805d")}`)}<div class="section-heading"><h2>同类任务对比</h2></div>${card(`<div class="table-scroll"><table class="table"><thead><tr><th>训练任务</th><th>模型</th><th>指标</th><th>结果</th><th>耗时</th><th>状态</th></tr></thead><tbody>${comparison}</tbody></table></div>`)}` : card(`<div class="empty-state"><h3>暂无已完成的训练</h3></div>`)}`;
}
