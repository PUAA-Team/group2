import fs from 'node:fs/promises';
import path from 'node:path';
import { FONT, text, wrapTableCell } from './slide-layout.mjs';

const BLUE = '#1063A8', INK = '#172A3B', LINE = '#617B8F', PAPER = '#FAFBFC';
const normalized = sh => sh.name.replace(/\s/g, '');

export async function cleanModelingBody(p, slide, index) {
  const furniture = new Set(['矩形32', '椭圆19', '椭圆21', '椭圆22', '矩形6', '任意多边形16', '矩形12', '标题1']);
  const info = (await p.inspect({ select: `$.slides[${index}].elements[*]`, include: ['id', 'kind', 'name'] })).records;
  p.delete(info.filter(el => el.kind !== 'image' && !furniture.has(el.name.replace(/\s/g, ''))).map(el => el.id));
}

function node(s, label, x, y, w, h, geometry = 'roundRect', fill = '#FFFFFF', size = 21) {
  const sh = s.shapes.add({ geometry, name: label || '模型节点', position: { left: x, top: y, width: w, height: h },
    fill, line: { fill: LINE, width: 1.25 }, ...(geometry === 'roundRect' ? { borderRadius: 9 } : {}) });
  sh.text = label;
  sh.text.style = { typeface: FONT, fontSize: size, color: INK, alignment: 'center', verticalAlignment: 'middle',
    autoFit: 'none', wrap: 'none', insets: 3 };
  return sh;
}
function edge(s, a, b, options = {}) {
  const sh = s.shapes.connect(a, b, { kind: 'straight', line: { fill: LINE, width: 1.4 },
    ...(options.association ? {} : { tail: { type: 'arrow', width: 'sm', length: 'sm' } }), ...options });
  sh.bringToFront();
  return sh;
}
function label(s, value, x, y, w, h = 28, size = 20) {
  return text(s, value, x, y, w, h, size, { color: INK, fill: PAPER });
}
function line(s, x, y, w, h, color = LINE) {
  return s.shapes.add({ geometry: 'line', name: '模型连线', position: { left: x, top: y, width: w, height: h },
    fill: 'none', line: { fill: color, width: 1.4 } });
}
function finalNode(s, x, y) {
  const outer = node(s, '', x, y, 18, 18, 'ellipse', 'none');
  node(s, '', x + 4, y + 4, 10, 10, 'ellipse', INK);
  return outer;
}
function actor(s, value, x, y) {
  const head = node(s, '', x + 30, y, 22, 22, 'ellipse', PAPER);
  line(s, x + 41, y + 22, 0, 42); line(s, x + 17, y + 37, 48, 0);
  const leg = line(s, x + 15, y + 40, 26, 24);
  leg.position = { left: x + 15, top: y + 40, width: 26, height: 24, verticalFlip: true };
  line(s, x + 41, y + 40, 26, 24);
  text(s, value, x - 15, y + 72, 120, 31, 22, { bold: true, align: 'center' });
  return head;
}

export function nativeTable(s, d, top, available = 390, size = 20) {
  const values = [d.headers, ...d.rows].map(row => row.map((v, c) => wrapTableCell(v, d.widths[c], size)));
  const heights = values.map((row, r) => Math.max(...row.map(v => v.split('\n').length)) * size * 1.29 + (r ? 15 : 18));
  const height = heights.reduce((a, b) => a + b, 0);
  if (height > available) throw new Error(`表格超出设计高度 ${d.title}: ${height}/${available}`);
  const table = s.tables.add({ rows: values.length, columns: values[0].length,
    left: 136, top, width: 1000, height, values, columnWidths: d.widths });
  table.styleOptions = { headerRow: true, bandedRows: false };
  table.borders.assign({ fill: '#D6E0E7', width: 0.65, style: 'solid' });
  heights.forEach((h, r) => {
    table.rows[r].height = h;
    values[r].forEach((_, c) => {
      const cell = table.getCell(r, c);
      cell.fill = r === 0 ? BLUE : r % 2 ? '#FFFFFF' : '#F1F5F8';
      cell.text.style = { typeface: FONT, fontSize: size, color: r === 0 ? '#FFFFFF' : INK, bold: r === 0 || c === 0,
        autoFit: 'none', wrap: 'none', insets: 0 };
    });
  });
  table.cells.block({ row: 0, column: 0, rowCount: values.length, columnCount: values[0].length })
    .assign({ margins: { left: 10, right: 10, top: 7, bottom: 7 } });
  return { height, rowHeights: heights, size };
}

