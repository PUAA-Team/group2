import test from 'node:test';
import assert from 'node:assert/strict';
import { researchV3, surveyData } from './research-v3-content.mjs';
import { layoutSlide } from './defense-v2-layout.mjs';
import { layoutResearch } from './research-v3-layout.mjs';
import path from 'node:path';

export function fakeSlide() {
  const added = [];
  const shape = (name = '') => new Proxy({ name, text: { style: {} } }, { set(o, k, v) {
    o[k] = k === 'text' ? Object.assign(new String(v), { style: {} }) : v; return true;
  } });
  return {
    added, speakerNotes: {},
    shapes: { items: ['矩形6', '任意多边形16', '矩形12', '标题1', '文本框27', '文本框28', '矩形11'].map(shape),
      add(c) { const s = shape(c.name); s.position = c.position; added.push(s); return s; } },
    images: { add() {} }, charts: { add() { return {}; } },
    tables: { add(c) { return { rows: Array.from({ length: c.rows }, () => ({})), borders: { assign() {} },
      cells: { block: () => ({ assign() {} }) }, getCell: () => shape() }; } },
  };
}
test('研究页移除章名小字，章节页只显示章名', async () => {
  const slide = fakeSlide();
  await layoutSlide(slide, { kind: 'story', title: '测试', chapter: 1, sections: [] }, researchV3, '', () => {}, {});
  assert.equal(slide.added.length, 0, '仍添加了重复章名');
  const chapter = fakeSlide();
  await layoutSlide(chapter, { kind: 'chapter', number: 1, title: '调研方案与对象' }, researchV3, '', () => {}, {});
  assert.equal(chapter.added.length, 0, '仍添加了章节副标题');
});
test('四章31页，主讲8页，团队和时间位于内容之后', () => {
  assert.equal(researchV3.slides.length, 31);
  assert.equal(researchV3.slides.filter(d => d.main).length, 8);
  assert.deepEqual(researchV3.slides.filter(d => d.kind === 'chapter').map(d => d.number), [1, 2, 3, 4]);
  assert.equal(researchV3.slides[3].kind, 'methods');
  assert.equal(researchV3.slides[28].title, '团队分工与两组研究路线');
  assert.equal(researchV3.slides[29].title, '调研时间规划');
});
test('问卷范围先于结果，计数与选择范围正确', () => {
  assert.equal(researchV3.slides[23].title, '问卷样本与调查范围');
  assert.equal(researchV3.slides.filter(d => d.kind.startsWith('survey')).length, 4);
  assert.deepEqual(surveyData.difficulties.counts, [45, 45, 44, 44]);
  assert.equal(surveyData.resources.counts.reduce((a, b) => a + b), 67);
  assert.equal(surveyData.experience.counts.reduce((a, b) => a + b), 67);
  assert.equal(((25 + 24) / 67 * 100).toFixed(2), '73.13');
});
test('八个平台与华为必查能力完整，标题使用业务主题', () => {
  const copy = JSON.stringify(researchV3);
  for (const term of ['ModelArts', 'PAI', 'TI-ONE', 'SageMaker', 'Azure ML', 'Crater', 'Kubeflow', 'PyTorch', 'MindSpore', 'checkpoint', 'KooCLI', 'UUID']) assert.ok(copy.includes(term), term);
  assert.equal(researchV3.slides.filter(d => d.asset?.startsWith('bml')).length, 4);
  assert.equal(researchV3.slides.filter(d => d.asset?.startsWith('modelarts')).length, 2);
  for (const d of researchV3.slides) assert.ok(!/BML|ModelArts|PAI|TI-ONE|SageMaker|Azure/.test(d.title), d.title);
});
test('讲解保持直接陈述，没有灰色导语、脚注和反驳式总结', () => {
  for (const d of researchV3.slides) {
    assert.equal(d.caption, undefined); assert.equal(d.topics, undefined);
    const { asset, crop, ...body } = d;
    for (const term of ['而是', '不是', '不能', '不要', '不等于', '截图来源', '原始像素', '本页结论', '原调研计划']) assert.ok(!JSON.stringify(body).includes(term), `${d.title}: ${term}`);
  }
});
test('表格列与裁切参数完整', () => {
  for (const d of researchV3.slides) {
    if (d.kind === 'table') {
      assert.equal(d.headers.length, d.widths.length);
      assert.ok(Math.abs(d.widths.reduce((a, b) => a + b) - 1) < 0.001);
      for (const row of d.rows) assert.equal(row.length, d.headers.length);
    }
    if (d.crop) assert.deepEqual(Object.keys(d.crop).sort(), ['bottom', 'left', 'right', 'top']);
  }
});
test('全页容量、图片和新增问卷讲解通过检查', async () => {
  const assetPath = file => path.join(file.startsWith('modelarts/') ? 'D:/model-training-demo/research-ppt-update-20261012/assets' : 'D:/model-training-demo/style-samples-20261011/assets', file);
  for (const d of researchV3.slides.filter(s => s.kind !== 'methods')) {
    const slide = fakeSlide();
    await layoutResearch(slide, d, researchV3, assetPath, () => {}, {});
    assert.equal(slide.speakerNotes.text, '');
    for (const s of slide.added) assert.notEqual(s.text.style.color, '#536777', d.title);
  }
});
test('原方法页直接复制，不改文字、位置、字体和版式', async () => {
  const slide = fakeSlide();
  const before = JSON.stringify(slide.shapes.items);
  const page = researchV3.slides[3];
  assert.equal(page.copyOriginal, true);
  await layoutResearch(slide, page, researchV3, '', () => {}, {});
  assert.equal(JSON.stringify(slide.shapes.items), before);
  assert.equal(slide.added.length, 0);
  assert.equal(slide.hidden, false);
  assert.equal(slide.speakerNotes.text, '');
});
