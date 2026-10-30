import { createRequire } from 'node:module';
import fs from 'node:fs/promises';
import path from 'node:path';

const requireRuntime = createRequire('C:/Users/lixu/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/package.json');
const sharp = requireRuntime('sharp');
const output = path.resolve('frontend/design-review/previews');
const schemes = [['a', 'A 精密工作台'], ['b', 'B 实验室'], ['c', 'C 资源控制台'], ['d', 'D 轻量工作室']];
const width = 1440;
const height = 960;
const gap = 32;
const labelHeight = 64;

for (const [page, title] of [['home', '四套工作台对照'], ['run', '四套训练详情对照'], ['resources', '四套资源管理对照']]) {
  const overlays = [];
  for (const [index, [id, label]] of schemes.entries()) {
    const left = gap + index % 2 * (width + gap);
    const top = gap + Math.floor(index / 2) * (height + labelHeight + gap);
    const source = await sharp(path.join(output, `${id}-${page}.jpg`)).resize(width, height, { fit: 'contain', background: '#ffffff' }).jpeg({ quality: 95 }).toBuffer();
    const heading = Buffer.from(`<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${labelHeight}"><rect width="100%" height="100%" fill="#ffffff"/><text x="20" y="44" font-family="Microsoft YaHei,Segoe UI,sans-serif" font-size="30" fill="#253747">${label}</text></svg>`);
    overlays.push({ input: heading, left, top }, { input: source, left, top: top + labelHeight });
  }
  await sharp({ create: { width: width * 2 + gap * 3, height: (height + labelHeight) * 2 + gap * 3, channels: 3, background: '#e9edf1' } }).composite(overlays).jpeg({ quality: 94 }).toFile(path.join(output, `${title}.jpg`));
  console.log(`已生成 ${title}.jpg`);
}

const responsive = JSON.parse(await fs.readFile(path.join(output, 'responsive-audit.json'), 'utf8'));
const interactions = JSON.parse(await fs.readFile(path.join(output, 'interaction-audit.json'), 'utf8'));
if (responsive.some(check => check.horizontal) || interactions.some(check => !check.pass)) throw new Error('浏览器验收记录包含失败项');
console.log(`验收：${responsive.length} 项响应式检查、${interactions.length} 项交互检查通过`);
