import test from 'node:test';
import assert from 'node:assert/strict';
import { research } from './research-content.mjs';
import { analysis } from './analysis-content.mjs';
import { surveyRatio, wrapTableCell, surveyAxes } from './slide-layout.mjs';

test('两份分别完整且合计 15 页主讲', () => {
  assert.equal(research.slides.length, 27);
  assert.equal(analysis.slides.length, 20);
  assert.equal(research.mainCount + analysis.mainCount, 15);
});
test('所有图表人数有效，Q9 互斥分类合计为 67', () => {
  const charts = research.slides.flatMap(s => s.chart ? [s.chart] : s.charts || []);
  for (const c of charts) {
    assert.equal(c.labels.length, c.counts.length);
    assert.ok(c.counts.every(n => Number.isInteger(n) && n >= 0 && n <= 67));
  }
  const q9 = charts.find(c => c.title.startsWith('Q9'));
  assert.deepEqual(q9.counts, [16, 19, 24, 8]);
  assert.equal(q9.counts.reduce((a, b) => a + b), 67);
});
test('Q5 标签与原始报告一致，计算资源及日志查看不能改写为模型或理解问题', () => {
  const chart = research.slides.find(s => s.chart?.title.startsWith('Q5')).chart;
  assert.deepEqual(chart.labels, ['缺少 GPU 资源', '不会选择计算资源', '训练参数难配置', '日志不容易查看', '训练进度不清楚', '数据处理困难']);
  assert.deepEqual(chart.counts, [45, 45, 44, 44, 41, 39]);
});
test('百分比固定精度仍与原始人数的两位百分比一致', () => {
  for (let n = 0; n <= 67; n++) {
    assert.equal((surveyRatio(n) * 100).toFixed(2), (n / 67 * 100).toFixed(2));
    assert.ok(String(surveyRatio(n)).length <= 8);
  }
});
test('模板占位只用于用户确认的人员、AI 记录和五类模型图', () => {
  const frames = analysis.slides.filter(s => s.kind === 'diagram');
  assert.equal(frames.length, 5);
  assert.ok(frames.every(s => s.frame.includes('CodeArts')));
  assert.ok(research.slides.slice(8, 16).every(s => s.rows.length >= 6));
});
test('表格列数一致，每页均保留来源与结论', () => {
  for (const d of [research, analysis]) for (const s of d.slides) {
    assert.ok(s.source);
    if (s.kind !== 'cover') assert.ok(s.conclusion);
    if (s.kind === 'table') {
      assert.ok(s.rows.every(row => row.length === s.headers.length));
      assert.ok(Math.abs(s.widths.reduce((a, b) => a + b, 0) - 1) < 1e-8);
    }
  }
});
test('英文模型和框架名称不会被跨行拆开', () => {
  const input = 'PyTorch/Transformers/PEFT；MindSpore 作为执行适配候选';
  const result = wrapTableCell(input, 400, 21);
  assert.ok(result.includes('MindSpore'));
  assert.ok(result.includes('Transformers'));
  assert.equal(result.replace(/\n/g, ''), input);
});
test('水平条形图的数值轴固定为 0 到 100%', () => {
  const axes = surveyAxes(20);
  assert.equal(axes.yAxis.min, 0);
  assert.equal(axes.yAxis.max, 1);
  assert.equal(axes.yAxis.majorUnit, 0.25);
  assert.equal(axes.yAxis.numberFormatCode, '0%');
});
test('中文换行不会以句读开始或留下孤立标点', () => {
  const wrapped = wrapTableCell('记录数据集版本、标注状态和字段。', 155, 20);
  assert.ok(wrapped.split('\n').every(line => !/^[、，。；：！？）】》]/.test(line)));
  assert.equal(wrapped.replace(/\n/g, ''), '记录数据集版本、标注状态和字段。');
});
test('图框右侧文字在指定行高内，不与下一节标题重叠', () => {
  for (const s of analysis.slides.filter(s => s.sections)) {
    for (const item of s.sections) {
      const lines = wrapTableCell(item.text, 412, 20).split('\n').length;
      assert.ok(lines * 24 <= 80, `${s.title}：${item.heading}`);
    }
  }
});

test('问卷主讲页侧栏不以括号或句读开始一行', () => {
  for (const item of research.slides[6].aside) {
    const lines = wrapTableCell(item.text, 360, 20).split('\n');
    assert.ok(lines.every(line => !/^[、，。；：！？）】》]/.test(line)));
    assert.ok(lines.length <= 4);
  }
});
