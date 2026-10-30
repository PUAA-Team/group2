import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createFixtures, summarize, selectRuns, parseRoute, schemes, navigation } from './data.js';
import { shell, escapeHtml, chart } from './ui.js';
import { renderHome } from './home.js';
import { renderRun } from './detail.js';
import { renderResources } from './resources.js';

const makeState = scheme => ({ scheme, page: 'home', groups: {}, collapsed: false, mobileOpen: false, filter: '全部', query: '', metric: 'loss', runId: 'TRN-1048', runTab: 'metrics', resourceTab: 'devices' });

test('四套方案使用同一组任务和资源数据', () => {
  assert.deepEqual(summarize(createFixtures()), { running: 2, queued: 1, completed: 2, failed: 1, gpu: 5, online: 5, idle: 2 });
  assert.notEqual(createFixtures().runs, createFixtures().runs);
});

test('路由可识别四套方案和三个示范页面', () => {
  assert.deepEqual(parseRoute('#/c/resources'), { scheme: 'c', page: 'resources' });
  assert.deepEqual(parseRoute('#/b/run'), { scheme: 'b', page: 'run' });
  assert.deepEqual(parseRoute('#/unknown/run'), { scheme: 'gallery', page: 'run' });
  assert.deepEqual(parseRoute(''), { scheme: 'gallery', page: 'home' });
});

test('搜索支持任务、模型与状态组合', () => {
  const data = createFixtures();
  assert.equal(selectRuns(data.runs, '运行中').length, 2);
  assert.equal(selectRuns(data.runs, '运行中', 'qwen').length, 1);
  assert.equal(selectRuns(data.runs, '全部', '客服').length, 4);
  assert.equal(selectRuns(data.runs, '全部', '不存在').length, 0);
});

test('四套布局有不同的页面结构，十二个页面可渲染', () => {
  const data = createFixtures();
  const landmarks = { a: 'workspace-columns', b: 'experiment-layout', c: 'device-matrix', d: 'asset-shelf' };
  for (const { id } of schemes) {
    const state = makeState(id);
    assert.ok(renderHome(state, data).includes(landmarks[id]));
    for (const [page, render] of [['home', renderHome], ['run', renderRun], ['resources', renderResources]]) {
      state.page = page;
      const result = shell(state, render(state, data));
      assert.ok(result.includes('模拟数据'));
      assert.ok(result.includes('aria-label="主导航"'));
      assert.ok(result.includes('<h1>'));
      assert.ok(!result.includes('undefined'));
    }
  }
});

test('导航分组全部默认展开，手动收起状态可以保留', () => {
  const state = makeState('a');
  const allOpen = shell(state, '');
  assert.equal((allOpen.match(/aria-expanded="true"/g) || []).length, navigation.length);
  state.groups.training = false;
  assert.equal((shell(state, '').match(/aria-expanded="false"/g) || []).length, 1);
});

test('不展示伪造运行曲线，动态文本使用 HTML 转义', () => {
  const state = makeState('a');
  state.runId = 'TRN-1045';
  assert.ok(renderRun(state, createFixtures()).includes('当前状态暂无可展示曲线'));
  assert.equal(escapeHtml('<img onerror="x">'), '&lt;img onerror=&quot;x&quot;&gt;');
});

test('样例独立保存偏好，不使用现有原型的存储键', async () => {
  const script = await readFile(new URL('./app.js', import.meta.url), 'utf8');
  assert.ok(script.includes('model-training-design-review-20261014'));
  assert.ok(!script.includes('model-training-demo-v1'));
  assert.ok(script.includes('dialog.showModal()'));
  assert.ok(script.includes('menu.scrollTop = menuScroll'));
});

test('Windows 静态服务入口使用正确 MIME 类型的 js 扩展名', async () => {
  const html = await readFile(new URL('./index.html', import.meta.url), 'utf8');
  const entry = html.match(/<script type="module" src="([^"]+)"/)?.[1];
  assert.ok(entry?.endsWith('.js'), '本机 http.server 将 mjs 发送为 text/plain，浏览器拒绝执行模块');
});

test('演示曲线的值始终位于绘图坐标范围内', () => {
  for (const metric of ['loss', 'f1']) {
    for (const match of chart(metric, true).matchAll(/<polyline points="([^"]+)"/g)) {
      for (const point of match[1].split(' ')) {
        const [x, y] = point.split(',').map(Number);
        assert.ok(x >= 48 && x <= 710 && y >= 50 && y <= 200, `曲线超出范围: ${metric} ${point}`);
      }
    }
  }
});

test('视觉任务使用自己的指标名称，排队任务没有已完成的执行阶段', () => {
  const state = makeState('a');
  state.runId = 'TRN-1047';
  state.metric = 'f1';
  assert.ok(!renderRun(state, createFixtures()).includes('验证 F1'));
  state.runId = 'TRN-1045';
  assert.ok(!renderRun(state, createFixtures()).includes('execution-step done'));
});

test('资源管理只标记一个导航位置，菜单任务数量使用当前记录', () => {
  const state = makeState('a');
  state.page = 'resources';
  state.runCount = 9;
  const nav = shell(state, '').match(/<nav class="sidebar-scroll"[\s\S]*?<\/nav>/)[0];
  assert.equal((nav.match(/class="nav-(?:child|admin) current"/g) || []).length, 1);
  assert.ok(nav.includes('class="nav-count">9</span>'));
});

test('待审核节点不计入在线节点', () => {
  const data = createFixtures();
  data.nodes.push({ id: 'GPU 06', status: '待审核' });
  assert.equal(summarize(data).online, 5);
});
