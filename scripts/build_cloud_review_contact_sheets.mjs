import { createRequire } from 'node:module';
import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const require = createRequire('C:/Users/lixu/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/package.json');
const sharp = require('sharp');
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const folder = path.join(root, 'frontend/design-review/cloud-v2/previews');
const audit = JSON.parse(await readFile(path.join(folder, 'browser-audit.json'), 'utf8'));
if ([...audit.responsive, ...audit.interactions].some(check => !check.passed)) throw new Error('浏览器验收尚有未通过项');

const width = 1440;
const height = 1000;
const gap = 24;
const labelHeight = 76;
const labels = ['云管控型', '团队协作型'];
const meta = ['正文 14px / 控件 32px / 基础行高 58px', '正文 14px / 控件 36px / 基础行高 64px'];
for (const [page, name] of [['jobs', '任务列表对照'], ['components', '组件对照'], ['modal', '弹窗对照'], ['resources', '资源管理对照']]) {
  const compositions = [];
  for (const [index, system] of ['ali', 'tencent'].entries()) {
    const capture = await readFile(path.join(folder, `${system}-${page}.jpg`));
    const dimensions = await sharp(capture).metadata();
    if (dimensions.width !== width || dimensions.height !== height) throw new Error(`截图尺寸不一致：${system}-${page}`);
    const label = Buffer.from(`<svg width="1440" height="76" xmlns="http://www.w3.org/2000/svg"><rect width="1440" height="76" fill="#fff"/><text x="22" y="32" font-family="Microsoft YaHei" font-size="24" fill="#1e2b3d">${labels[index]}</text><text x="22" y="59" font-family="Microsoft YaHei" font-size="16" fill="#687586">${meta[index]}</text></svg>`);
    compositions.push({ input: label, left: gap + index * (width + gap), top: gap });
    compositions.push({ input: capture, left: gap + index * (width + gap), top: gap + labelHeight });
  }
  const output = await sharp({ create: { width: width * 2 + gap * 3, height: height + labelHeight + gap * 2, channels: 3, background: '#e7ebf1' } })
    .composite(compositions).jpeg({ quality: 92, chromaSubsampling: '4:4:4' }).toBuffer();
  await writeFile(path.join(folder, `${name}.jpg`), output);
  process.stdout.write(`${name}：${width * 2 + gap * 3} × ${height + labelHeight + gap * 2}\n`);
}

const statusLayers = [];
let statusWidth = 0;
for (const [index, [mode, label]] of [['text', '纯文字'], ['outline', '线框标记'], ['icon', '图形符号']].entries()) {
  const capture = await readFile(path.join(folder, `status-${mode}.jpg`));
  const dimensions = await sharp(capture).metadata();
  statusWidth = Math.max(statusWidth, dimensions.width + 48);
  const labelSvg = Buffer.from(`<svg width="440" height="30" xmlns="http://www.w3.org/2000/svg"><text x="0" y="21" font-family="Microsoft YaHei" font-size="16" fill="#39465a">${label}</text></svg>`);
  statusLayers.push({ input: labelSvg, left: 24, top: 12 + index * 84 });
  statusLayers.push({ input: capture, left: 24, top: 42 + index * 84 });
}
await sharp({ create: { width: Math.max(statusWidth, 488), height: 264, channels: 3, background: '#fff' } }).composite(statusLayers).jpeg({ quality: 95, chromaSubsampling: '4:4:4' }).toFile(path.join(folder, '状态样式对照.jpg'));
process.stdout.write('状态样式对照已生成\n');
