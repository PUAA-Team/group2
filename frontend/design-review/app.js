import { schemes, pages, createFixtures, parseRoute, selectRuns } from './data.js';
import { shell, icon, button, runTable, escapeHtml as e } from './ui.js';
import { renderHome, datasetPreview } from './home.js';
import { renderRun, logText } from './detail.js';
import { renderResources, nodeModal } from './resources.js';

const app = document.querySelector('#app');
const dialog = document.querySelector('#modal');
const storageKey = 'model-training-design-review-20261014';
const preferences = JSON.parse(localStorage.getItem(storageKey) || '{}');
const state = { ...parseRoute(location.hash), groups: preferences.groups || {}, collapsed: preferences.collapsed || false, mobileOpen: false, runId: 'TRN-1048', runTab: 'metrics', metric: 'loss', filter: '全部', query: '', resourceTab: 'devices', chosen: preferences.chosen || '' };
const data = createFixtures();
let menuScroll = 0;
let previousFocus;
let toastTimeout;

function savePreferences() {
  localStorage.setItem(storageKey, JSON.stringify({ groups: state.groups, collapsed: state.collapsed, chosen: state.chosen }));
}

function gallery() {
  return `<main class="gallery"><header class="gallery-header"><a class="gallery-brand" href="#/gallery">${icon('model', 25)}模训平台</a><a href="http://127.0.0.1:8765/#/home" class="button" target="_blank" rel="noopener">查看现有原型 ${icon('arrow', 15)}</a></header><div class="gallery-heading"><h1>选择你喜欢的界面</h1><p>四套方案，三个页面，统一演示数据。</p><span class="gallery-selection" role="status">${state.chosen ? `已选：${schemes.find(s => s.id === state.chosen).name}` : '尚未选择'}</span></div><div class="gallery-grid">${schemes.map(s => `<article class="gallery-card ${state.chosen === s.id ? 'chosen' : ''}"><a class="preview-image" href="#/${s.id}/home"><img src="./previews/${s.id}-home.jpg" alt="${s.name}工作台实拍截图" /><span class="preview-number">${s.code}</span></a><div class="gallery-card-copy"><div><h2>${s.name}</h2><p>${s.description}</p></div><button class="choose-button ${state.chosen === s.id ? 'selected' : ''}" data-action="choose" data-scheme="${s.id}">${state.chosen === s.id ? `${icon('check', 15)}已选择` : '选择此方案'}</button></div><div class="gallery-card-links">${pages.map(p => `<a href="#/${s.id}/${p.id}">${p.name}${icon('arrow', 12)}</a>`).join('')}</div></article>`).join('')}</div><footer class="gallery-footer"><span>界面样例 · 模拟数据</span><span>可分别选择导航、训练详情和资源页面的布局</span>${state.chosen ? '<button class="text-button" data-action="clear-choice">清除选择</button>' : ''}<button class="text-button" data-action="references">查看设计参考</button></footer></main>`;
}

function render() {
  state.runCount = data.runs.length;
  const oldMenu = app.querySelector('.sidebar-scroll');
  if (oldMenu) menuScroll = oldMenu.scrollTop;
  document.body.dataset.scheme = state.scheme;
  if (state.scheme === 'gallery') app.innerHTML = gallery();
  else {
    const body = state.page === 'run' ? renderRun(state, data) : state.page === 'resources' ? renderResources(state, data) : renderHome(state, data);
    app.innerHTML = shell(state, body);
    const menu = app.querySelector('.sidebar-scroll');
    if (menu) menu.scrollTop = menuScroll;
  }
  document.title = state.scheme === 'gallery' ? '模训平台 · 四套界面样例' : `${schemes.find(s => s.id === state.scheme).code} ${schemes.find(s => s.id === state.scheme).name} · ${pages.find(p => p.id === state.page).name}`;
}

function notify(message) {
  const toast = document.querySelector('#toast');
  toast.textContent = message;
  toast.classList.add('visible');
  clearTimeout(toastTimeout);
  toastTimeout = setTimeout(() => toast.classList.remove('visible'), 3200);
}

function openModal(title, body, footer = button('关闭', 'close-modal')) {
  previousFocus = document.activeElement;
  dialog.innerHTML = `<div class="modal-header"><h2 id="modal-title">${e(title)}</h2><button class="icon-button" data-action="close-modal" aria-label="关闭弹窗">${icon('close')}</button></div><div class="modal-body">${body}</div><div class="modal-footer">${footer}</div>`;
  dialog.showModal();
  dialog.querySelector('input, select, textarea, button')?.focus();
}

function currentRun() {
  return data.runs.find(run => run.id === state.runId) || data.runs[0];
}

