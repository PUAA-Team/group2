import fs from 'node:fs/promises';
import path from 'node:path';
import { layoutSlide } from './defense-v2-layout.mjs';
import { FONT, text, wrapTableCell, surveyRatio, surveyAxes } from './slide-layout.mjs';

const BLUE = '#1063A8', INK = '#172A3B';

function paragraph(slide, item, x, y, w, h, size = 21) {
  text(slide, item.heading, x, y, w, 31, size + 2, { color: BLUE, bold: true });
  const copy = wrapTableCell(item.text, w + 22, size);
  if (copy.split('\n').length * size * 1.3 > h - 42) throw new Error(`问卷说明过长：${item.heading}`);
  text(slide, copy, x, y + 42, w, h - 42, size, { wrap: 'none' });
}

function chart(slide, data, pos, chartFont) {
  const axes = surveyAxes(18);
  axes.xAxis.textStyle.fill = INK; axes.yAxis.textStyle.fill = INK;
  const ch = slide.charts.add('bar', {
    position: pos, title: data.title, titlePlacement: 'aboveChart',
    titleTextStyle: { fontSize: 22, fill: BLUE, bold: true },
    categories: data.labels.map((label, i) => `${label}（${data.counts[i]}人）`).reverse(),
    series: [{ name: '占67份问卷的比例', values: data.counts.map(surveyRatio).reverse(), fill: BLUE, valuesFormatCode: '0.00%' }],
    hasLegend: false, barOptions: { direction: 'bar', grouping: 'clustered', gapWidth: 110 }, ...axes,
    dataLabels: { showValue: true, position: 'outEnd', numberFormatCode: '0.00%', numberFormatSourceLinked: false, textStyle: { fontSize: 18, fill: INK } },
    chartFill: '#FAFBFC', plotAreaFill: '#FAFBFC', chartLine: { fill: 'none', width: 0 }, plotAreaLine: { fill: 'none', width: 0 },
  });
  chartFont(ch, { fontFamily: FONT });
}

export async function layoutResearch(slide, d, deck, assetPath, chartFont, record) {
  if (d.kind === 'methods') {
    // 原模板第 3 页直接复用，保持原文字、字体、位置和四栏排版。
    slide.hidden = !d.main; slide.speakerNotes.text = ''; return;
  }
  if (d.kind === 'surveyAside' || d.kind === 'surveyEvidence') {
    await layoutSlide(slide, { ...d, kind: 'story', sections: [] }, deck, assetPath, chartFont, record);
    if (d.kind === 'surveyAside') {
      chart(slide, d.chart, { left: 132, top: 225, width: 635, height: 402 }, chartFont);
      d.sections.forEach((s, i) => paragraph(slide, s, 810, 232 + i * 137, 326, 137, 20));
    } else {
      text(slide, '问卷原始统计', 136, 237, 448, 28, 22, { bold: true, color: BLUE });
      slide.images.add({ blob: new Uint8Array(await fs.readFile(assetPath(d.asset))), contentType: 'image/png', alt: 'Q5原始统计报告',
        fit: 'contain', position: { left: 136, top: 284, width: 448, height: 248 }, crop: d.crop });
      chart(slide, d.chart, { left: 608, top: 225, width: 528, height: 352 }, chartFont);
      text(slide, d.insight, 136, 606, 1000, 63, 21);
    }
    return;
  }
  // 原排版将图片目录作为参数，这里只为图片页转为具体所在目录。
  if (d.kind === 'image') {
    const resolved = assetPath(d.asset);
    await layoutSlide(slide, { ...d, asset: path.basename(resolved) }, deck, path.dirname(resolved), chartFont, record);
  } else await layoutSlide(slide, d, deck, '', chartFont, record);
}
