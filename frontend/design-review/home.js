import { summarize, selectRuns } from './data.js';
import { heading, summaryStrip, runTable, runFilters, status, button, icon, chart, legend, sparkline, escapeHtml as e } from './ui.js';

function exceptionNotice(data) {
  const failed = data.runs.find(x => x.status === '失败');
  return failed ? `<div class="attention-row"><span class="attention-mark">!</span><div><strong>${e(failed.name)}</strong><span>标签字段缺失，检查数据版本后可重新提交</span></div><button data-action="open-run" data-run="${failed.id}">查看任务 ${icon('chevron', 14)}</button></div>` : '';
}

function activeRun(data, scheme) {
  const run = data.runs.find(x => x.status === '运行中') || data.runs[0];
  return `<div class="active-run"><div class="section-label">当前训练</div><a href="#/${scheme}/run" class="active-run-name" data-run="${run.id}">${e(run.name)}</a><div class="run-identity">${run.model}<span>LoRA r=${run.rank}</span>${status(run.status)}</div><div class="active-run-stats"><div><span>${run.metric}</span><strong>${run.score}</strong></div><div><span>Epoch</span><strong>${run.epoch}</strong></div></div><div class="progress-track"><i style="width:${run.progress}%"></i></div><div class="progress-caption"><span>${run.progress}%</span><span>${run.duration}</span></div><div class="definition-row"><span>数据版本</span><strong>${run.dataset}</strong></div><div class="definition-row"><span>计算资源</span><strong>${run.gpu}</strong></div><a class="text-link" href="#/${scheme}/run" data-run="${run.id}">打开训练详情 ${icon('arrow', 14)}</a></div>`;
}

function datasetPreview(item) {
  if (item.id === 'image') return `<div class="image-sample"><svg viewBox="0 0 320 120" aria-label="目标检测示例"><rect width="320" height="120" fill="#e4eced"/><path d="M0 91h320M230 26h90M256 26v65M40 22v69" stroke="#b5c5c7" stroke-width="3"/><path d="M95 70v42m-22 0V82q0-17 22-17t22 17v30" fill="#a7bfc0"/><circle cx="95" cy="44" r="16" fill="#bdcdd0"/><path d="M76 42q0-24 19-24t19 24Z" fill="#cba45a"/><rect x="65" y="14" width="61" height="101" rx="2" fill="none" stroke="#477c79" stroke-width="2"/><text x="137" y="39" fill="#456160" font-size="12">helmet</text><path d="M136 44h-10" stroke="#477c79"/></svg></div>`;
  if (item.id === 'table') return `<div class="table-sample"><span>访问次数</span><span>最近活跃</span><span>流失</span><b>24</b><b>3</b><b>0</b><b>2</b><b>45</b><b>1</b><b>18</b><b>7</b><b>0</b></div>`;
  return `<div class="text-sample"><p>快递到了哪里？<span>物流查询</span></p><p>这个商品可以退换吗？<span>售后咨询</span></p></div>`;
}

function assetShelf(data) {
  return `<div class="asset-shelf">${data.datasets.map(item => `<button class="asset-preview" data-action="asset" data-asset="${item.id}">${datasetPreview(item)}<div class="asset-caption"><strong>${item.name}</strong><span>${item.count} <b>${item.format}</b></span></div><span class="asset-version">${item.version}</span></button>`).join('')}</div>`;
}

function deviceMatrix(data) {
  return `<div class="device-matrix">${data.nodes.filter(n => n.id.startsWith('GPU')).map(node => `<button class="device-tile ${node.status === '离线' ? 'offline' : ''}" data-action="node" data-node="${node.id}"><span>${node.id}</span><strong>${node.model}</strong><div class="device-load"><i style="height:${Math.max(node.util, 5)}%"></i><b>${node.status === '离线' ? '—' : `${node.util}%`}</b></div>${status(node.status)}<small>${node.memory} / ${node.total} GB</small></button>`).join('')}</div>`;
}