function newRun(clone = false) {
  const run = currentRun();
  openModal(clone ? '复制训练配置' : '新建训练', `<form id="run-form"><label>任务名称<input name="name" required maxlength="60" value="${clone ? e(`${run.name} 副本`) : ''}" placeholder="例如：客服意图 · LoRA 06" /></label><div class="form-grid"><label>任务类型<select name="task"><option>文本分类</option><option>目标检测</option><option>图像分类</option><option>指令微调</option></select></label><label>模型<select name="model"><option>Qwen3-0.6B</option><option>YOLOv8n</option><option>ResNet18</option></select></label></div><label>数据版本<select name="dataset">${data.datasets.map(d => `<option>${d.name} ${d.version}</option>`).join('')}</select></label><div class="form-grid"><label>学习率<input name="lr" value="${clone ? run.lr : '2e-4'}" required /></label><label>LoRA Rank<select name="rank"><option>8</option><option>16</option><option>32</option></select></label></div><label>计算资源<select name="gpu"><option>自动分配 · GPU 队列</option><option>GPU 03 · RTX 4060</option><option>GPU 05 · RTX 4070 Laptop</option><option>CPU 队列</option></select></label><p class="modal-demo-note">创建记录仅用于界面演示，不提交真实训练。</p></form>`, `${button('取消', 'close-modal')}<button class="button primary" type="submit" form="run-form">创建演示任务</button>`);
  const form = dialog.querySelector('#run-form');
  const syncTask = () => {
    const task = form.elements.task.value;
    form.elements.model.value = task === '目标检测' ? 'YOLOv8n' : task === '图像分类' ? 'ResNet18' : 'Qwen3-0.6B';
    form.elements.dataset.selectedIndex = task === '目标检测' || task === '图像分类' ? 1 : 0;
    form.elements.rank.disabled = task === '目标检测' || task === '图像分类';
  };
  form.elements.task.addEventListener('change', syncTask);
  if (clone) { form.elements.task.value = run.task; syncTask(); if (run.rank) form.elements.rank.value = run.rank; }
}

function newNode() {
  openModal('接入新节点', `<form id="node-form"><label>节点名称<input name="name" required maxlength="40" placeholder="例如：实验室节点 01" /></label><div class="form-grid"><label>接入方式<select name="source"><option>本地 Worker</option><option>实验室 Worker</option><option>云端 Worker</option><option>Modal 适配器</option></select></label><label>模拟设备<select name="model"><option>RTX 4060</option><option>RTX 4070 Laptop</option><option>CPU · 16 核</option></select></label></div><div class="command-preview"><div><strong>接入命令示意</strong><button type="button" class="text-button" data-action="copy-command">复制</button></div><code>DEMO_ONLY://REGISTER &lt;平台地址&gt; &lt;一次性令牌&gt;</code></div><p class="modal-demo-note">示意文本不可执行。探测与接入结果使用模拟数据。</p></form>`, `${button('取消', 'close-modal')}<button class="button primary" type="submit" form="node-form">模拟探测并登记</button>`);
}

