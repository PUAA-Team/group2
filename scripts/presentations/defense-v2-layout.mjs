import fs from 'node:fs/promises';
import path from 'node:path';
import { FONT, text, wrapTableCell, surveyRatio, surveyAxes } from './slide-layout.mjs';

const BLUE = '#1063A8', INK = '#172A3B', MUTED = '#536777';
const names = slide => Object.fromEntries(slide.shapes.items.map(s => [s.name.replace(/\s/g, ''), s]));

export async function cleanBody(p, slide, index) {
  const items = JSON.parse((await p.inspect({ select: `$.slides[${index}]`, include: ['elements.id', 'elements.name'] })).ndjson.trim()).elements;
  p.delete(['矩形23', '任意多边形11', '任意多边形13'].map(name => items.find(el => el.name.replace(/\s/g, '') === name)?.id).filter(Boolean));
}

function heading(slide, d, deck) {
  const sh = names(slide);
  sh['矩形6'].position = { left: 100, top: 114, width: 1080, height: 574 };
  sh['矩形6'].fill = '#FAFBFC';
  sh['任意多边形16'].position = { left: 1096, top: 114, width: 84, height: 82 };
  sh['矩形12'].position = { left: 1120, top: 131, width: 52, height: 38, rotation: 45 };
  sh['矩形12'].text = deck.key === 'research' ? '调研' : '分析';
  sh['矩形12'].text.style = { typeface: FONT, fontSize: 20, color: '#FFFFFF', bold: true, insets: 0, autoFit: 'none' };
  const title = sh['标题1'];
  title.position = { left: 136, top: 143, width: 936, height: 46 };
  title.fill = 'none'; title.line = { fill: 'none', width: 0 }; title.text = d.title;
  title.text.style = { typeface: FONT, fontSize: 29, color: BLUE, bold: true, insets: 0, autoFit: 'none', wrap: 'none' };
  if (d.kind !== 'contents' && !deck.cleanText) text(slide, `${String(d.chapter).padStart(2, '0')}  ${deck.chapters[d.chapter - 1]}`, 136, 203, 1000, 26, 17, { color: MUTED });
}

function section(slide, item, x, y, w, h, font = 21) {
  text(slide, item.heading, x, y, w, 32, font + 2, { bold: true, color: BLUE });
  const copy = wrapTableCell(item.text.replaceAll('；', '。'), w + 22, font);
  const lines = copy.split('\n').length;
  if (lines * font * 1.3 > h - 40) throw new Error(`文字超出区块：${item.heading} ${lines}行/${h}`);
  text(slide, copy, x, y + 39, w, h - 39, font, { wrap: 'none' });
}

function addTable(slide, d, record) {
  const w = 1000, widths = d.widths.map(fr => fr * w);
  const top = d.caption ? 263 : 244, available = 662 - top;
  let font = d.font || 20, values, heights;
  do {
    values = [d.headers, ...d.rows].map(row => row.map((v, c) => wrapTableCell(v.replaceAll('；', '。'), widths[c], font)));
    heights = values.map(row => Math.max(...row.map(v => v.split('\n').length)) * font * 1.27 + 12);
    if (heights.reduce((a, b) => a + b) <= available || font <= 18) break;
    font -= 0.5;
  } while (true);
  const height = heights.reduce((a, b) => a + b);
  if (height > available) throw new Error(`表格过长：${d.title} (${height}/${available})`);
  const tb = slide.tables.add({ rows: values.length, columns: values[0].length, left: 136, top, width: w, height, values, columnWidths: widths });
  tb.styleOptions = { headerRow: true, bandedRows: false };
  tb.borders.assign({ fill: '#D4DFE7', style: 'solid', width: 0.65 });
  for (let r = 0; r < values.length; r++) {
    tb.rows[r].height = heights[r];
    for (let c = 0; c < widths.length; c++) {
      const cell = tb.getCell(r, c);
      cell.fill = r === 0 ? BLUE : r % 2 ? '#FFFFFF' : '#F0F5F8';
      cell.text.style = { typeface: FONT, fontSize: font, color: r === 0 ? '#FFFFFF' : INK, bold: r === 0 || c === 0, wrap: 'none', insets: 0, autoFit: 'none' };
    }
  }
  tb.cells.block({ row: 0, column: 0, rowCount: values.length, columnCount: widths.length }).assign({ margins: { left: 10, right: 10, top: 6, bottom: 6 } });
  record.table = { font, height, rowHeights: heights };
}

async function addImage(slide, assets, file, alt, position, crop) {
  slide.images.add({ blob: new Uint8Array(await fs.readFile(path.join(assets, file))), contentType: 'image/png', fit: 'contain', alt, position, crop });
}

function addChart(slide, data, pos, font, applyChartFont, withTitle = true) {
  const chart = slide.charts.add('bar', {
    position: pos, ...(withTitle ? { title: data.title, titlePlacement: 'aboveChart', titleTextStyle: { fontSize: 21, fill: BLUE, bold: true } } : {}),
    categories: data.labels.map((label, i) => `${label}（${data.counts[i]}人）`).reverse(),
    series: [{ name: '占67份问卷的比例', values: data.counts.map(surveyRatio).reverse(), fill: BLUE, valuesFormatCode: '0.00%' }],
    hasLegend: false, barOptions: { direction: 'bar', grouping: 'clustered', gapWidth: 80 }, ...surveyAxes(font),
    dataLabels: { showValue: true, position: 'outEnd', numberFormatCode: '0.00%', numberFormatSourceLinked: false, textStyle: { fontSize: font - 1, fill: INK } },
    chartFill: '#FAFBFC', plotAreaFill: '#FAFBFC', chartLine: { fill: 'none', width: 0 }, plotAreaLine: { fill: 'none', width: 0 },
  });
  applyChartFont(chart, { fontFamily: FONT });
}

