import { taskPresets } from './data.js?v=palette-3';
import { e, button, icon, select, status } from './components.js?v=palette-3';

export function dependentFields(task, run = {}) {
  run = run || {};
  const p = taskPresets[task];
  return `<div class="form-grid"><label class="field"><span>基础模型 <em>*</em></span>${select('model', p.models.includes(run.model) ? run.model : p.models[0], p.models, '基础模型')}</label><label class="field"><span>训练数据 <em>*</em></span>${select('dataset', p.datasets.includes(run.dataset) ? run.dataset : p.datasets[0], p.datasets, '训练数据')}</label></div><div class="form-section">训练参数<span>${p.method}</span></div><div class="parameter-fields"><label class="field"><span>学习率 <em>*</em></span><input class="input" name="lr" type="number" min="0.00000001" max="1" step="any" required value="${run.lr || p.lr}"></label><label class="field"><span>训练轮次 <em>*</em></span><input class="input" name="epochs" type="number" min="1" max="100" step="1" required value="${run.epoch?.split(' / ')[1] || p.epochs}"></label><label class="field"><span>批大小 <em>*</em></span><input class="input" name="batch" type="number" min="1" max="64" step="1" required value="${run.batch || p.batch}"></label></div>`;
}
const modalHead = title => `<header class="modal-head"><h2 id="modal-title">${title}</h2><button class="icon-btn" data-action="close" aria-label="关闭弹窗">${icon('close')}</button></header>`;
const footer = (label = '创建任务') => `<footer class="modal-footer">${button('取消', 'close')}<button type="submit" class="btn primary">${label}</button></footer>`;
export function jobForm(run) {
  const task = run?.task || '文本分类';
  return `${modalHead(run ? '复制训练配置' : '新建训练任务')}<form id="job-form"><div class="modal-body"><div class="form-grid"><label class="field"><span>任务名称 <em>*</em></span><input class="input" name="name" required maxlength="60" placeholder="请输入任务名称" value="${run ? e(run.name + ' 副本') : ''}"></label><label class="field"><span>任务类型 <em>*</em></span>${select('task', task, Object.keys(taskPresets), '任务类型')}</label></div><div id="dependent-fields">${dependentFields(task, run)}</div><div class="form-section">计算资源</div><label class="field"><span>资源池</span>${select('pool', '本地 GPU 资源池', ['本地 GPU 资源池', 'CPU 资源池'], '计算资源池')}</label><div class="resource-inline"><span>RTX 4060 / RTX 4070 Laptop</span><strong>8 GB</strong></div><label class="check-label form-check"><input type="checkbox" name="checkpoint" checked>保存训练检查点</label><div class="field-error" id="form-error" role="alert"></div></div>${footer()}</form>`;
}
export function nodeForm() {
  return `${modalHead('接入计算节点')}<form id="node-form"><div class="modal-body"><label class="field"><span>节点名称 <em>*</em></span><input name="name" class="input" placeholder="例如：实验室 GPU 01" required maxlength="40"></label><label class="field"><span>接入类型</span>${select('source', '本地 Worker', ['本地 Worker', '实验室服务器', '云平台适配器'], '接入类型')}</label><label class="field"><span>设备类型</span>${select('device', 'RTX 4060', ['RTX 4060', 'RTX 4070 Laptop', 'CPU'], '设备类型')}</label><div class="form-section">启动命令示意</div><pre class="command"># 界面示意，不可执行\nworker register --endpoint &lt;平台地址&gt;\n  --token &lt;一次性接入凭证&gt;</pre><div class="alert">登记后进入待审核，硬件探测与接入由后端完成。</div></div>${footer('登记节点')}</form>`;
}
export function confirmStop(runs) {
  const running = runs.some(r => r.status === '运行中');
  return `${modalHead(running ? '停止训练任务' : '取消排队')}<div class="modal-body confirm-body"><p>${runs.map(r => e(r.name)).join('<br>')}</p><div class="alert">${running ? '运行中的任务将标记为已停止，排队任务将标记为已取消。' : '选定任务将移出排队队列，并标记为已取消。'}</div></div><footer class="modal-footer">${button('保留任务', 'close')}${button(running ? '确认停止' : '确认取消', 'confirm-stop', 'danger primary')}</footer>`;
}
export function nodeDrawer(node) {
  return `<header class="modal-head"><h2 id="drawer-title">${e(node.name)}</h2><button class="icon-btn" data-action="close-drawer" aria-label="关闭资源详情">${icon('close')}</button></header><div class="drawer-body">${status(node.status)}<dl class="drawer-info">${[['节点 ID', node.id], ['设备型号', node.model], ['接入方式', node.source], ['显存 / 内存', `${node.memory} / ${node.total} GB`], ['CPU 使用率', node.status === '离线' ? '—' : node.cpu + '%'], ['执行任务', node.task]].map(([k, v]) => `<div><dt>${k}</dt><dd>${e(v)}</dd></div>`).join('')}</dl><h3>资源分配</h3><div class="allocation"><span>所属用户组</span><strong>研发组</strong><span>个人配额</span><strong>1 GPU / 8 GB</strong></div><h3>节点事件</h3><ol class="event-list"><li>${node.status === '待审核' ? '接入登记已提交' : node.status === '离线' ? '心跳中断，等待恢复' : '节点心跳正常'}</li><li>${node.status === '待审核' ? '等待硬件探测' : '资源状态已同步'}</li></ol></div><footer class="modal-footer">${button('关闭', 'close-drawer')}</footer>`;
}