function download(name, content, type = 'text/plain;charset=utf-8') {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = name;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

document.addEventListener('click', async event => {
  const runLink = event.target.closest('[data-run]');
  if (runLink) { state.runId = runLink.dataset.run; state.runTab = 'metrics'; }
  const element = event.target.closest('[data-action]');
  if (!element) return;
  const action = element.dataset.action;
  if (['scope', 'open-run'].includes(action)) event.preventDefault();
  if (action === 'toggle-group') { state.groups[element.dataset.group] = state.groups[element.dataset.group] === false; savePreferences(); render(); }
  else if (action === 'collapse') { state.collapsed = !state.collapsed; savePreferences(); render(); }
  else if (action === 'mobile-menu') { state.mobileOpen = !state.mobileOpen; render(); }
  else if (action === 'scope') openModal(element.dataset.scope, '<div class="scope-message">本次提供工作台、训练详情和资源管理样例。请选择顶部页签审查。</div>');
  else if (action === 'filter') { state.filter = element.dataset.filter; render(); }
  else if (action === 'metric') { state.metric = element.dataset.metric; render(); }
  else if (action === 'run-tab') { state.runTab = element.dataset.tab; render(); }
  else if (action === 'resource-tab') { state.resourceTab = element.dataset.tab; render(); }
  else if (action === 'open-run') { location.hash = `#/${state.scheme}/run`; render(); }
  else if (action === 'new-run') newRun();
  else if (action === 'clone-run') newRun(true);
  else if (action === 'stop-run') openModal(currentRun().status === '排队中' ? '取消排队' : '停止训练', `<p>确认${currentRun().status === '排队中' ? '取消' : '停止'}“${e(currentRun().name)}”？仅更新本次演示记录。</p>`, `${button('返回', 'close-modal')}${button('确认', 'confirm-stop', true)}`);
  else if (action === 'confirm-stop') { currentRun().status = currentRun().status === '排队中' ? '已取消' : '已停止'; dialog.close(); render(); notify('演示任务状态已更新'); }
  else if (action === 'new-node') newNode();
  else if (action === 'node') { const node = data.nodes.find(n => n.id === element.dataset.node); openModal(node.id, nodeModal(node)); }
  else if (action === 'asset') { const asset = data.datasets.find(d => d.id === element.dataset.asset); openModal(asset.name, `${datasetPreview(asset)}<dl class="parameter-list"><div><dt>任务</dt><dd>${asset.task}</dd></div><div><dt>数量</dt><dd>${asset.count}</dd></div><div><dt>版本 / 格式</dt><dd>${asset.version} / ${asset.format}</dd></div></dl>`); }
  else if (action === 'quota') openModal('研发组资源配额', '<dl class="parameter-list"><div><dt>GPU 上限</dt><dd>2 张</dd></div><div><dt>并发任务上限</dt><dd>4 个</dd></div><div><dt>个人 GPU 上限</dt><dd>2 张</dd></div><div><dt>有效 GPU 上限</dt><dd>2 张</dd></div></dl>');
  else if (action === 'artifact-info') openModal('模型产物', '<p>此处展示训练产物的界面组织。样例未生成或存储模型权重。</p>');
  else if (action === 'download-log') download(`${currentRun().id}-demo.log`, logText(currentRun()));
  else if (action === 'copy-command') { await navigator.clipboard.writeText('DEMO_ONLY://REGISTER <平台地址> <一次性令牌>'); notify('已复制不可执行的命令示意'); }
  else if (action === 'close-modal') dialog.close();
  else if (action === 'choose') { state.chosen = element.dataset.scheme; savePreferences(); render(); }
  else if (action === 'clear-choice') { state.chosen = ''; savePreferences(); render(); }
  else if (action === 'references') openModal('设计参考', '<ul class="reference-links"><li><a href="https://linear.app/now/how-we-redesigned-the-linear-ui" target="_blank" rel="noopener">Linear 界面设计</a></li><li><a href="https://mlflow.org/docs/latest/ml/tracking/" target="_blank" rel="noopener">MLflow 实验追踪</a></li><li><a href="https://carbondesignsystem.com/components/data-table/usage/" target="_blank" rel="noopener">IBM Carbon 数据表</a></li><li><a href="https://grafana.com/docs/grafana/latest/fundamentals/dashboards-overview/" target="_blank" rel="noopener">Grafana 仪表盘</a></li><li><a href="https://fluent2.microsoft.design/components/web/react/core/nav/usage/" target="_blank" rel="noopener">Microsoft Fluent 导航</a></li><li><a href="https://huggingface.co/docs/hub/models-the-hub" target="_blank" rel="noopener">Hugging Face 模型资产</a></li></ul>');
});

dialog.addEventListener('submit', event => {
  event.preventDefault();
  const fields = new FormData(event.target);
  if (event.target.id === 'run-form') {
    const id = `TRN-${1050 + data.runs.filter(r => r.demoNew).length}`;
    const task = fields.get('task');
    data.runs.unshift({ id, name: fields.get('name').trim(), task, project: '新建演示项目', model: fields.get('model'), dataset: fields.get('dataset'), status: '排队中', progress: 0, epoch: '0 / 5', score: '—', metric: task === '目标检测' ? 'mAP' : task === '图像分类' ? '准确率' : '宏平均 F1', gpu: 'GPU 队列', duration: '刚刚提交', lr: fields.get('lr'), rank: Number(fields.get('rank')) || null, batch: 4, memory: 0, demoNew: true });
    dialog.close(); render(); notify(`演示任务 ${id} 已创建`);
  } else if (event.target.id === 'node-form') {
    const model = fields.get('model');
    const prefix = model.startsWith('CPU') ? 'CPU' : 'GPU';
    const number = data.nodes.filter(node => node.id.startsWith(prefix)).length + 1;
    data.nodes.push({ id: `${prefix} ${String(number).padStart(2, '0')}`, name: fields.get('name').trim(), model, source: fields.get('source'), status: '待审核', util: 0, memory: 0, total: model.startsWith('CPU') ? 32 : 8, task: '—', temperature: 0, cpu: 0 });
    dialog.close(); render(); notify('模拟探测完成，节点已登记为待审核');
  }
});

dialog.addEventListener('close', () => { if (previousFocus?.isConnected) previousFocus.focus(); });
dialog.addEventListener('click', event => { const rect = dialog.getBoundingClientRect(); if (event.target === dialog && (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom)) dialog.close(); });
app.addEventListener('input', event => {
  if (event.target.id === 'run-search') {
    state.query = event.target.value;
    document.querySelector('#run-results').innerHTML = runTable(selectRuns(data.runs, state.filter, state.query), state.scheme, state.scheme === 'c');
  }
});
window.addEventListener('hashchange', () => { Object.assign(state, parseRoute(location.hash), { mobileOpen: false }); render(); window.scrollTo({ top: 0 }); });
render();