function usecase(s) {
  node(s, '', 310, 231, 664, 421, 'rect', PAPER);
  text(s, '大模型集成训练平台', 465, 239, 350, 29, 22, { color: BLUE, bold: true, align: 'center' });
  const user = actor(s, '普通用户', 160, 395), admin = actor(s, '管理员', 1040, 395);
  const auth = node(s, '登录认证', 535, 282, 220, 58, 'ellipse');
  const users = ['管理数据集', '提交训练任务', '查看任务与实时监控', '发布推理服务']
    .map((v, i) => node(s, v, 346, 358 + 72 * i, 262, 55, 'ellipse', '#ECF3F9', 21));
  const admins = ['资源池与配额管理', '用户组与个人授权', '系统管理与审计']
    .map((v, i) => node(s, v, 677, 376 + 92 * i, 265, 57, 'ellipse', '#ECF3F9', 21));
  edge(s, user, auth, { association: true, fromSide: 'right', toSide: 'left' });
  edge(s, admin, auth, { association: true, fromSide: 'left', toSide: 'right' });
  users.forEach(sh => edge(s, user, sh, { association: true, fromSide: 'right', toSide: 'left' }));
  admins.forEach(sh => edge(s, admin, sh, { association: true, fromSide: 'left', toSide: 'right' }));
  [...users, ...admins, auth].forEach(sh => sh.bringToFront());
}

function activity(s) {
  const lanes = [[136, 270, '用户与任务受理'], [406, 305, '资源调度'], [711, 425, '训练执行与监控']];
  lanes.forEach(([x, w, name]) => {
    node(s, '', x, 233, w, 420, 'rect', PAPER);
    text(s, name, x + 10, 242, w - 20, 29, 21, { color: BLUE, bold: true, align: 'center' });
    line(s, x, 278, w, 0, '#D6E0E7');
  });
  const start = node(s, '', 150, 309, 13, 13, 'ellipse', INK);
  const submit = node(s, '配置并提交', 188, 294, 176, 47);
  const check = node(s, '身份、资产、参数校验', 160, 368, 224, 51, 'roundRect', '#ECF3F9', 19);
  const valid = node(s, '', 246, 452, 47, 47, 'diamond');
  const reject = node(s, '返回错误', 145, 546, 107, 48, 'roundRect', '#FFFFFF', 19);
  const snapshot = node(s, '保存快照\n返回任务 ID', 284, 541, 108, 58, 'roundRect', '#FFFFFF', 18);
  const queue = node(s, '排队等待', 436, 540, 250, 53);
  const ready = node(s, '', 537, 420, 48, 48, 'diamond');
  const allocate = node(s, '重查授权并预留资源', 433, 300, 254, 51, 'roundRect', '#ECF3F9', 19);
  const begin = node(s, '准备环境并启动', 817, 300, 230, 51);
  const fork = node(s, '', 771, 398, 336, 5, 'rect', INK);
  const train = node(s, '执行训练', 751, 444, 147, 50);
  const monitor = node(s, '采集指标与日志', 935, 444, 183, 50, 'roundRect', '#ECF3F9', 19);
  const join = node(s, '', 771, 533, 336, 5, 'rect', INK);
  const cleanup = node(s, '记录结果、归档与清理', 781, 570, 326, 49, 'roundRect', '#FFFFFF', 20);
  const end = finalNode(s, 923, 633);
  const rejectedEnd = finalNode(s, 190, 607);
  edge(s, start, submit, { fromSide: 'right', toSide: 'left' });
  edge(s, submit, check, { fromSide: 'bottom', toSide: 'top' });
  edge(s, check, valid, { fromSide: 'bottom', toSide: 'top' });
  edge(s, valid, reject, { fromSide: 'left', toSide: 'top', kind: 'elbow' });
  edge(s, valid, snapshot, { fromSide: 'right', toSide: 'top', kind: 'elbow' });
  edge(s, snapshot, queue, { fromSide: 'right', toSide: 'left' });
  edge(s, reject, rejectedEnd, { fromSide: 'bottom', toSide: 'top' });
  edge(s, queue, ready, { fromSide: 'top', toSide: 'bottom' });
  edge(s, ready, queue, { fromSide: 'right', toSide: 'right', kind: 'elbow' });
  edge(s, ready, allocate, { fromSide: 'top', toSide: 'bottom' });
  edge(s, allocate, begin, { fromSide: 'right', toSide: 'left' });
  edge(s, begin, fork, { fromSide: 'bottom', toSide: 'top' });
  edge(s, fork, train, { fromSide: 'left', toSide: 'top', kind: 'elbow' });
  edge(s, fork, monitor, { fromSide: 'right', toSide: 'top', kind: 'elbow' });
  edge(s, train, join, { fromSide: 'bottom', toSide: 'left', kind: 'elbow' });
  edge(s, monitor, join, { fromSide: 'bottom', toSide: 'right', kind: 'elbow' });
  edge(s, join, cleanup, { fromSide: 'bottom', toSide: 'top' });
  edge(s, cleanup, end, { fromSide: 'bottom', toSide: 'top' });
  label(s, '[拒绝]', 151, 486, 82, 26, 18); label(s, '[通过]', 302, 486, 90, 26, 18);
  label(s, '[满足资源条件]', 445, 372, 185, 26, 18); label(s, '[暂忙]', 618, 477, 70, 26, 18);
  text(s, '失败、停止均核对进程退出与资源清理', 143, 623, 545, 27, 20, { color: BLUE });
  [submit, check, valid, reject, snapshot, queue, ready, allocate, begin, fork, train, monitor, join, cleanup, end].forEach(sh => sh.bringToFront());
}

