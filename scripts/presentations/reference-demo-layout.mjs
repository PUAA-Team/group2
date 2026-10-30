import fs from 'node:fs/promises';
import { layoutSlide } from './defense-v2-layout.mjs';
import { FONT, text } from './slide-layout.mjs';

const BLUE = '#1063A8', INK = '#172A3B', LINE = '#627E91';
function node(slide, label, x, y, w, h, geometry = 'roundRect', fill = '#FFFFFF', font = 20) {
  const s = slide.shapes.add({ geometry, name: label, position: { left: x, top: y, width: w, height: h }, fill, line: { fill: LINE, width: 1.1 } });
  s.text = label;
  s.text.style = { typeface: FONT, fontSize: font, color: INK, alignment: 'center', verticalAlignment: 'middle', insets: 2, autoFit: 'none', wrap: 'none' };
  return s;
}
function edge(slide, from, to, options = {}) {
  const connector = slide.shapes.connect(from, to, { kind: 'straight', line: { fill: LINE, width: 1.2, style: options.dashed ? 'dashed' : 'solid' },
    ...(options.association ? {} : { tail: { type: 'arrow', width: 'sm', length: 'sm' } }),
    ...options });
  // 新连线默认置底，会被模板正文背景遮住，明确提升层级。
  connector.bringToFront();
  return connector;
}
function note(slide, value, x, y, w, h = 26, size = 18) { return text(slide, value, x, y, w, h, size, { color: BLUE }); }
function finalNode(slide, x, y) {
  const outer = node(slide, '', x, y, 22, 22, 'ellipse');
  node(slide, '', x + 5, y + 5, 12, 12, 'ellipse', INK);
  return outer;
}

