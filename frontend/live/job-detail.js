import { badge, btn, can, card, date, e, fieldsInfo, pageHeader, table, tag, TASKS } from "./components.js?v=stage13-3a";

const statusNames = { draft: "草稿", queued: "排队中", preparing: "准备中", running: "运行中", stopping: "停止中", stopped: "已停止", cancelled: "已取消", succeeded: "已完成", failed: "失败" };
const parameterNames = { epochs: "Epochs", batch_size: "Batch size", learning_rate: "Learning rate", validation_ratio: "验证比例", seed: "Seed", max_length: "最大长度", lora_rank: "LoRA rank" };
const tabs = [["overview", "概况"], ["metrics", "指标"], ["logs", "日志"], ["outputs", "产物"]];

export function renderTrainingDetail(ctx, metricChart) {
  const job = ctx.data.item, result = job.result || {}, config = job.config || {}, events = ctx.data.events || [];
  const tab = ctx.params?.get("tab") || "overview", write = can(ctx, "training.write");
  const final = ["succeeded", "failed", "stopped", "cancelled"].includes(job.status), llm = job.snapshot?.task_type === "llm_sft" || job.task_type === "llm_sft";
  const model = ctx.data.options?.models.find(item => item.id === job.model_version_id);
  const dataset = ctx.data.options?.datasets.find(item => item.id === job.dataset_version_id);
  const actions = (write ? `<a class="btn btn-secondary" href="#/train/new?copy=${e(job.id)}">复制配置</a>` : "") +
    (write && job.status === "draft" ? btn("编辑草稿", "workflow-edit", job.id) + btn("提交", "workflow-submit", job.id, "primary") : "") +
    (write && !final && job.status !== "draft" ? btn(job.status === "queued" ? "取消任务" : "停止", "workflow-stop", job.id, "secondary", job.status === "stopping") : "") +
    (write && final ? btn("重跑", "workflow-retry", job.id) : "");
  const outcomes = [["准确率", result.accuracy == null ? "—" : `${(result.accuracy * 100).toFixed(1)}%`], ["Macro F1", result.macro_f1 == null ? "—" : result.macro_f1.toFixed(3)], ["Loss", result.validation_loss == null && result.loss == null ? "—" : Number(result.validation_loss ?? result.loss).toFixed(4)]];
  let panel;
  if (tab === "metrics") panel = `<div class="execution-charts ${llm ? "execution-single-chart" : ""}">${metricChart(events, ["loss", "val_loss"], "训练损失")}${llm ? "" : metricChart(events, ["accuracy", "val_accuracy"], "准确率")}</div>` +
    (events.some(event => event.type === "metric") ? table(["Epoch", "Loss", "验证 Loss", ...(llm ? [] : ["准确率", "验证准确率"])], events.filter(event => event.type === "metric").map(({ payload: row }) => [e(row.epoch), ...["loss", "val_loss", ...(llm ? [] : ["accuracy", "val_accuracy"])].map(key => row[key] == null ? "—" : e(Number(row[key]).toFixed(4)))])) : "");
  else if (tab === "logs") {
    const search = ctx.params?.get("log_q") || "";
    const logs = events.filter(event => event.type === "log").map(event => event.payload.message || "").filter(message => !search || message.toLowerCase().includes(search.toLowerCase()));
    panel = `<div class="toolbar"><form class="toolbar-left" data-form="logs-search"><input class="input" type="search" name="log_q" aria-label="搜索日志" placeholder="搜索日志" value="${e(search)}"/><button class="btn btn-secondary" type="submit">搜索</button></form><div class="heading-actions"><a class="btn btn-secondary" href="/api/v1/workspaces/${e(ctx.workspace.id)}/jobs/${e(job.id)}/logs">下载完整日志</a>${btn("刷新", "refresh")}</div></div><pre class="execution-log console-log">${e(logs.join("\n") || "暂无匹配日志")}</pre>`;
  } else if (tab === "outputs") {
    const controls = (job.artifact_sha256 ? `<a class="btn btn-secondary" href="/api/v1/workspaces/${e(ctx.workspace.id)}/jobs/${e(job.id)}/artifact">下载产物</a>` : "") +
      (job.output_model_version_id && write ? btn("创建评估", "workflow-evaluate", job.output_model_version_id) : "") +
      (job.output_model_version_id && can(ctx, "services.write") ? btn("部署服务", "workflow-deploy", job.output_model_version_id, "primary") : "");
    panel = job.status === "succeeded" ? card(`<div class="card-header"><h2>模型产物</h2><div class="heading-actions">${controls}</div></div>${fieldsInfo([["模型版本", e(job.output_model_version_id || "—")], ["文件大小", job.artifact_bytes == null ? "—" : `${(job.artifact_bytes / 1024).toFixed(1)} KiB`], ["SHA256", `<span class="live-break">${e(job.artifact_sha256 || "—")}</span>`]])}`) : '<div class="empty-state"><h3>暂无模型产物</h3></div>';
  } else panel = `<div class="console-detail-grid">${card(`<div class="card-header"><h2>执行信息</h2><span class="heading-actions">${badge(statusNames[job.status] || job.status)}${e(statusNames[job.status] || job.status)}</span></div>${fieldsInfo([["模型", e(model ? `${model.name} / ${model.version}` : job.model_name || job.model_version_id)], ["数据集", e(dataset ? `${dataset.name} / v${dataset.number}` : job.dataset_name || job.dataset_version_id || "—")], ["任务类型", tag(TASKS[job.task_type || job.snapshot?.task_type] || "待提交")], ["执行设备", tag(job.device_kind === "cuda" ? "GPU" : "CPU")], ["创建时间", date(job.created_at)], ["结束时间", date(job.execution?.finished_at)]])}`)}${card(`<div class="card-header"><h2>训练参数</h2></div>${fieldsInfo(Object.entries(parameterNames).filter(([key]) => config[key] != null && (llm || !["max_length", "lora_rank"].includes(key))).map(([key, label]) => [label, e(config[key])]))}`)}</div>` +
    (job.status === "succeeded" ? `<div class="section-heading"><h2>执行结果</h2></div>${card(fieldsInfo([...outcomes.map(([key, value]) => [key, e(value)]), ...[["训练样本", result.training_samples], ["验证样本", result.validation_samples], ["响应 Token", result.response_tokens], ["困惑度", result.perplexity]].filter(([, value]) => value != null).map(([key, value]) => [key, e(value)])]))}` +
      (result.confusion_matrix ? `<div class="section-heading"><h2>混淆矩阵</h2>${tag("行：实际 / 列：预测")}</div>${table(["类别", ...result.labels], result.confusion_matrix.map((row, index) => [e(result.labels[index]), ...row.map(e)]))}` : "") : "");
  return `<div class="breadcrumb"><a href="#/runs">训练任务</a><span>/</span><span>${e(job.name)}</span></div>` + pageHeader(job.name, "", actions) +
    `<div class="tabs">${tabs.map(([key, label]) => `<a class="tab ${key === tab ? "active" : ""}" href="#/runs/${e(job.id)}?tab=${key}" ${key === tab ? 'aria-current="page"' : ""}>${label}</a>`).join("")}</div>` +
    (job.queue_reason ? `<div class="notice">${e(job.queue_reason)}</div>` : "") + (job.error ? `<div class="notice notice-danger" role="alert">${e(job.error)}</div>` : "") + panel;
}
