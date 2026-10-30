import { route, fixtures, filterRuns, taskPresets, stopStatus, validateJob } from './data.js?v=palette-3';
import { e, pagination, button } from './components.js?v=palette-3';
import { gallery, shell } from './shell.js?v=palette-3';
import { jobs, detail, resources, componentPage, jobTable } from './pages.js?v=palette-3';
import { jobForm, dependentFields, nodeForm, confirmStop, nodeDrawer } from './forms.js?v=palette-3';
import { normalizeAppearance, paletteTokens, appearanceForm, defaults } from './appearance.js?v=palette-3';

const app = document.querySelector('#app');
const modal = document.querySelector('#modal');
const drawer = document.querySelector('#drawer');
const prefKey = 'model-training-cloud-review-v2';
let prefs;
try { prefs = JSON.parse(localStorage.getItem(prefKey) || '{}'); } catch { prefs = {}; }
const state = { ...route(location.hash), groups: prefs.groups || {}, collapsed: prefs.collapsed || false, chosen: prefs.chosen || '', mobile: false, status: '全部', query: '', sort: 'newest', selected: [], runId: 'TRN-1048', detailTab: 'metrics', resourceTab: 'nodes', componentTab: 'a' };
const data = fixtures();
state.appearance = { ali: normalizeAppearance(prefs.appearance?.ali, 'ali'), tencent: normalizeAppearance(prefs.appearance?.tencent, 'tencent') };
let menuScroll = 0;
let dialogFocus;
let pendingStops = [];
let toastTimer;

function save() {
  localStorage.setItem(prefKey, JSON.stringify({ groups: state.groups, collapsed: state.collapsed, chosen: state.chosen, appearance: state.appearance }));
}
function applyAppearance() {
  const system = state.system === 'gallery' ? 'ali' : state.system;
  const settings = state.appearance[system];
  document.body.dataset.status = settings.status;
  document.body.dataset.corners = settings.corners;
  Object.entries(paletteTokens(settings.color, system)).forEach(([name, value]) => document.body.style.setProperty(name, value));
}
function updateAppearance(key, value) {
  state.appearance[state.system][key] = value;
  applyAppearance(); save();
}
function showAppearance() {
  dialogFocus = document.activeElement;
  drawer.dataset.kind = 'appearance';
  drawer.innerHTML = appearanceForm(state.appearance[state.system], state.system);
  drawer.showModal();
}
function render() {
  menuScroll = document.querySelector('.sidebar-scroll')?.scrollTop ?? menuScroll;
  document.body.dataset.system = state.system === 'gallery' ? 'ali' : state.system;
  applyAppearance();
  app.innerHTML = state.system === 'gallery' ? gallery(state.chosen) : shell(state, state.page === 'jobs' ? jobs(state, data) : state.page === 'detail' ? detail(state, data) : state.page === 'resources' ? resources(state, data) : componentPage(state, data));
  const nav = document.querySelector('.sidebar-scroll');
  if (nav) nav.scrollTop = menuScroll;
  syncChecks();
}
function syncChecks() {
  const all = document.querySelector('[data-check-all]');
  const visible = filterRuns(data.runs, state);
  if (all) {
    all.checked = visible.length > 0 && visible.every(r => state.selected.includes(r.id));
    all.indeterminate = !all.checked && visible.some(r => state.selected.includes(r.id));
  }
}
function toast(message) {
  clearTimeout(toastTimer);
  const box = document.querySelector('#toast');
  box.textContent = message;
  box.classList.add('visible');
  toastTimer = setTimeout(() => box.classList.remove('visible'), 2400);
}
function openModal(html, type = '') {
  dialogFocus = document.activeElement;
  modal.className = type;
  modal.innerHTML = html;
  modal.showModal();
  (modal.querySelector('input:not([type="hidden"])') || modal.querySelector('button'))?.focus();
}
function closeDialog(target = modal) {
  target.close();
  if (dialogFocus?.isConnected) dialogFocus.focus();
}
function stop(ids) {
  pendingStops = data.runs.filter(r => ids.includes(r.id) && ['运行中', '排队中'].includes(r.status));
  if (pendingStops.length) openModal(confirmStop(pendingStops), 'confirm-dialog');
}
function results() {
  const target = document.querySelector('#job-results');
  if (target) {
    const filtered = filterRuns(data.runs, state);
    target.innerHTML = jobTable(filtered, state) + pagination(filtered.length);
    syncChecks();
  }
}

