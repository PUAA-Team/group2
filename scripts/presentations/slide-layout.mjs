export const FONT = '微软雅黑';
// 固定展示数据精度，避免循环小数超过 Excel 的有效数字限制。
export const surveyRatio = count => Number((count / 67).toFixed(6));
const BLUE = '#1063A8';
const INK = '#172A3B';
const MUTED = '#536777';

export function text(slide, value, x, y, w, h, size = 22, options = {}) {
  const sh = slide.shapes.add({
    geometry: 'textbox', name: options.name || value.slice(0, 35),
    position: { left: x, top: y, width: w, height: h },
    fill: options.fill || 'none', line: { fill: 'none', width: 0 },
  });
  sh.text = value;
  sh.text.style = {
    typeface: FONT, fontSize: size, color: options.color || INK,
    bold: options.bold || false, alignment: options.align || 'left',
    verticalAlignment: 'top', autoFit: 'none', wrap: options.wrap || 'square', insets: 0,
  };
  return sh;
}

export async function prepareBody(presentation, slide, definition, deck, index) {
  // 复用模板背景、校徽、浅色内容区和蓝色折角，只替换正文和标题。
  const byName = Object.fromEntries(slide.shapes.items.map(sh => [sh.name.replace(/\s/g, ''), sh]));
  const inspected = await presentation.inspect({ select: `$.slides[${index}]`, include: ['elements.id', 'elements.name'] });
  const anchors = JSON.parse(inspected.ndjson.trim()).elements;
  presentation.delete(['矩形23', '任意多边形11', '任意多边形13']
    .map(name => anchors.find(el => el.name.replace(/\s/g, '') === name)?.id).filter(Boolean));
  const panel = byName['矩形6'];
  panel.position = { left: 100, top: 114, width: 1080, height: 574 };
  panel.fill = '#FAFBFC';
  const fold = byName['任意多边形16'];
  fold.position = { left: 1096, top: 114, width: 84, height: 82 };
  const corner = byName['矩形12'];
  corner.position = { left: 1120, top: 131, width: 52, height: 38, rotation: 45 };
  corner.text = deck.key === 'research' ? '调研' : '分析';
  corner.text.style = { typeface: FONT, fontSize: 20, color: '#FFFFFF', bold: true, insets: 0, autoFit: 'none' };
  const heading = byName['标题1'];
  heading.position = { left: 134, top: 139, width: 936, height: 49 };
  heading.fill = 'none';
  heading.line = { fill: 'none', width: 0 };
  heading.text = definition.title;
  heading.text.style = { typeface: FONT, fontSize: 31, color: BLUE, bold: true, alignment: 'left', insets: 0, autoFit: 'none', wrap: 'none' };
  text(slide, definition.subtitle || '', 136, 198, 978, 30, 19, { color: MUTED, name: '页内导语' });
  text(slide, definition.conclusion || '', 136, 620, 1000, 43, 19, { bold: true, color: BLUE, name: '本页结论' });
  text(slide, `${deck.label}  ·  ${String(index + 1).padStart(2, '0')} / ${deck.slides.length}${index >= deck.mainCount ? '  ·  备查' : ''}`,
    850, 671, 294, 17, 13, { color: MUTED, align: 'right', name: '页码' });
  if (definition.kind === 'charts' || definition.kind === 'chartAside') {
    text(slide, '来源：67 份问卷原始统计；图表括号为人数。', 136, 671, 690, 17, 13, { color: MUTED });
  }
  slide.hidden = index >= deck.mainCount;
  slide.speakerNotes.text = `页面：${definition.title}\n${index >= deck.mainCount ? '备查页，默认隐藏；需要时取消隐藏。' : '课堂主讲页。'}\n\n来源与核对：\n${definition.source || ''}\n\n${definition.kind === 'diagram' ? '本页插图框有意保留，须以正式 CodeArts 模型替换。不能声称模型已完成。\n' : ''}${definition.conclusion || ''}`;
}

