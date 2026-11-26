import { badge, date, e, fieldsInfo, link, options, pageHeader, pager, raw, table, tag, TASKS } from "./components.js?v=stage20a-2";

const METRICS = { accuracy: "准确率", macro_f1: "Macro F1", loss: "Loss", validation_loss: "验证 Loss", perplexity: "困惑度", samples: "样本数", response_tokens: "响应 Token" };
const PARAMETERS = { epochs: '训练轮次', batch_size: '批量大小', learning_rate: '学习率', validation_ratio: '验证比例', seed: '随机种子', max_length: '最大序列长度', lora_rank: 'LoRA 秩' };
const format = (key, value) => value == null ? "—" : key === "accuracy" ? `${(value * 100).toFixed(2)}%` : Number.isInteger(value) ? e(value) : e(Number(value).toFixed(4));
export const isResultPage = path => path === "/evaluation/compare" || /^\/evaluation\/errors\/[^/]+$/.test(path);

export async function loadResults(api, ctx, signal) {
  const base = `/workspaces/${ctx.workspace.id}`;
  if (ctx.path === "/evaluation/compare") {
    const query = new URLSearchParams();
    for (const id of ctx.params.getAll("ids")) query.append("ids", id);
    return (await api.request(`${base}/evaluation-comparison?${query}`, { signal })).data;
  }
  const id = ctx.path.split("/").at(-1);
  return (await api.request(`${base}/jobs/${encodeURIComponent(id)}/error-samples?page=${ctx.page}&page_size=20`, { signal })).data;
}

export function renderResults(ctx) {
  const data = ctx.data;
  if (ctx.path !== "/evaluation/compare") {
    const heading = pageHeader("错误样本", "", link("返回评估", `/runs/${data.job_id}`));
    if (!data.supported) return heading + '<div class="empty-state">此评估未报告样本级结果</div>';
    const samples = data.samples || [];
    return heading + fieldsInfo([["错误总数", e(data.error_sample_count)], ["已报告", e(data.reported_count)]]) +
      table(["样本", "实际", "预测", "内容"], samples.map(item => [item.index + 1, raw(tag(item.actual)), raw(tag(item.predicted)),
        data.task_type === "image_classification" ? raw(`<img class="data-thumbnail" src="/api/v1/workspaces/${e(ctx.workspace.id)}/dataset-versions/${e(data.version_id)}/images/${item.index}" alt="样本 ${item.index + 1}"/>`) : raw(`<div class="data-sample-text">${e(item.source?.text || "")}</div>`) ])) +
      pager({ page: ctx.page, page_size: 20, total: data.reported_count });
  }
  const items = data.items || [], metrics = Object.keys(METRICS).filter(key => items.some(item => key in item.metrics));
  const headers = ["指标", ...items.map(item => item.name)];
  return `<div class="breadcrumb">${link("模型评估", "/evaluation")} / 结果对比</div>` + pageHeader("评估对比") +
    fieldsInfo([["任务", tag(TASKS[data.task_type])], ["数据版本", link(`${data.dataset.name} / v${data.dataset.number}`, `/datasets/${data.dataset.id}`)]]) +
    table(headers, [["模型", ...items.map(item => raw(link(`${item.model_name} / ${item.model_version}`, `/models/${item.model_id}`)))],
      ...metrics.map(key => [METRICS[key], ...items.map(item => format(key, item.metrics[key]))]),
      ["评估时间", ...items.map(item => date(item.created_at))], ["样本分析", ...items.map(item => item.errors_available ? raw(link("错误样本", `/evaluation/errors/${item.id}`)) : "—")]]) +
    `<div class="section-heading"><h2>评估配置</h2></div>${fieldsInfo(Object.entries(data.config || {}).filter(([key, value]) => value != null && (data.task_type === 'llm_sft' || !['max_length', 'lora_rank'].includes(key))).map(([key, value]) => [PARAMETERS[key] || key, e(value)]))}` +
    items.filter(item => Array.isArray(item.confusion_matrix) && Array.isArray(item.labels)).map(item =>
      `<div class="section-heading"><h2>${e(item.name)}</h2>${tag("行：实际 / 列：预测")}</div>` +
      table(["类别", ...item.labels], item.confusion_matrix.map((row, index) => [item.labels[index], ...row]))).join("");
}

export function renderCallHistory(ctx) {
  const counts = ctx.data.callStatistics || {}, history = ctx.data.callHistory || { data: [] };
  const states = { pending: "排队中", succeeded: "已完成", failed: "失败" };
  const ms = value => value == null ? "—" : `${value} ms`;
  return `<div class="section-heading"><h2>调用记录</h2><select class="select" data-query-filter="call_status" aria-label="调用状态">${options([["", "全部状态"], ...Object.entries(states)], ctx.params?.get("call_status"))}</select></div>` +
    fieldsInfo([["总调用", e(counts.total ?? 0)], ["成功", e(counts.succeeded ?? 0)], ["失败", e(counts.failed ?? 0)], ["等待中", e(counts.pending ?? 0)],
      ["计时样本", e(counts.measured_calls ?? 0)], ["平均等待与响应", ms(counts.mean_ms)]]) +
    table(["请求", "调用人", "状态", "提交时间", "完成时间", "等待与响应"], history.data.map(item => [item.id, item.actor_name, raw(badge(states[item.status])), date(item.created_at), date(item.completed_at), ms(item.elapsed_ms)])) + pager(history.pagination);
}

export function renderEvaluationReport(ctx) {
  const report = ctx.data.evaluationSummary;
  if (!report) return '';
  const base = `/api/v1/workspaces/${encodeURIComponent(ctx.workspace.id)}/jobs/${encodeURIComponent(report.job_id)}/evaluation-report`;
  const download = `<div class="heading-actions"><a class="btn btn-secondary" href="${base}?format=json">下载 JSON</a><a class="btn btn-secondary" href="${base}?format=csv">下载 CSV</a></div>`;
  const score = value => value == null ? '—' : `${(value * 100).toFixed(2)}%`;
  return `<div class="section-heading"><h2>评估报告</h2>${download}</div>` + (report.per_class ? table(['类别', '精确率', '召回率', 'F1', '样本数'], report.per_class.map(item =>
    [raw(tag(item.label)), score(item.precision), score(item.recall), score(item.f1), item.support])) : '');
}
