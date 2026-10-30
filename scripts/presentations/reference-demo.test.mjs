import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import { demo, surveyCounts, trainingStates } from './reference-demo-content.mjs';
import { layoutDemo } from './reference-demo-layout.mjs';

const draftDir = new URL('../../docs/需求调研+需求分析/参考对照补充样稿/', import.meta.url);
test('四章及用例/活动/状态模型各有独立页', () => {
  assert.equal(demo.chapters.length, 4);
  assert.deepEqual(demo.slides.filter(s => s.kind === 'chapter').map(s => s.number), [1, 2, 3, 4]);
  for (const type of ['usecase', 'activity', 'state']) assert.equal(demo.slides.filter(s => s.diagram === type).length, 1);
  assert.ok(demo.slides.every(s => s.main));
});
test('问卷口径与九个服务端状态固定', () => {
  assert.deepEqual(surveyCounts.q9, [16, 19, 24, 8]);
  assert.equal(surveyCounts.q9.reduce((a, b) => a + b), 67);
  assert.deepEqual(surveyCounts.q5, [45, 44, 44]);
  assert.equal(trainingStates.length, 9);
  assert.equal(new Set(trainingStates).size, 9);
  for (const s of ['Finalizing', 'Cancelled', 'Stopped']) assert.ok(trainingStates.includes(s));
});
test('详细用例全部有验收设计，SPEC 包含22个测试', async () => {
  const uc = await fs.readFile(new URL('用例与业务规则补充稿.md', draftDir), 'utf8');
  const sections = [...uc.matchAll(/^### (UC-[A-Z]\d+) .+$/gm)];
  assert.equal(sections.length, 13);
  for (const m of sections) assert.ok(uc.includes(`AT-${m[1].slice(3)}`), m[1]);
  const spec = await fs.readFile(new URL('核心模块开发规范SPEC.md', draftDir), 'utf8');
  assert.equal([...spec.matchAll(/^\| T[DRT]\d\d \|/gm)].length, 22);
  assert.ok(uc.includes('| UC-D02 | 生成并检查处理后的新版本 | FR-DAT-004、候选 FR-DAT-007 |'));
});
test('全部表格行列完整，正文无来源脚注和空洞宣传', () => {
  for (const d of demo.slides.filter(s => s.kind === 'table')) {
    assert.equal(d.widths.length, d.headers.length);
    assert.ok(Math.abs(d.widths.reduce((a, b) => a + b) - 1) < 0.001);
    for (const row of d.rows) assert.equal(row.length, d.headers.length);
  }
  const copy = JSON.stringify(demo);
  for (const term of ['截图来源', '原始像素', 'X178', '三轮原型测试', '全面赋能']) assert.ok(!copy.includes(term), term);
});
test('组/个人权限、任务书要求及模拟边界有明确内容', () => {
  const txt = JSON.stringify(demo);
  for (const term of ['UUID', '任务类型', '较小', '日志导出', 'SDK/API/CLI', '不可变', '未执行真实训练', 'CodeArts']) assert.ok(txt.includes(term), term);
});
test('图片裁切必须提供完整四边参数', () => {
  for (const slide of demo.slides.filter(s => s.crop)) {
    assert.deepEqual(Object.keys(slide.crop).sort(), ['bottom', 'left', 'right', 'top']);
  }
});
test('复用版式与模型对象均在幻灯片范围内', async () => {
  for (const d of demo.slides) {
    const shape = (name = '', position = null) => new Proxy({ name, position, text: { style: {} } }, { set(obj, key, value) {
      obj[key] = key === 'text' ? Object.assign(new String(value), { style: {} }) : value; return true;
    } });
    const objects = [];
    const connections = [];
    const slide = {
      speakerNotes: {}, shapes: {
        items: ['矩形6', '任意多边形16', '矩形12', '标题1', '文本框27', '文本框28', '矩形11'].map(n => shape(n)),
        add(c) { objects.push(c); return shape(c.name, c.position); },
        connect(from, to, options) { const record = { from, to, options, visible: false }; connections.push(record);
          return { bringToFront() { record.visible = true; } }; },
      }, images: { add(c) { objects.push(c); } },
      tables: { add: c => ({ rows: Array.from({ length: c.rows }, () => ({})), borders: { assign() {} },
        cells: { block: () => ({ assign() {} }) }, getCell: () => shape() }) },
    };
    await layoutDemo(slide, d, demo, 'D:/model-training-demo/style-samples-20261011/assets', () => {}, {});
    for (const c of objects) if (c.position) {
      const { left, top, width, height } = c.position;
      assert.ok(left >= 0 && top >= 0 && left + width <= 1280 && top + height <= 720, d.title);
    }
    assert.equal(slide.speakerNotes.text, '');
    for (const link of connections) {
      assert.ok(link.visible, '连线不能留在模板背景下');
      if (!link.options.association) {
        assert.equal(link.options.tail?.type, 'arrow', '箭头必须位于目标端');
        assert.equal(link.options.head, undefined, '源端不应显示反向箭头');
      }
    }
  }
});