const unitWidth = value => [...value].reduce((sum, c) => sum + (/[^\u0000-\u007f]/.test(c) ? 1.05 : 0.64), 0);
export function wrapTableCell(value, width, font) {
  const limit = (width - 22) / font;
  return String(value).split('\n').map(paragraph => {
    const tokens = paragraph.match(/\d+(?:\.\d+)?\s+(?:ms|s|GB|MB|GiB|MiB)\b|[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*(?:%)?|./gu) || [];
    let line = [], used = 0;
    const lines = [];
    for (const token of tokens) {
      const units = unitWidth(token);
      if (used + units > limit && line.length) {
        if (/^[、，。；：！？）】》]$/.test(token) && line.length > 1) {
          const previous = line.pop();
          lines.push(line); line = [previous]; used = unitWidth(previous);
        } else { lines.push(line); line = []; used = 0; }
      }
      line.push(token); used += units;
    }
    lines.push(line);
    if (lines.length > 1 && unitWidth(lines.at(-1).join('')) < 3) {
      const previous = lines.at(-2), last = lines.at(-1);
      while (previous.length > 1 && unitWidth(last.join('')) < 3) last.unshift(previous.pop());
    }
    return lines.map(tokens => tokens.join('')).join('\n');
  }).join('\n');
}

export function addTable(slide, definition, record) {
  const x = 136, y = 234, w = 1000, available = 378;
  const sourceValues = [definition.headers, ...definition.rows];
  const widths = (definition.widths || definition.headers.map(() => 1 / definition.headers.length)).map(fr => fr * w);
  let font = definition.font || 21;
  let heights, values;
  do {
    values = sourceValues.map(row => row.map((v, c) => wrapTableCell(v, widths[c], font)));
    heights = values.map(row => Math.max(...row.map(v => v.split('\n').length)) * font * 1.27 + 10);
    if (heights.reduce((a, b) => a + b, 0) <= available || font <= 17) break;
    font -= 0.5;
  } while (true);
  const h = heights.reduce((a, b) => a + b, 0);
  if (h > available) throw new Error(`表格内容超过可用高度：${definition.title} (${h})`);
  const tb = slide.tables.add({ rows: values.length, columns: values[0].length,
    left: x, top: y, width: w, height: h, values, columnWidths: widths });
  tb.styleOptions = { headerRow: true, bandedRows: false };
  tb.borders.assign({ fill: '#D4DFE7', style: 'solid', width: 0.65 });
  for (let r = 0; r < values.length; r++) {
    tb.rows[r].height = heights[r];
    for (let c = 0; c < values[0].length; c++) {
      const cell = tb.getCell(r, c);
      cell.fill = r === 0 ? BLUE : r % 2 ? '#FFFFFF' : '#F0F5F8';
      cell.text.style = { typeface: FONT, fontSize: font, color: r === 0 ? '#FFFFFF' : INK, bold: r === 0 || c === 0, autoFit: 'none', wrap: 'none', insets: 0 };
    }
  }
  tb.cells.block({ row: 0, column: 0, rowCount: values.length, columnCount: values[0].length })
    .assign({ margins: { left: 10, right: 10, top: 5, bottom: 5 } });
  record.table = { font, height: h, rowHeights: heights };
}

function section(slide, item, x, y, w, h, font = 23) {
  text(slide, item.heading, x, y, w, 35, font + 1, { bold: true, color: BLUE });
  text(slide, wrapTableCell(item.text, w + 22, font), x, y + 38, w, h - 38, font, { wrap: 'none' });
}

export function addColumns(slide, definition) {
  definition.columns.forEach((item, i) => section(slide, item, 142 + 520 * i, 244, 470, 350, 23));
}

export function addDiagram(slide, definition) {
  const frame = slide.shapes.add({ geometry: 'rect', name: 'CodeArts 插图位置（待替换）',
    position: { left: 136, top: 238, width: 580, height: 354 },
    fill: '#F0F5F8', line: { fill: '#718DA3', width: 1.4, style: 'dashed' } });
  frame.text = definition.frame;
  frame.text.style = { typeface: FONT, fontSize: 22, color: MUTED, alignment: 'center', verticalAlignment: 'middle', insets: 22, autoFit: 'none' };
  definition.sections.forEach((item, i) => section(slide, item, 744, 239 + i * 118, 390, 118, 20));
}

export function surveyAxes(font) {
  return {
    xAxis: { textStyle: { fontSize: font, fill: INK }, line: { fill: 'none', width: 0 }, majorGridlines: null },
    yAxis: { min: 0, max: 1, majorUnit: 0.25, numberFormatCode: '0%', textStyle: { fontSize: 16, fill: MUTED }, majorGridlines: { fill: '#DCE5EB', width: 0.6 }, line: { fill: '#A2B3C0', width: 0.6 } },
  };
}
export function addCharts(slide, definition, applyChartFont) {
  const make = (data, pos, font = 19) => {
    const categories = data.labels.map((label, i) => `${label}（${data.counts[i]}人）`).reverse();
    const chart = slide.charts.add('bar', {
      position: pos, title: data.title, titlePlacement: 'aboveChart',
      titleTextStyle: { fontSize: 22, fill: BLUE, bold: true },
      categories, series: [{ name: '占 67 份有效问卷的比例', values: data.counts.map(surveyRatio).reverse(), fill: BLUE, valuesFormatCode: '0.00%' }],
      hasLegend: false, barOptions: { direction: 'bar', grouping: 'clustered', gapWidth: 80 },
      ...surveyAxes(font),
      dataLabels: { showValue: true, position: 'outEnd', numberFormatCode: '0.00%', numberFormatSourceLinked: false, textStyle: { fontSize: font - 1, fill: INK } },
      chartFill: '#FAFBFC', plotAreaFill: '#FAFBFC', chartLine: { fill: 'none', width: 0 }, plotAreaLine: { fill: 'none', width: 0 },
    });
    applyChartFont(chart, { fontFamily: FONT });
  };
  if (definition.kind === 'charts') {
    definition.charts.forEach((data, i) => make(data, { left: 131 + 510 * i, top: 239, width: 495, height: 350 }, 18));
  } else {
    make(definition.chart, { left: 132, top: 237, width: 637, height: 355 }, 20);
    definition.aside.forEach((item, i) => section(slide, item, 797, 253 + 165 * i, 338, 160, 20));
  }
}

export function editCover(slide, definition, deck) {
  const title = slide.shapes.items.find(sh => sh.name.replace(/\s/g, '') === '文本框27');
  title.position = { left: 149, top: 421, width: 1020, height: 129 };
  title.text = `${definition.subtitle}\n${definition.title}`;
  title.text.style = { typeface: FONT, fontSize: 46, color: '#FFFFFF', bold: true, insets: 0, autoFit: 'none' };
  const meta = slide.shapes.items.find(sh => sh.name.replace(/\s/g, '') === '文本框28');
  meta.position = { left: 564, top: 576, width: 680, height: 111 };
  meta.text = '《软件系统分析与设计》\n五组：王者灵宝的 coding 能力也不是不行\n2026.10  ·  成员与分工见可填写页';
  meta.text.style = { typeface: FONT, fontSize: 23, color: '#FFFFFF', alignment: 'right', insets: 0, autoFit: 'none' };
  slide.speakerNotes.text = `${deck.label}，${deck.mainCount} 页主讲；其余为默认隐藏的备查页。\n沿用原 PPT 封面、北航标识与背景，原文件未覆盖。\n${definition.source}`;
}
