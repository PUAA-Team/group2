import test from 'node:test';
import assert from 'node:assert/strict';
import { researchV2, analysisV2, taskMapping } from './defense-v2-content.mjs';
import { layoutSlide } from './defense-v2-layout.mjs';
import { wrapTableCell } from './slide-layout.mjs';

test('两稿各有四章，合计十五页主讲', () => {
  assert.equal(researchV2.slides.filter(s => s.main).length, 8);
  assert.equal(analysisV2.slides.filter(s => s.main).length, 7);
  for (const d of [researchV2, analysisV2]) assert.deepEqual(d.slides.filter(s => s.kind === 'chapter').map(s => s.number), [1, 2, 3, 4]);
});
test('五项背景要求和分析验收都有任务书对应', () => {
  assert.equal(taskMapping.length, 5);
  const txt = JSON.stringify(taskMapping);
  for (const term of ['GPU 2/3', '任务类型', '日志', '推理', '数据', '扩展']) assert.ok(txt.includes(term));
  assert.ok(analysisV2.slides.some(s => s.title === '任务书要求、需求模型与验收'));
});
test('BML 调研是主要案例，全部八个平台保留', () => {
  assert.equal(researchV2.slides.filter(s => s.title.startsWith('BML：')).length, 5);
  const txt = JSON.stringify(researchV2);
  for (const term of ['BML', 'ModelArts', 'PAI', 'TI-ONE', 'SageMaker', 'Azure ML', 'Crater', 'Kubeflow', 'SDK', 'CLI']) assert.ok(txt.includes(term));
  const capabilities = researchV2.slides.find(s => s.title === 'ModelArts：分布式、续训与资源池边界');
  for (const term of ['分布式训练', '断点续训', '在线推理', '资源池与权限']) assert.ok(capabilities.sections.some(s => s.heading === term));
});
test('校验模型截图不能当作部署截图', () => {
  const deployment = researchV2.slides.find(s => s.title.includes('部署方式'));
  assert.equal(deployment.kind, 'story');
  assert.ok(!researchV2.slides.some(s => s.asset === 'bml/page-08-image-02.png'));
});
test('五类 UML 插图框保持独立，表格宽度与行列完整', () => {
  assert.deepEqual(analysisV2.slides.filter(s => s.kind === 'frame').map(s => s.layout).sort(), ['activity', 'class', 'sequence', 'state', 'usecase']);
  for (const d of [researchV2, analysisV2]) for (const s of d.slides.filter(s => s.kind === 'table')) {
    assert.equal(s.headers.length, s.widths.length);
    assert.ok(Math.abs(s.widths.reduce((a, b) => a + b) - 1) < 0.001);
    for (const row of s.rows) assert.equal(row.length, s.headers.length);
  }
});
test('正文没有本地图片来源和制作流程提醒', () => {
  const copy = [researchV2, analysisV2].flatMap(d => d.slides.map(({ asset, crop, ...s }) => s));
  const txt = JSON.stringify(copy);
  for (const term of ['截图来源', 'X178', '原始像素提取', '不能据此声称', '建议补充', '插入 CodeArts', '本页结论']) assert.ok(!txt.includes(term), term);
  const q5 = researchV2.slides.find(s => s.kind === 'survey').chart;
  assert.deepEqual(q5.counts, [45, 45, 44, 44, 41, 39]);
  assert.equal(q5.labels[1], '不会选择计算资源');
  assert.equal(q5.labels[3], '日志不容易查看');
});
test('所有正文区块能装入预定版式', async () => {
  for (const deck of [researchV2, analysisV2]) for (const d of deck.slides) {
    const shape = () => ({ text: { style: {} } });
    const items = ['矩形6', '任意多边形16', '矩形12', '标题1', '文本框27', '文本框28', '矩形11'].map(name => ({ name, ...shape() }));
    // 用轻量替身验证版式容量，不导入或导出 PPT。
    const proxy = value => new Proxy(value, { set(obj, key, v) { obj[key] = key === 'text' ? Object.assign(new String(v), { style: {} }) : v; return true; } });
    const slide = {
      speakerNotes: {}, shapes: { items: items.map(proxy), add: () => proxy(shape()) },
      images: { add() {} }, charts: { add: () => ({}) },
      tables: { add: config => ({ rows: Array.from({ length: config.rows }, () => ({})), borders: { assign() {} }, cells: { block: () => ({ assign() {} }) }, getCell: () => proxy(shape()) }) },
    };
    await layoutSlide(slide, d, deck, 'D:/model-training-demo/style-samples-20261011/assets', () => {}, {});
  }
});
test('百分号与数值不跨行拆开', () => {
  const copy = 'Q13 常用参数优先或双模式共 49 人（73.13%）；Q14 标签页 27 人（40.30%），为最大单项。';
  assert.ok(!wrapTableCell(copy, 492, 21).includes('73.13\n%'));
});
test('秒数与单位不跨行拆开', () => {
  const copy = '普通查询 p95 ≤ 2 s。提交持久化后 ≤ 3 s 返回 ID。指标采集到页面 ≤ 5 s。测试明确并发和数据规模。';
  assert.ok(!/3 *\ns\b/.test(wrapTableCell(copy, 492, 21)));
});