export function renderHome(state, data) {
  const sums = summarize(data);
  const runs = selectRuns(data.runs, state.filter, state.query);
  const title = heading('工作台', button('新建训练', 'new-run', true, 'plus'));
  const table = `<section class="run-section"><div class="section-heading"><h2>训练任务</h2><span>${runs.length} 项</span></div>${runFilters(state)}<div id="run-results">${runTable(runs, state.scheme, state.scheme === 'c')}</div></section>`;
  if (state.scheme === 'a') {
    return `${title}${summaryStrip([['运行中', sums.running], ['排队中', sums.queued], ['已完成', sums.completed], ['可用 GPU', sums.idle, ` / ${sums.gpu}`]])}<div class="workspace-columns"><div class="workspace-primary">${table}${exceptionNotice(data)}</div><aside class="workspace-secondary">${activeRun(data, state.scheme)}<section class="activity-section"><h2>近期活动</h2><div class="activity-event"><i></i><div><strong>客服意图语料已更新至 v3</strong><span>14:28</span></div></div><div class="activity-event"><i></i><div><strong>LoRA 03 训练完成</strong><span>13:42</span></div></div><div class="activity-event"><i></i><div><strong>GPU 03 已释放</strong><span>13:42</span></div></div></section></aside></div>`;
  }
  if (state.scheme === 'b') {
    return `${title}<div class="experiment-layout"><section class="experiment-main"><div class="experiment-header"><div><span class="section-label">客服意图识别</span><h2>实验对照</h2></div><div class="metric-toggle"><button data-action="metric" data-metric="loss" class="${state.metric === 'loss' ? 'selected' : ''}">Loss</button><button data-action="metric" data-metric="f1" class="${state.metric === 'f1' ? 'selected' : ''}">F1</button></div></div><div class="experiment-chart">${chart(state.metric, true)}${legend(true)}</div><div class="experiment-summary"><div><span>当前 F1</span><strong>0.914</strong></div><div><span>参考实验 F1</span><strong>0.902</strong></div><div><span>对比训练</span><strong>2<small> 次</small></strong></div></div></section><aside class="experiment-side">${activeRun(data, state.scheme)}</aside></div><div class="experiment-lower"><section class="experiment-comparison"><div class="section-heading"><h2>同项目训练</h2><a href="#/b/run">查看详情 ${icon('arrow', 14)}</a></div><div class="table-scroll"><table class="data-table"><thead><tr><th>实验</th><th>学习率</th><th>Rank</th><th>F1</th><th>状态</th></tr></thead><tbody>${data.runs.filter(r => r.project === '客服意图识别').slice(0, 3).map(r => `<tr><td><a href="#/b/run" data-run="${r.id}">${r.name}</a></td><td class="number">${r.lr}</td><td>${r.rank}</td><td><strong>${r.score}</strong></td><td>${status(r.status)}</td></tr>`).join('')}</tbody></table></div></section><section class="allocation-panel"><h2>运行中的实验</h2>${data.runs.filter(r => r.status === '运行中').map((r, i) => `<a href="#/b/run" data-run="${r.id}"><div><strong>${r.name}</strong><span>${r.gpu} <b>${r.progress}%</b></span></div>${sparkline(i)}</a>`).join('')}</section></div>${exceptionNotice(data)}`;
  }
  if (state.scheme === 'c') {
    return `${title}<div class="control-summary">${summaryStrip([['在线节点', sums.online, ` / ${data.nodes.length}`], ['运行任务', sums.running], ['等待调度', sums.queued], ['异常任务', sums.failed]])}<span class="sync-label">${icon('clock', 14)}14:32:18</span></div><section class="compute-board"><div class="section-heading"><h2>GPU 状态</h2><a href="#/c/resources">资源管理 ${icon('arrow', 14)}</a></div>${deviceMatrix(data)}</section><div class="queue-layout"><div>${table}</div><aside class="queue-side"><h2>等待队列</h2>${data.runs.filter(r => r.status === '排队中').map(r => `<div class="queue-item"><span class="queue-position">1</span><div><strong>${r.name}</strong><span>单 GPU · 8 GB</span><small>等待可用设备</small></div></div>`).join('')}<div class="queue-quota"><span>研发组并发配额</span><strong>2 / 4</strong><div class="progress-track"><i style="width:50%"></i></div></div><h2>节点事件</h2><div class="node-event">${status('离线')}<strong>开发节点 04</strong><span>最近心跳：14:25</span></div></aside></div>${exceptionNotice(data)}`;
  }
  return `${title}<div class="studio-focus"><section class="studio-project"><div class="project-topline"><span class="project-icon">${icon('training', 25)}</span><span class="project-type">文本分类</span>${status('运行中')}</div><h2>客服意图识别</h2><div class="project-model">Qwen3-0.6B <span>LoRA 微调</span></div><div class="project-bottom"><div><span>当前 F1</span><strong>0.914</strong></div><div><span>训练进度</span><strong>68<small>%</small></strong></div><a class="button primary" href="#/d/run">继续查看 ${icon('arrow', 16)}</a></div></section><section class="studio-side"><div class="section-heading"><h2>我的项目</h2><span>3 个</span></div><a href="#/d/run" data-run="TRN-1047"><span class="project-small-icon">${icon('model', 21)}</span><div><strong>安全帽检测</strong><span>YOLOv8n · 运行中</span></div>${sparkline(1)}</a><a href="#/d/run" data-run="TRN-1044"><span class="project-small-icon">${icon('data', 21)}</span><div><strong>商品图像分类</strong><span>ResNet18 · 已完成</span></div>${sparkline(2, true)}</a><a href="#/d/resources"><span class="project-small-icon">${icon('service', 21)}</span><div><strong>计算资源</strong><span>${sums.idle} 张 GPU 空闲</span></div>${icon('chevron', 16)}</a></section></div><div class="section-heading asset-title"><h2>数据资产</h2><button class="text-button" data-action="scope" data-scope="导入数据集">导入数据集 ${icon('plus', 14)}</button></div>${assetShelf(data)}${table}`;
}

export { datasetPreview };
