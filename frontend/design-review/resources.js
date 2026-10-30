import { summarize } from './data.js';
import { heading, summaryStrip, status, button, icon, meter, escapeHtml as e } from './ui.js';

function cards(data) {
  return `<div class="resource-cards">${data.nodes.map(node => `<button class="resource-card ${node.status === '离线' ? 'offline' : ''}" data-action="node" data-node="${node.id}"><div class="resource-top"><span class="hardware-icon">${icon('service', 22)}</span>${status(node.status)}</div><div class="resource-title"><strong>${node.id}</strong><span>${node.name}</span></div><h3>${node.model}</h3><div class="resource-usage"><span>设备利用率</span><strong>${node.status === '离线' ? '—' : `${node.util}%`}</strong></div>${meter(node.util)}<div class="resource-memory"><span>显存 / 内存</span><strong>${node.memory} / ${node.total} GB</strong></div><div class="resource-task">${node.task === '—' ? node.status === '离线' ? '等待节点恢复' : '可分配任务' : node.task}</div></button>`).join('')}</div>`;
}

function table(data, state) {
  return `<div class="table-scroll"><table class="data-table ${state.scheme === 'c' ? 'compact' : ''}"><thead><tr><th>设备 / 节点</th><th>型号</th><th>状态</th><th>利用率</th><th>显存 / 内存</th><th>当前任务</th><th></th></tr></thead><tbody>${data.nodes.map(node => `<tr><td><button class="run-name text-button" data-action="node" data-node="${node.id}">${node.id}</button><span class="row-meta">${node.name}</span></td><td>${node.model}</td><td>${status(node.status)}</td><td><div class="table-meter"><span class="number">${node.status === '离线' ? '—' : `${node.util}%`}</span>${meter(node.util)}</div></td><td class="nowrap"><strong>${node.memory}</strong> / ${node.total} GB</td><td>${node.task}</td><td><button class="icon-button" data-action="node" data-node="${node.id}" aria-label="查看${node.id}">${icon('chevron', 15)}</button></td></tr>`).join('')}</tbody></table></div>`;
}

function allocation(data) {
  return `<section class="allocation-map"><h2>任务分配</h2>${data.nodes.filter(n => n.status === '使用中').map(node => `<div class="allocation-row"><span>${icon('service', 18)}${node.id}</span><i></i><strong>${node.task}</strong><b>${node.memory} GB</b></div>`).join('')}<div class="allocation-row idle-allocation"><span>${icon('service', 18)}GPU 03</span><i></i><strong>等待分配</strong><b>8 GB</b></div></section>`;
}

export function renderResources(state, data) {
  const sums = summarize(data);
  const head = heading('资源管理', button('接入新节点', 'new-node', true, 'plus'));
  const tabs = `<div class="detail-tabs"><button data-action="resource-tab" data-tab="devices" class="${state.resourceTab === 'devices' ? 'selected' : ''}">设备</button><button data-action="resource-tab" data-tab="nodes" class="${state.resourceTab === 'nodes' ? 'selected' : ''}">节点</button><button data-action="resource-tab" data-tab="queue" class="${state.resourceTab === 'queue' ? 'selected' : ''}">队列</button></div>`;
  let body;
  if (state.resourceTab === 'queue') body = `<section class="panel queue-table"><div class="section-heading"><h2>等待中的任务</h2><span>按提交顺序</span></div><div class="table-scroll"><table class="data-table"><thead><tr><th>顺序</th><th>任务</th><th>设备要求</th><th>等待状态</th></tr></thead><tbody>${data.runs.filter(r => r.status === '排队中').map((run, i) => `<tr><td>${i + 1}</td><td>${run.name}</td><td>单 GPU / 8 GB / PyTorch</td><td>${status('排队中')}</td></tr>`).join('')}</tbody></table></div></section>`;
  else if (state.resourceTab === 'nodes') body = `<section class="panel"><div class="section-heading"><h2>计算节点</h2><span>${data.nodes.length} 个</span></div><div class="table-scroll"><table class="data-table"><thead><tr><th>节点</th><th>接入方式</th><th>设备</th><th>CPU 占用</th><th>状态</th></tr></thead><tbody>${data.nodes.map(node => `<tr><td><button class="text-button" data-action="node" data-node="${node.id}">${node.name}</button></td><td>${node.source}</td><td>${node.model}</td><td>${node.cpu}%</td><td>${status(node.status)}</td></tr>`).join('')}</tbody></table></div></section>`;
  else if (state.scheme === 'b') body = `${allocation(data)}<section class="panel resource-list"><div class="section-heading"><h2>计算设备</h2><span>${sums.idle} 张 GPU 空闲</span></div>${table(data, state)}</section>`;
  else if (state.scheme === 'c' || state.scheme === 'd') body = `${cards(data)}${state.scheme === 'c' ? '<div class="resource-policy"><span>调度策略</span><strong>设备与显存匹配</strong><span>优先级</span><strong>标准队列</strong><span>组并发配额</span><strong>2 / 4</strong><button class="text-button" data-action="quota">查看配额</button></div>' : ''}`;
  else body = `<section class="resource-list"><div class="section-heading"><h2>计算设备</h2><button class="text-button" data-action="quota">组配额 ${icon('chevron', 14)}</button></div>${table(data, state)}</section>`;
  return `${head}${summaryStrip([['GPU 设备', sums.gpu], ['在线节点', sums.online, ` / ${data.nodes.length}`], ['空闲 GPU', sums.idle], ['等待任务', sums.queued]])}${tabs}${body}`;
}

export function nodeModal(node) {
  return `<div class="node-detail-heading"><span class="hardware-icon">${icon('service', 26)}</span><div><h3>${e(node.model)}</h3><span>${node.name}</span></div>${status(node.status)}</div><dl class="parameter-list"><div><dt>接入方式</dt><dd>${node.source}</dd></div><div><dt>设备容量</dt><dd>${node.total} GB</dd></div><div><dt>温度</dt><dd>${node.temperature || '—'} °C</dd></div><div><dt>CPU 占用</dt><dd>${node.cpu}%</dd></div><div><dt>当前任务</dt><dd>${node.task}</dd></div></dl><div class="node-modal-meter"><span>设备利用率 <strong>${node.util}%</strong></span>${meter(node.util)}<span>显存 / 内存 <strong>${node.memory} / ${node.total} GB</strong></span>${meter(node.memory / node.total * 100)}</div>`;
}