// 下拉控件保持原生表单值，统一维护展开状态与键盘焦点。
function closeSelects(except) {
  document.querySelectorAll('.select-wrap.open').forEach(w => {
    if (w !== except) {
      w.classList.remove('open');
      w.querySelector('.options').hidden = true;
      const c = w.querySelector('[role="combobox"]');
      c.setAttribute('aria-expanded', 'false');
      c.removeAttribute('aria-activedescendant');
    }
  });
}
function toggleSelect(w) {
  const open = !w.classList.contains('open');
  closeSelects(w);
  w.classList.toggle('open', open);
  w.querySelector('.options').hidden = !open;
  w.querySelector('[role="combobox"]').setAttribute('aria-expanded', String(open));
  if (open) {
    const rect = w.querySelector('[role="combobox"]').getBoundingClientRect();
    const list = w.querySelector('.options');
    const height = Math.min(list.scrollHeight, 240);
    const below = window.innerHeight - rect.bottom - 12;
    list.style.left = `${rect.left}px`;
    list.style.width = `${rect.width}px`;
    list.style.maxHeight = `${Math.min(height, Math.max(below, rect.top - 12))}px`;
    list.style.top = `${below >= height ? rect.bottom + 4 : Math.max(8, rect.top - height - 4)}px`;
    w.querySelectorAll('[role="option"]').forEach(o => o.classList.remove('highlighted'));
    const opt = w.querySelector('[aria-selected="true"]') || w.querySelector('[role="option"]');
    opt.classList.add('highlighted');
    w.querySelector('[role="combobox"]').setAttribute('aria-activedescendant', opt.id);
  }
}
function chooseOption(opt) {
  const w = opt.closest('.select-wrap');
  const hidden = w.querySelector('input');
  hidden.value = opt.dataset.value;
  w.querySelector('.select-value').textContent = hidden.value;
  w.querySelectorAll('[role="option"]').forEach(o => o.setAttribute('aria-selected', String(o === opt)));
  closeSelects();
  w.querySelector('[role="combobox"]').focus();
  if (hidden.name === 'filter-status') { state.status = hidden.value; state.selected = []; render(); }
  if (hidden.name === 'task') document.querySelector('#dependent-fields').innerHTML = dependentFields(hidden.value);
  if (hidden.name === 'pool') document.querySelector('.resource-inline').innerHTML = hidden.value === 'CPU 资源池' ? '<span>CPU 节点 / 16 核</span><strong>32 GB</strong>' : '<span>RTX 4060 / RTX 4070 Laptop</span><strong>8 GB</strong>';
}
document.addEventListener('click', event => {
  const combobox = event.target.closest('[role="combobox"]');
  if (combobox) { toggleSelect(combobox.closest('.select-wrap')); return; }
  const option = event.target.closest('[role="option"]');
  if (option) { chooseOption(option); return; }
  if (!event.target.closest('.select-wrap')) closeSelects();
  const run = event.target.closest('[data-run]');
  if (run) { state.runId = run.dataset.run; state.detailTab = 'metrics'; }
  const control = event.target.closest('[data-action]');
  if (!control) return;
  event.preventDefault();
  const action = control.dataset.action;
  const value = control.dataset.value;
  if (action === 'appearance') showAppearance();
  else if (action === 'palette') { updateAppearance('color', value); drawer.innerHTML = appearanceForm(state.appearance[state.system], state.system); }
  else if (action === 'appearance-reset') { state.appearance[state.system] = defaults(state.system); applyAppearance(); save(); drawer.innerHTML = appearanceForm(state.appearance[state.system], state.system); }
  else if (action === 'new-job' || action === 'clone') openModal(jobForm(action === 'clone' ? data.runs.find(r => r.id === control.dataset.id) : null));
  else if (action === 'new-node') openModal(nodeForm());
  else if (action === 'close') closeDialog();
  else if (action === 'close-drawer') closeDialog(drawer);
  else if (action === 'stop') stop([control.dataset.id]);
  else if (action === 'stop-selected') stop(state.selected);
  else if (action === 'confirm-stop') {
    pendingStops.forEach(r => { r.status = stopStatus(r.status); });
    state.selected = []; closeDialog(); render(); toast('任务状态已更新');
  } else if (action === 'status') { state.status = value; state.selected = []; render(); }
  else if (action === 'reset') { state.status = '全部'; state.query = ''; state.selected = []; render(); }
  else if (action === 'sort') { state.sort = state.sort === 'newest' ? 'oldest' : 'newest'; render(); }
  else if (action === 'tab') { state.detailTab = value; render(); }
  else if (action === 'component-tab') { state.componentTab = value; render(); }
  else if (action === 'resource-tab') { state.resourceTab = value; render(); }
  else if (action === 'group') {
    state.groups[value] = state.groups[value] === false;
    control.closest('.nav-group').classList.toggle('open', state.groups[value]);
    control.setAttribute('aria-expanded', String(state.groups[value])); save();
  } else if (action === 'collapse') { state.collapsed = !state.collapsed; document.querySelector('.workspace').classList.toggle('collapsed', state.collapsed); save(); }
  else if (action === 'mobile') { state.mobile = !state.mobile; document.querySelector('.workspace').classList.toggle('mobile-open', state.mobile); }
  else if (action === 'choose' || action === 'clear') { state.chosen = action === 'clear' ? '' : value; save(); render(); }
  else if (action === 'node') {
    dialogFocus = document.activeElement;
    drawer.dataset.kind = 'resource';
    drawer.innerHTML = nodeDrawer(data.nodes.find(n => n.id === control.dataset.id)); drawer.showModal();
  } else if (action === 'detail' || action === 'show-logs') {
    state.detailTab = action === 'show-logs' ? 'logs' : 'metrics'; location.hash = `#/${state.system}/detail`;
  } else if (action === 'scope' || action === 'artifact' || action === 'notice') {
    openModal(`<header class="modal-head"><h2 id="modal-title">${e(value || (action === 'artifact' ? '训练产物' : '通知'))}</h2></header><div class="modal-body"><p>${action === 'artifact' ? '样例仅展示产物信息，未提供模型文件。' : '本轮审查覆盖训练任务、任务详情、资源管理和组件规范。'}</p></div><footer class="modal-footer">${button('关闭', 'close', 'primary')}</footer>`, 'confirm-dialog');
  } else if (action === 'refresh' || action === 'feedback') toast(action === 'refresh' ? '样例数据已刷新' : '配置已保存（演示）');
});
[modal, drawer].forEach(d => d.addEventListener('scroll', event => { if (!event.target.closest('.options')) closeSelects(); }, true));
window.addEventListener('resize', () => closeSelects());
document.addEventListener('toggle', event => {
  const menu = event.target;
  if (!menu.matches?.('.dropdown') || !menu.open) return;
  const list = menu.querySelector('.dropdown-menu');
  const rect = menu.querySelector('summary').getBoundingClientRect();
  list.style.left = `${Math.max(8, rect.right - list.offsetWidth)}px`;
  list.style.top = `${window.innerHeight - rect.bottom > list.offsetHeight + 8 ? rect.bottom + 4 : rect.top - list.offsetHeight - 4}px`;
}, true);
document.addEventListener('scroll', event => {
  if (event.target.closest?.('.options')) return;
  if (event.target.matches?.('.main, .sidebar-scroll, .modal-body')) {
    closeSelects(); document.querySelectorAll('.dropdown[open]').forEach(menu => { menu.open = false; });
  }
}, true);
document.addEventListener('input', event => {
  if (event.target.hasAttribute('data-custom-color')) {
    updateAppearance('color', event.target.value);
    document.querySelector('#color-value').textContent = event.target.value.toUpperCase();
    drawer.querySelectorAll('.palette-choice').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.value === event.target.value)));
  }
  if (event.target.name === 'query') { state.query = event.target.value; results(); }
});
document.addEventListener('change', event => {
  const box = event.target;
  if (box.dataset.appearance) { updateAppearance(box.dataset.appearance, box.value); return; }
  if (box.hasAttribute('data-check-all')) {
    state.selected = box.checked ? filterRuns(data.runs, state).map(r => r.id) : []; render();
  } else if (box.dataset.check) {
    state.selected = box.checked ? [...new Set([...state.selected, box.dataset.check])] : state.selected.filter(id => id !== box.dataset.check); render();
  }
});
document.addEventListener('submit', event => {
  event.preventDefault();
  const values = Object.fromEntries(new FormData(event.target));
  if (event.target.id === 'search-form') { state.query = values.query; results(); }
  if (event.target.id === 'job-form') {
    const error = validateJob(values);
    if (error) { document.querySelector('#form-error').textContent = error; return; }
    const preset = taskPresets[values.task];
    const id = `TRN-${Math.max(...data.runs.map(r => Number(r.id.split('-')[1]))) + 1}`;
    data.runs.unshift({ id, name: values.name.trim(), project: values.task, task: values.task, model: values.model, dataset: values.dataset, lr: values.lr, epoch: `0 / ${values.epochs}`, batch: Number(values.batch), rank: preset.method === 'LoRA' ? 8 : undefined, status: '排队中', progress: 0, score: '—', metric: values.task === '目标检测' ? 'mAP' : values.task === '图像分类' ? '准确率' : '宏平均 F1', gpu: values.pool === 'CPU 资源池' ? 'CPU 队列' : 'GPU 队列', duration: '等待调度', memory: 0, owner: '平台管理员', created: '2026-10-14 10:43' });
    state.status = '全部'; state.query = ''; state.selected = []; closeDialog();
    if (state.page !== 'jobs') location.hash = `#/${state.system}/jobs`; else render();
    toast('演示任务已创建');
  }
  if (event.target.id === 'node-form') {
    const gpu = values.device !== 'CPU';
    data.nodes.push({ id: `${gpu ? 'GPU' : 'CPU'} NEW ${data.nodes.length + 1}`, name: values.name.trim(), model: values.device, source: values.source, status: '待审核', util: 0, memory: 0, total: gpu ? 8 : 32, task: '—', cpu: 0 });
    closeDialog(); render(); toast('节点已登记，等待后端探测');
  }
});
document.addEventListener('keydown', event => {
  const combo = event.target.closest('[role="combobox"]');
  if (!combo) { if (event.key === 'Escape') closeSelects(); return; }
  const w = combo.closest('.select-wrap');
  if (event.key === 'Escape' && w.classList.contains('open')) { event.preventDefault(); event.stopPropagation(); closeSelects(); }
  if (['ArrowDown', 'ArrowUp'].includes(event.key)) {
    event.preventDefault();
    if (!w.classList.contains('open')) { toggleSelect(w); return; }
    const options = [...w.querySelectorAll('[role="option"]')];
    const old = options.findIndex(o => o.id === combo.getAttribute('aria-activedescendant'));
    const index = (old + (event.key === 'ArrowDown' ? 1 : -1) + options.length) % options.length;
    options.forEach(o => o.classList.remove('highlighted')); options[index].classList.add('highlighted');
    combo.setAttribute('aria-activedescendant', options[index].id); options[index].scrollIntoView({ block: 'nearest' });
  } else if (event.key === 'Enter' && w.classList.contains('open')) {
    event.preventDefault(); chooseOption(w.querySelector(`#${combo.getAttribute('aria-activedescendant')}`));
  } else if (event.key === 'Tab') closeSelects();
});
[modal, drawer].forEach(d => d.addEventListener('close', () => { closeSelects(); if (dialogFocus?.isConnected) dialogFocus.focus(); }));
window.addEventListener('hashchange', () => { Object.assign(state, route(location.hash), { mobile: false }); if (modal.open) modal.close(); if (drawer.open) drawer.close(); render(); });
render();