function state(s) {
  const topLabels = ['排队中', '准备中', '运行中', '归档中', '成功'];
  const top = topLabels.map((value, i) => node(s, value, 136 + 202 * i, 278, 170, 63, 'roundRect', i === 4 ? '#ECF3F9' : '#FFFFFF', 23));
  const initial = node(s, '', 110, 303, 11, 11, 'ellipse', INK);
  edge(s, initial, top[0], { fromSide: 'right', toSide: 'left' });
  top.slice(0, -1).forEach((sh, i) => edge(s, sh, top[i + 1], { fromSide: 'right', toSide: 'left' }));
  ['资源预留', '环境就绪', '正常退出', '产物及清理确认'].forEach((v, i) => label(s, v, 145 + 202 * i, 232, i === 3 ? 216 : 178, 29, 19));
  const cancel = node(s, '已取消', 136, 551, 170, 63, 'roundRect', '#ECF3F9', 23);
  const stopping = node(s, '停止中', 339, 416, 170, 63, 'roundRect', '#FFF1DF', 23);
  const stopped = node(s, '已停止', 339, 551, 170, 63, 'roundRect', '#ECF3F9', 23);
  const failed = node(s, '失败', 946, 551, 170, 63, 'roundRect', '#FFF1DF', 23);
  edge(s, top[0], cancel, { fromSide: 'bottom', toSide: 'top' });
  edge(s, top[1], stopping, { fromSide: 'bottom', toSide: 'top' });
  edge(s, top[2], stopping, { fromSide: 'bottom', toSide: 'right', kind: 'elbow' });
  edge(s, stopping, stopped, { fromSide: 'bottom', toSide: 'top' });
  label(s, '授权取消', 158, 426, 122, 30, 20);
  label(s, '授权停止', 351, 363, 129, 29, 20);
  label(s, '停止请求', 530, 401, 140, 29, 20);
  label(s, '退出且清理完成', 351, 503, 224, 29, 19);
  // 异常共用右侧路径，避开停止分支和主状态节点。
  top.slice(1, 4).forEach((sh, i) => {
    const x = sh.position.left + 145;
    line(s, x, 341, 0, 45 + i * 14);
    line(s, x, 386 + i * 14, 1140 - x, 0);
  });
  line(s, 1140, 386, 0, 196);
  const tip = s.shapes.add({ geometry: 'connector', kind: 'straight', name: '异常进入失败',
    position: { left: 1116, top: 582, width: 24, height: 0, horizontalFlip: true },
    line: { fill: LINE, width: 1.4 }, tail: { type: 'arrow', width: 'sm', length: 'sm' } });
  tip.bringToFront();
  label(s, '准备、执行或归档异常', 752, 445, 349, 32, 21);
  text(s, '清理未确认时保持占用并隔离设备\n重跑创建新任务，保留原日志与快照', 647, 491, 460, 59, 20);
  text(s, '任务受理后进入排队。草稿与提交中保留在配置流程。终态保持不变。', 136, 641, 1000, 29, 21, { color: BLUE });
  [...top, cancel, stopping, stopped, failed].forEach(sh => sh.bringToFront());
}