function usecase(slide) {
  node(slide, '', 348, 247, 783, 375, 'rect', '#FAFBFC');
  note(slide, '训练业务', 369, 258, 250);
  const actor = node(slide, '«actor»\n普通用户', 145, 403, 160, 77, 'rect', '#FAFBFC');
  const submit = node(slide, '提交训练运行', 399, 303, 246, 66, 'ellipse');
  const observe = node(slide, '查看监控及日志', 399, 429, 246, 66, 'ellipse');
  const stop = node(slide, '取消 / 停止运行', 399, 548, 246, 58, 'ellipse');
  const validate = node(slide, '校验训练输入', 833, 303, 246, 66, 'ellipse');
  const authorize = node(slide, '审核资源资格', 833, 418, 246, 66, 'ellipse');
  [submit, observe, stop].forEach(s => edge(slide, actor, s, { association: true, fromSide: 'right', toSide: 'left' }));
  edge(slide, submit, validate, { dashed: true, fromSide: 'right', toSide: 'left' });
  edge(slide, submit, authorize, { dashed: true, fromSide: 'right', toSide: 'left' });
  note(slide, '«include»', 690, 300, 138);
  note(slide, '«include»', 690, 385, 138);
  note(slide, '核心子模型。数据导入、模型服务和管理用例另列详细规约', 136, 640, 1000, 27, 19);
}
function activity(slide) {
  // 分区只表示责任归属，队列等待及后续执行由状态模型继续描述。
  [136, 466, 796].forEach((x, i) => {
    node(slide, '', x, 250, 330, 374, 'rect', '#FAFBFC');
    note(slide, ['用户', '控制服务', '队列'][i], x + 16, 261, 295);
  });
  const initial = node(slide, '', 292, 297, 14, 14, 'ellipse', INK);
  const config = node(slide, '填写模型、数据及参数', 169, 326, 264, 50);
  const confirm = node(slide, '确认提交', 200, 409, 204, 48);
  const check = node(slide, '校验权限 / 兼容 / 幂等', 493, 409, 276, 48);
  const decision = node(slide, '', 605, 486, 52, 48, 'diamond');
  const reject = node(slide, '显示字段或资格错误', 169, 488, 264, 49);
  const created = node(slide, '持久化并返回运行 ID', 497, 568, 270, 47);
  const queue = node(slide, '入队等待合资格资源', 825, 568, 274, 47);
  const final = finalNode(slide, 951, 638);
  const rejectFinal = finalNode(slide, 292, 573);
  edge(slide, initial, config, { fromSide: 'bottom', toSide: 'top' });
  edge(slide, config, confirm, { fromSide: 'bottom', toSide: 'top' });
  edge(slide, confirm, check, { fromSide: 'right', toSide: 'left' });
  edge(slide, check, decision, { fromSide: 'bottom', toSide: 'top' });
  edge(slide, decision, reject, { fromSide: 'left', toSide: 'right' });
  edge(slide, decision, created, { fromSide: 'bottom', toSide: 'top' });
  edge(slide, reject, rejectFinal, { fromSide: 'bottom', toSide: 'top' });
  edge(slide, created, queue, { fromSide: 'right', toSide: 'left' });
  edge(slide, queue, final, { fromSide: 'bottom', toSide: 'top' });
  note(slide, '[不通过]', 466, 485, 130);
  note(slide, '[通过]', 657, 538, 130);
}
function state(slide) {
  const labels = ['Queued\n排队', 'Preparing\n准备', 'Running\n运行', 'Finalizing\n归档及清理', 'Succeeded\n成功'];
  const top = labels.map((s, i) => node(slide, s, 140 + 200 * i, 285, i === 4 ? 176 : 158, 66));
  for (let i = 0; i < 4; i++) edge(slide, top[i], top[i + 1], { fromSide: 'right', toSide: 'left' });
  ['派发', '就绪', '正常退出', '归档/清理确认'].forEach((s, i) => note(slide, s, 147 + 200 * i, 252, 195, 24, 17));
  const cancelled = node(slide, 'Cancelled\n排队取消', 140, 555, 158, 66);
  const stopping = node(slide, 'Stopping\n停止中', 340, 424, 158, 66);
  const stopped = node(slide, 'Stopped\n已停止', 340, 555, 158, 66);
  const failed = node(slide, 'Failed\n失败', 670, 555, 158, 66);
  edge(slide, top[0], cancelled, { fromSide: 'bottom', toSide: 'top' });
  note(slide, '取消', 168, 431, 90);
  edge(slide, top[1], stopping, { fromSide: 'bottom', toSide: 'top' });
  edge(slide, top[2], stopping, { fromSide: 'bottom', toSide: 'right' });
  note(slide, '停止请求', 430, 378, 145);
  edge(slide, stopping, stopped, { fromSide: 'bottom', toSide: 'top' });
  note(slide, '退出及清理确认', 513, 506, 175, 24, 17);
  [top[2], top[3]].forEach(s => edge(slide, s, failed, { fromSide: 'bottom', toSide: 'top' }));
  note(slide, '执行 / 归档失败', 865, 420, 270, 27, 19);
  text(slide, '准备失败也进入 Failed\n清理不明时隔离设备\nFinalizing 不接受新停止', 865, 495, 270, 122, 19);
  note(slide, '草稿及提交中属于表单。终态不回退，重新运行创建新 ID', 136, 647, 1000, 27, 19);
}
async function prototype(slide) {
  const filename = 'D:/model-training-demo/qa-browser-profile/captures/stage3-1790694505923/user-modal-desktop.png';
  slide.images.add({ blob: new Uint8Array(await fs.readFile(filename)), contentType: 'image/png', alt: '纯前端原型用户管理新增弹窗', fit: 'contain',
    position: { left: 136, top: 253, width: 668, height: 360 }, crop: { left: 0.237, right: 0.244, top: 0.214, bottom: 0.207 } });
  note(slide, '实际操作问题', 847, 255, 286, 35, 22);
  text(slide, '新增用户是否在弹窗完成？\n能否选择所属组？\n取消是否保留原列表？', 847, 304, 286, 139, 21);
  note(slide, '后续权限确认', 847, 461, 286, 35, 22);
  text(slide, '核对个人禁用和较小配额。\nUUID 授权待后端实现。\n用户确认结果尚未采集。', 847, 509, 286, 145, 21);
  note(slide, '账户保存、权限及设备流程为纯前端演示', 136, 635, 1000, 30, 19);
}

export async function layoutDemo(slide, d, deck, assets, chartFont, record) {
  await layoutSlide(slide, d, deck, assets, chartFont, record);
  if (d.diagram === 'usecase') usecase(slide);
  else if (d.diagram === 'activity') activity(slide);
  else if (d.diagram === 'state') state(slide);
  else if (d.diagram === 'prototype') await prototype(slide);
  record.diagram = d.diagram || null;
}
