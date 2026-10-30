import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fixtures, systems, route, filterRuns, validateJob, stopStatus, nodeSummary } from './data.js';
import { e, chart, select } from './components.js';
import { jobs, detail, resources, componentPage } from './pages.js';
import { shell } from './shell.js';
import { jobForm, nodeForm } from './forms.js';
import { palettes, defaults, normalizeAppearance, paletteTokens, contrast, appearanceForm } from './appearance.js';

const baseState = system => ({ system, page: 'jobs', groups: {}, status: '全部', query: '', sort: 'newest', selected: [], runId: 'TRN-1048', detailTab: 'metrics', resourceTab: 'nodes' });
test('两套体系均使用紧凑正文，按场景区分标题和控件尺寸', () => {
  assert.equal(systems[0].body, 14); assert.equal(systems[1].body, 14);
  for (const key of ['title', 'control', 'row']) assert.notEqual(systems[0][key], systems[1][key]);
  const css = readFileSync(new URL('./cloud.css', import.meta.url), 'utf8');
  assert.match(css, /--body: 14px; --title: 22px/);
  assert.match(css, /--body: 14px; --title: 24px/);
  assert.match(css, /--row: 58px/); assert.match(css, /--row: 64px/);
});
test('路由识别两套方案及四个审查页面', () => {
  assert.deepEqual(route('#/tencent/components'), { system: 'tencent', page: 'components' });
  assert.deepEqual(route('#/invalid'), { system: 'gallery', page: 'jobs' });
});
test('样例数据独立于上一轮数据', () => {
  const a = fixtures(); const b = fixtures(); a.runs[0].status = '已停止';
  assert.equal(b.runs[0].status, '运行中');
});
test('状态、关键词和排序可组合', () => {
  const data = fixtures();
  assert.equal(filterRuns(data.runs, { status: '运行中', query: 'Qwen' }).length, 1);
  assert.equal(filterRuns(data.runs, { query: 'TRN-1045' })[0].id, 'TRN-1045');
  assert.equal(filterRuns(data.runs, { sort: 'oldest' })[0].id, 'TRN-1043');
});
test('表格和字号之外，列组织也分别设计', () => {
  const data = fixtures();
  assert.match(jobs(baseState('ali'), data), /<th>基础模型<\/th>/);
  assert.match(jobs(baseState('tencent'), data), /<th>计算资源<\/th>/);
  assert.doesNotMatch(jobs(baseState('tencent'), data), /task-overview/);
  assert.doesNotMatch(jobs(baseState('ali'), data), /task-overview/);
});
test('每套每页正常生成且表单标识唯一', () => {
  for (const system of ['ali', 'tencent']) {
    const state = baseState(system); const data = fixtures();
    for (const [page, render] of [['jobs', jobs], ['detail', detail], ['resources', resources], ['components', componentPage]]) {
      const html = shell({ ...state, page }, render(state, data));
      assert.doesNotMatch(html, /undefined|NaN/);
      const ids = [...html.matchAll(/\sid="([^"]+)"/g)].map(m => m[1]);
      assert.equal(new Set(ids).size, ids.length, `${system}/${page}`);
    }
  }
});
test('导航默认展开且没有竖线指示条', () => {
  const html = shell(baseState('ali'), '');
  assert.equal((html.match(/nav-group open/g) || []).length, 5);
  assert.equal((html.match(/nav-child current/g) || []).length, 1);
  const css = readFileSync(new URL('./base.css', import.meta.url), 'utf8');
  assert.doesNotMatch(css, /\.nav-child[^}]*border-left/);
});
test('创建与普通配置均通过弹窗表单', () => {
  assert.match(jobForm(), /id="job-form"/);
  assert.match(nodeForm(), /id="node-form"/);
  assert.doesNotMatch(jobs(baseState('ali'), fixtures()), /id="job-form"/);
});
test('新建事件传入空配置时仍能生成弹窗', () => {
  assert.match(jobForm(null), /id="job-form"/);
});
test('CPU 队列不展示 GPU 设备规格', () => {
  const data = fixtures(); data.runs[0].gpu = 'CPU 队列';
  const html = jobs(baseState('tencent'), { ...data, runs: [data.runs[0]] });
  assert.match(html, /CPU 资源池/); assert.doesNotMatch(html, /RTX 4060/);
});
test('自绘选择框具备键盘所需语义', () => {
  const html = select('example', 'LoRA', ['LoRA', '全量训练'], '训练方式');
  assert.match(html, /role="combobox"/); assert.match(html, /aria-controls="options-example"/);
  assert.match(html, /role="listbox"/); assert.match(html, /role="option" aria-selected="true"/);
});
test('浮动选项层不继承视口百分比最小宽度', () => {
  const css = readFileSync(new URL('./base.css', import.meta.url), 'utf8');
  assert.match(css, /\.select-wrap\.open \.options \{[^}]*min-width: 0/);
});
test('模型和数据集随任务类型校验', () => {
  const values = { name: '测试', task: '文本分类', model: 'Qwen3-0.6B', dataset: '客服意图语料 v3', lr: '0.0002', epochs: '5', batch: '4' };
  assert.equal(validateJob(values), '');
  assert.match(validateJob({ ...values, model: 'ResNet18' }), /匹配/);
  assert.match(validateJob({ ...values, dataset: '安全帽样本 v2' }), /匹配/);
  assert.match(validateJob({ ...values, lr: '0' }), /学习率/);
  assert.match(validateJob({ ...values, epochs: '1.5' }), /整数/);
  assert.match(validateJob({ ...values, batch: '100' }), /批大小/);
});
test('运行后停止和排队取消分别处理', () => {
  assert.equal(stopStatus('运行中'), '已停止'); assert.equal(stopStatus('排队中'), '已取消'); assert.equal(stopStatus('已完成'), '已完成');
});
test('待审核和离线节点不计入在线资源', () => {
  const nodes = fixtures().nodes;
  assert.deepEqual(nodeSummary(nodes), { online: 5, gpu: 4, idle: 2, pending: 0 });
  assert.deepEqual(nodeSummary([...nodes, { id: 'GPU NEW 7', status: '待审核' }]), { online: 5, gpu: 4, idle: 2, pending: 1 });
});
test('CPU 使用率和 GPU 使用率分别展示', () => {
  const html = resources(baseState('tencent'), fixtures());
  assert.match(html, /CPU 使用率/); assert.match(html, /GPU 使用率/);
});
test('排队任务不绘制已完成训练曲线', () => {
  const html = detail({ ...baseState('ali'), runId: 'TRN-1045' }, fixtures());
  assert.doesNotMatch(html, /class="metric-chart"/); assert.match(html, /任务正在排队/);
});
test('曲线位于非负坐标范围，分类与检测指标各自命名', () => {
  const svg = chart();
  const points = [...svg.matchAll(/points="([^"]+)"/g)].flatMap(m => m[1].split(' ').map(p => p.split(',').map(Number)));
  assert.ok(points.every(([x, y]) => x >= 54 && x <= 678 && y >= 44 && y <= 218));
  assert.match(detail({ ...baseState('tencent'), runId: 'TRN-1047' }, fixtures()), /mAP/);
});
test('文本均转义且命令明确为示意', () => {
  assert.equal(e('<script>'), '&lt;script&gt;'); assert.match(nodeForm(), /界面示意，不可执行/);
});
test('主方向默认海军蓝、纯文字状态和微圆角', () => {
  assert.deepEqual(defaults(), { color: '#2b5278', status: 'text', corners: 'micro' });
  assert.equal(palettes.length, 6);
});
test('外观偏好保持合法格式，坏记录恢复对应默认', () => {
  assert.deepEqual(normalizeAppearance({ color: 'bad', status: 'bad', corners: 'bad' }, 'ali'), defaults());
  assert.deepEqual(normalizeAppearance({ color: '#276D62', status: 'icon', corners: 'soft' }, 'ali'), { color: '#276d62', status: 'icon', corners: 'soft' });
});
test('预设和自选主色的按钮文字、链接具有可读对比度', () => {
  const colors = [...palettes.map(p => p[1]), '#ffffff', '#000000', '#808080', '#ffff00', '#aaaaaa'];
  for (const color of colors) {
    const tokens = paletteTokens(color, 'ali');
    assert.ok(contrast(color, tokens['--primary-ink']) >= 4.5, color);
    assert.ok(contrast(tokens['--link'], '#ffffff') >= 4.5, color);
  }
});
test('外观入口和选择控件可访问', () => {
  assert.match(shell(baseState('ali'), ''), /data-action="appearance"/);
  const html = appearanceForm(defaults(), 'ali');
  assert.match(html, /aria-label="自选主色"/);
  assert.equal((html.match(/data-appearance="status"/g) || []).length, 3);
  assert.equal((html.match(/data-appearance="corners"/g) || []).length, 3);
});
test('状态不使用小圆点，三种样式由同一模型产生', () => {
  const html = detail(baseState('ali'), fixtures());
  assert.match(html, /status-symbol/); assert.doesNotMatch(html, /<i aria-hidden="true"><\/i>/);
});
test('入口和全部界面模块使用同一版本，避免部分更新', () => {
  const html = readFileSync(new URL('./index.html', import.meta.url), 'utf8');
  assert.match(html, /app\.js\?v=palette-3/);
  assert.match(html, /appearance\.css\?v=palette-3/);
  for (const file of ['app.js', 'appearance.js', 'forms.js', 'pages.js', 'shell.js']) {
    const code = readFileSync(new URL(file, import.meta.url), 'utf8');
    const imports = [...code.matchAll(/from '\.\/([^']+)'/g)];
    assert.ok(imports.every(m => m[1].endsWith('?v=palette-3')), file);
  }
});
