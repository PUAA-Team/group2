import { heading, status, button, icon, chart, legend, escapeHtml as e } from './ui.js';

const logEntries = [
  ['14:14:02', '节点 GPU 01 已分配，准备运行环境'],
  ['14:14:08', '读取客服意图语料 v3，训练集 6,880 条，验证集 1,720 条'],
  ['14:14:12', 'Qwen3-0.6B 已加载，LoRA rank=8，batch_size=4'],
  ['14:18:24', 'epoch=1  step=200  loss=0.8421  eval_f1=0.8610'],
  ['14:23:16', 'epoch=2  step=400  loss=0.5143  eval_f1=0.8924'],
  ['14:28:40', 'epoch=3  step=600  loss=0.3827  eval_f1=0.9062'],
  ['14:32:18', 'epoch=3  step=680  loss=0.3418  eval_f1=0.9140'],
];

export function parameterList(run) {
  const params = [['任务类型', run.task], ['模型', run.model], ['数据版本', run.dataset], ['训练方式', run.rank ? 'LoRA' : '全参数'], ['学习率', run.lr], ['批大小', run.batch], ...(run.rank ? [['LoRA Rank', run.rank], ['最大序列长度', 512]] : [['训练轮次', run.epoch.split('/')[1].trim()]]), ['计算节点', run.gpu]];
  return `<dl class="parameter-list">${params.map(([name, value]) => `<div><dt>${name}</dt><dd>${e(value)}</dd></div>`).join('')}</dl>`;
}

function steps(run) {
  const names = ['准备数据', '加载模型', '执行训练', '模型评估', '保存产物'];
  const completed = run.status === '已完成' ? 5 : ['运行中', '已停止'].includes(run.status) ? 2 : 0;
  return `<div class="execution-steps">${names.map((name, index) => `<div class="execution-step ${index < completed ? 'done' : index === completed && !['排队中', '已取消', '失败'].includes(run.status) ? 'current' : ''}"><span>${index < completed ? icon('check', 12) : index + 1}</span><strong>${name}</strong>${index === 2 ? `<small>${run.progress}%</small>` : ''}</div>`).join('')}</div>`;
}

function logs(run) {
  const entries = run.id === 'TRN-1048' ? logEntries : [['14:14:02', `${run.name} 已登记`], ['14:14:08', `模型 ${run.model}，数据 ${run.dataset}`], ['14:32:18', `当前状态：${run.status}，进度 ${run.progress}%`]];
  if (run.status === '失败') entries.push(['14:32:19', '数据校验失败：label 字段缺失']);
  return `<div class="log-toolbar"><span>执行日志</span><button class="text-button" data-action="download-log" data-run="${run.id}">导出日志 ${icon('arrow', 14)}</button></div><pre class="log-content">${entries.map(([time, message]) => `<span>${time}</span>  ${e(message)}`).join('\n')}</pre>`;
}

function metricBlock(run) {
  return `<div class="run-metrics"><div><span>${run.metric}</span><strong>${run.score}</strong><small>当前验证指标</small></div><div><span>Loss</span><strong>${run.status === '排队中' || run.status === '失败' ? '—' : '0.342'}</strong><small>训练集</small></div><div><span>训练进度</span><strong>${run.progress}<small>%</small></strong><small>Epoch ${run.epoch}</small></div><div><span>显存占用</span><strong>${run.memory}<small> GB</small></strong><small>${run.gpu}</small></div></div>`;
}

function plot(state, run) {
  const available = ['运行中', '已完成', '已停止'].includes(run.status);
  const label = run.metric === '宏平均 F1' ? 'F1' : run.metric;
  return `<section class="chart-panel"><div class="chart-title"><h2>${state.metric === 'loss' ? '训练损失' : `验证 ${label}`}</h2><div class="metric-toggle"><button data-action="metric" data-metric="loss" class="${state.metric === 'loss' ? 'selected' : ''}">Loss</button><button data-action="metric" data-metric="f1" class="${state.metric === 'f1' ? 'selected' : ''}">${label}</button></div></div>${available ? `${chart(state.metric, false, label, Number(run.score) || .914)}${legend()}` : '<div class="chart-empty">当前状态暂无可展示曲线</div>'}</section>`;
}