function addFrame(slide, d) {
  const full = ['activity', 'class', 'sequence'].includes(d.layout);
  const box = slide.shapes.add({ geometry: 'rect', name: d.frameTitle,
    position: { left: 136, top: 246, width: full ? 1000 : 620, height: full ? 269 : 384 },
    fill: '#F0F5F8', line: { fill: '#718DA3', width: 1.2, style: 'dashed' } });
  box.text = d.frameTitle;
  box.text.style = { typeface: FONT, fontSize: 25, color: MUTED, alignment: 'center', verticalAlignment: 'middle', insets: 0, autoFit: 'none' };
  if (full) {
    d.sections.forEach((s, i) => section(slide, s, 136 + (d.sections.length > 1 ? i * 510 : 0), 537,
      d.sections.length > 1 ? 480 : 1000, 123, 20));
  } else d.sections.forEach((s, i) => section(slide, s, 792, 247 + i * 137, 344, 137, 19));
}

export async function layoutSlide(slide, d, deck, assets, applyChartFont, record) {
  slide.hidden = !d.main;
  slide.speakerNotes.text = '';
  if (d.kind === 'cover') {
    const sh = names(slide);
    sh['文本框27'].text = `大模型集成训练平台\n${d.title}`;
    sh['文本框27'].text.style = { typeface: FONT, fontSize: 46, bold: true, color: '#FFFFFF', insets: 0, autoFit: 'none' };
    sh['文本框28'].text = '《软件系统分析与设计》\n五组：王者灵宝的 coding 能力也不是不行\n成员及分工：____________    2026.10';
    sh['文本框28'].text.style = { typeface: FONT, fontSize: 22, color: '#FFFFFF', alignment: 'right', insets: 0, autoFit: 'none' };
    return;
  }
  if (d.kind === 'chapter') {
    const sh = names(slide);
    sh['矩形11'].text = String(d.number).padStart(2, '0');
    sh['矩形6'].text = d.title;
    sh['矩形6'].position = { left: 468, top: 318, width: 720, height: 72 };
    if (!deck.cleanText) text(slide, d.topics, 470, 423, 710, 68, 20, { color: '#FFFFFF' });
    return;
  }
  heading(slide, d, deck);
  if (d.caption) text(slide, d.caption.replaceAll('；', '。'), 136, 232, 1000, 28, 17, { color: MUTED });
  if (d.kind === 'contents') {
    deck.chapters.forEach((title, i) => {
      text(slide, String(i + 1).padStart(2, '0'), 160, 258 + 93 * i, 85, 47, 32, { color: BLUE });
      text(slide, title, 277, 262 + 93 * i, 775, 47, 30, { bold: true });
    });
  } else if (d.kind === 'table') addTable(slide, d, record);
  else if (d.kind === 'story') {
    const start = d.caption ? 278 : 251;
    d.sections.forEach((s, i) => section(slide, s, i % 2 ? 666 : 136, start + Math.floor(i / 2) * 203, 470, 193, 21));
  } else if (d.kind === 'image') {
    let pos, x, y, w, step;
    if (d.imageLayout === 'portrait') {
      pos = { left: 136, top: 242, width: 570, height: 395 }; x = 750; y = 248; w = 386; step = 137;
    } else if (d.imageLayout === 'config') {
      pos = { left: 136, top: 256, width: 635, height: 290 }; x = 809; y = 245; w = 327; step = 111;
    } else {
      pos = { left: 136, top: 246, width: 685, height: 379 }; x = 850; y = 248; w = 286; step = 140;
    }
    await addImage(slide, assets, d.asset, d.title, pos, d.crop);
    d.sections.forEach((s, i) => section(slide, s, x, y + i * step, w, step, d.imageLayout === 'config' ? 18 : 19));
    if (d.bottom) text(slide, d.bottom.replaceAll('；', '。'), 136, 623, 1000, 35, 20);
  } else if (d.kind === 'scenario') {
    text(slide, d.config, 136, 263, 490, 325, 25);
    d.sections.forEach((s, i) => section(slide, s, 684, 248 + i * 137, 452, 137, 20));
  } else if (d.kind === 'survey') {
    text(slide, 'Q5 训练中容易遇到的问题  ·  多选题  ·  有效样本 67 份', 136, 233, 1000, 27, 18, { color: MUTED });
    text(slide, '原始统计报告', 136, 273, 448, 27, 19, { bold: true });
    await addImage(slide, assets, d.asset, '问卷第5题完整统计', { left: 136, top: 307, width: 448, height: 245 }, d.crop);
    addChart(slide, d.chart, { left: 602, top: 265, width: 538, height: 321 }, 17, applyChartFont, false);
    text(slide, '资源入口显示可用 GPU 与授权范围，保留自动和手动选择。\n任务详情分别展示日志、训练参数和实时进度。', 136, 610, 1000, 57, 21);
  } else if (d.kind === 'charts') {
    d.charts.forEach((data, i) => addChart(slide, data, { left: 136 + i * 510, top: 256, width: 495, height: 360 }, 17, applyChartFont));
    text(slide, '有效样本 67 份；括号为选择人数。', 136, 638, 1000, 24, 17, { color: MUTED });
  } else if (d.kind === 'frame') addFrame(slide, d);
  else throw new Error(`未支持的版式：${d.kind}`);
}