export async function layoutModeling(s, d, assets) {
  s.hidden = Boolean(d.hidden); s.speakerNotes.text = '';
  const byName = Object.fromEntries(s.shapes.items.map(sh => [normalized(sh), sh]));
  if (d.kind === 'chapter') {
    byName['矩形11'].text.set('02');
    byName['矩形6'].position = { left: 468, top: 310, width: 720, height: 80 };
    byName['矩形6'].text.style = { typeface: FONT, fontSize: 54, bold: true, color: '#FFFFFF', insets: 0, autoFit: 'none' };
    byName['矩形6'].text.set(d.title);
    d.topics.forEach((v, i) => text(s, `${i + 1}  ${v}`, 475 + i * 247, 425, 245, 36, 25, { color: '#FFFFFF' }));
    return {};
  }
  const title = byName['标题1'];
  title.position = { left: 136, top: 143, width: 936, height: 46 };
  title.text.style = { typeface: FONT, fontSize: 30, bold: true, color: BLUE, alignment: 'left', insets: 0, wrap: 'none', autoFit: 'none' };
  title.text.set(d.title);
  byName['矩形12'].text.set('');
  const record = {};
  if (d.kind === 'scope') {
    text(s, d.bottom, 136, 207, 1000, 32, 22);
    record.table = nativeTable(s, d, 260, 385, 20);
  } else if (d.kind === 'usecase') usecase(s);
  else if (d.kind === 'spec') {
    text(s, '训练输入：模型、数据与运行时版本，训练方法、参数和资源请求', 136, 201, 1000, 30, 21);
    record.table = nativeTable(s, d, 241, 348, 20);
    text(s, '有效授权 =（组允许 ∪ 个人追加）− 个人禁用', 136, 590, 1000, 34, 25, { color: BLUE, bold: true });
    text(s, '组允许卡 2/3，个人禁用卡 3，最终仅可用卡 2。数量与并发配额各取较小上限。', 136, 636, 1000, 28, 21);
  } else if (d.kind === 'activity') activity(s);
  else if (d.kind === 'state') state(s);
  else if (d.kind === 'nfr') {
    d.metrics.forEach(([value, caption], i) => {
      text(s, value, 143 + 335 * i, 217, 295, 63, 43, { color: BLUE, bold: true });
      text(s, caption, 143 + 335 * i, 283, 305, 29, 21);
    });
    record.table = nativeTable(s, d, 341, 248, 20);
    text(s, wrapTableCell(d.load, 1022, 20), 136, 606, 1000, 64, 20);
  } else if (d.kind === 'ai') record.table = nativeTable(s, d, 241, 390, 23);
  else if (d.kind === 'original') {
    s.images.add({ blob: new Uint8Array(await fs.readFile(path.join(assets, d.asset))), contentType: 'image/png',
      alt: d.title, fit: 'contain', position: { left: 136, top: 213, width: 1000, height: 461 } });
  }
  return record;
}