function provenance(run) {
  return `<div class="provenance"><span>${icon('data', 16)}${e(run.dataset)}</span>${icon('arrow', 13)}<span>${icon('training', 16)}${run.id}</span>${icon('arrow', 13)}<span class="pending">${icon('model', 16)}${run.status === '已完成' ? '模型已保存' : '等待模型产物'}</span></div>`;
}

export function renderRun(state, data) {
  const run = data.runs.find(r => r.id === state.runId) || data.runs[0];
  const actions = ['运行中', '排队中'].includes(run.status) ? `${button('复制配置', 'clone-run', false, 'plus')}${button(run.status === '排队中' ? '取消排队' : '停止训练', 'stop-run')}` : button('复制配置', 'clone-run', true, 'plus');
  const header = `${heading(run.name, actions)}<div class="detail-meta">${status(run.status)}<span class="mono">${run.id}</span><span>${run.model}</span><span>${run.duration}</span></div>`;
  const tabs = `<div class="detail-tabs" aria-label="训练详情页签">${[['metrics', '指标'], ['logs', '日志'], ['parameters', '配置'], ['artifacts', '产物']].map(([tab, name]) => `<button data-action="run-tab" data-tab="${tab}" class="${state.runTab === tab ? 'selected' : ''}" aria-pressed="${state.runTab === tab}">${name}</button>`).join('')}</div>`;
  let main;
  if (state.runTab === 'logs') main = `<section class="panel log-panel">${logs(run)}</section>`;
  else if (state.runTab === 'parameters') main = `<section class="panel config-panel"><h2>训练配置</h2>${parameterList(run)}<button class="button" data-action="clone-run">用此配置新建训练</button></section>`;
  else if (state.runTab === 'artifacts') main = `<section class="panel artifact-panel"><h2>模型产物</h2>${run.status === '已完成' ? `<div class="artifact-row">${icon('model', 26)}<div><strong>${e(run.model)} / ${run.id}</strong><span>模型与配置 · 演示产物</span></div><button class="button" data-action="artifact-info">查看产物</button></div>` : '<div class="chart-empty">训练完成后显示模型产物</div>'}</section>`;
  else if (state.scheme === 'c') main = `<div class="control-detail"><div>${steps(run)}${metricBlock(run)}${plot(state, run)}<section class="panel log-panel">${logs(run)}</section></div><aside class="execution-aside"><h2>运行配置</h2>${parameterList(run)}<div class="execution-node">${icon('service', 22)}<strong>${run.gpu}</strong><span>Worker / PyTorch</span></div></aside></div>`;
  else main = `<div class="detail-layout"><div class="detail-main">${metricBlock(run)}${plot(state, run)}${steps(run)}${state.scheme === 'b' ? `<section class="panel log-panel">${logs(run)}</section>` : provenance(run)}</div><aside class="configuration-aside"><div class="section-heading"><h2>运行配置</h2><button class="icon-button" aria-label="复制当前配置" data-action="clone-run">${icon('plus', 16)}</button></div>${parameterList(run)}<div class="resource-assignment"><span class="section-label">已分配资源</span><strong>${run.gpu}</strong><span>${run.id === 'TRN-1048' ? 'RTX 4060 · 8 GB' : '本地 GPU Worker'}</span><a href="#/${state.scheme}/resources">查看资源 ${icon('arrow', 14)}</a></div></aside></div>`;
  return `${header}${tabs}${main}`;
}

export function logText(run) {
  return logEntries.map(([time, message]) => `${time} ${message}`).join('\n') + `\n${run.id}：模拟日志，仅供界面审查\n`;
}
