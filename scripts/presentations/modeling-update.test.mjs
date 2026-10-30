import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { slides, states, transitions, preservedSlides } from './modeling-update-content.mjs';
import { wrapTableCell } from './slide-layout.mjs';

test('正文按需求分解、核心模型、非功能组织，保留 7 页主讲', () => {
  assert.deepEqual(slides.slice(0, 7).map(d => d.kind), ['chapter', 'scope', 'usecase', 'spec', 'activity', 'state', 'nfr']);
  assert.equal(preservedSlides, 29); assert.equal(slides.length, 11);
  assert.equal(slides.filter(d => d.hidden).length, 3);
});
test('第二阶段不混入类图、时序图或重复分析栏目', () => {
  const copy = JSON.stringify(slides);
  assert.doesNotMatch(copy, /业务类图|时序图|需求分析|不是.+而是|并非|灰色导语/);
});
test('规约保留真实规则编号和可验证业务行为', () => {
  const spec = slides.find(d => d.kind === 'spec');
  for (const rule of ['D-05', 'T-06', 'T-07', 'P-03']) assert.ok(spec.rows.some(row => row[0].includes(rule)));
  assert.match(JSON.stringify(spec), /SHA-256|NFC/);
  assert.match(JSON.stringify(spec), /相同请求标识|异配置返回冲突/);
});
test('完整九状态与终态不可回退', () => {
  assert.equal(new Set(states).size, 9);
  for (const terminal of ['成功', '失败', '已取消', '已停止']) assert.ok(!transitions.some(t => t[0] === terminal));
  assert.ok(transitions.some(t => t[0] === '停止中' && t[1] === '已停止'));
  for (const stage of ['准备中', '运行中', '归档中']) assert.ok(transitions.some(t => t[0] === stage && t[1] === '失败'));
});
test('原生表格内容在设计高度内，不缩小到小字', () => {
  const bounds = { scope: 385, spec: 348, nfr: 248, ai: 390 };
  for (const d of slides.filter(d => d.rows)) {
    const size = d.kind === 'ai' ? 23 : 20;
    const rows = [d.headers, ...d.rows].map(row => row.map((v, c) => wrapTableCell(v, d.widths[c], size)));
    const h = rows.reduce((sum, row, r) => sum + Math.max(...row.map(v => v.split('\n').length)) * size * 1.29 + (r ? 15 : 18), 0);
    assert.ok(h <= bounds[d.kind], `${d.kind}: ${h}/${bounds[d.kind]}`);
    assert.equal(d.widths.reduce((a, b) => a + b), 1000);
  }
});
test('非功能负载明确为拟定条件，未声称实测通过', () => {
  const nfr = slides.find(d => d.kind === 'nfr');
  assert.match(nfr.load, /拟定验收负载/); assert.match(nfr.load, /20 个会话/);
  assert.doesNotMatch(JSON.stringify(nfr), /实测通过|测试通过|已实现/);
});
test('模型图及源图片存在，连线提升至正文背景之上', () => {
  const source = fs.readFileSync(new URL('./modeling-update-layout.mjs', import.meta.url), 'utf8');
  assert.match(source, /bringToFront/); assert.match(source, /发布推理服务/);
  for (const d of slides.filter(d => d.asset)) assert.ok(fs.existsSync(new URL(`../../docs/需求调研+需求分析/图片/${d.asset}`, import.meta.url)));
  assert.doesNotMatch(source, /页内导语|本页结论|color: MUTED/);
});
test('活动结束节点内圆不会被外圆白底遮住', () => {
  const source = fs.readFileSync(new URL('./modeling-update-layout.mjs', import.meta.url), 'utf8');
  assert.match(source, /const outer = node\(s, '', x, y, 18, 18, 'ellipse', 'none'\)/);
});
