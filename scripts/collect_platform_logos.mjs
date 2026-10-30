import fs from 'node:fs/promises';
import path from 'node:path';
import { createRequire } from 'node:module';
import { inflateRawSync } from 'node:zlib';

const runtimeRequire = createRequire('C:/Users/lixu/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/package.json');
const sharp = runtimeRequire('sharp');
const output = path.resolve('docs/需求调研+需求分析/图片/平台标识');
const originals = path.join(output, '原始标识');
const headers = { 'User-Agent': 'academic-platform-logo-collector' };

async function download(url) {
  const response = await fetch(url, { headers, signal: AbortSignal.timeout(45000) });
  if (!response.ok) throw new Error(`下载失败 ${response.status}: ${url}`);
  return Buffer.from(await response.arrayBuffer());
}

async function githubFile(apiUrl) {
  const data = JSON.parse((await download(apiUrl)).toString());
  if (data.encoding !== 'base64') throw new Error(`仓库内容格式异常: ${apiUrl}`);
  return Buffer.from(data.content, 'base64');
}

async function downloadRange(url, first, last) {
  const response = await fetch(url, { headers: { ...headers, Range: `bytes=${first}-${last}` }, signal: AbortSignal.timeout(30000) });
  if (response.status !== 206) throw new Error(`图标包不支持范围读取: ${response.status}`);
  const bytes = Buffer.from(await response.arrayBuffer());
  if (bytes.length !== last - first + 1) throw new Error('图标包范围读取长度异常');
  return bytes;
}

// 分段读取官方 ZIP 目录，仅下载需要的一个 SVG。
async function extractSvg(url, pattern, prefer = () => true) {
  const head = await fetch(url, { method: 'HEAD', headers, signal: AbortSignal.timeout(30000) });
  if (!head.ok) throw new Error(`图标包信息读取失败: ${head.status}`);
  const size = Number(head.headers.get('content-length'));
  if (!Number.isSafeInteger(size) || size < 22) throw new Error('图标包长度异常');
  const tail = await downloadRange(url, Math.max(0, size - 65557), size - 1);
  let end = tail.length - 22;
  while (end >= 0 && tail.readUInt32LE(end) !== 0x06054b50) end--;
  if (end < 0) throw new Error('未找到 ZIP 目录');
  const start = tail.readUInt32LE(end + 16);
  const length = tail.readUInt32LE(end + 12);
  const ranges = [];
  for (let offset = 0; offset < length; offset += 262144) ranges.push(downloadRange(url, start + offset, start + Math.min(length, offset + 262144) - 1));
  const archive = Buffer.concat(await Promise.all(ranges));
  let cursor = 0;
  const matches = [];
  for (let i = 0; i < tail.readUInt16LE(end + 10); i++) {
    if (archive.readUInt32LE(cursor) !== 0x02014b50) throw new Error('ZIP 目录格式异常');
    const nameLength = archive.readUInt16LE(cursor + 28);
    const name = archive.subarray(cursor + 46, cursor + 46 + nameLength).toString('utf8');
    if (pattern.test(name) && !name.includes('__MACOSX')) matches.push({ name, cursor });
    cursor += 46 + nameLength + archive.readUInt16LE(cursor + 30) + archive.readUInt16LE(cursor + 32);
  }
  const item = matches.find(x => prefer(x.name)) ?? matches[0];
  if (!item) throw new Error(`图标包中缺少目标文件: ${pattern}`);
  const offset = archive.readUInt32LE(item.cursor + 42);
  const local = await downloadRange(url, offset, offset + 29);
  const begin = offset + 30 + local.readUInt16LE(26) + local.readUInt16LE(28);
  const compressed = await downloadRange(url, begin, begin + archive.readUInt32LE(item.cursor + 20) - 1);
  const method = archive.readUInt16LE(item.cursor + 10);
  if (![0, 8].includes(method)) throw new Error(`不支持的 ZIP 压缩方式: ${method}`);
  console.log(`官方图标包: ${item.name}`);
  return { buffer: method === 8 ? inflateRawSync(compressed) : compressed, entry: item.name };
}

const azurePack = 'https://arch-center.azureedge.net/icons/Azure_Public_Service_Icons_V24.zip';
const awsPack = 'https://d1.awsstatic.com/onedam/marketing-channels/website/public/shared/architecture-icon-release/Icon-package_07312026.5846e92413caa21490223536cc97f1269e44fa92.zip';
const huaweiFont = 'https://res-static.hc-cdn.cn/aem/content/dam/cloudbu-site/archive/china/static/v2_resources/fonts/iconFont-product/iconFont-product.svg?1657676474029';
const entries = [
  { id: 'modelarts', label: '华为云 ModelArts', page: 'https://www.huaweicloud.com/product/modelarts.html', kind: '官方产品图标字形', url: huaweiFont },
  { id: 'tione', label: '腾讯云 TI-ONE', page: 'https://cloud.tencent.com/document/product/851', kind: '官方产品导航图标', url: 'https://main.qcloudimg.com/image/product/2156/32_32/blue.svg' },
  { id: 'pai', label: '阿里云 PAI', page: 'https://help.aliyun.com/zh/pai/', kind: '官方阿里云品牌标识配产品名', url: 'https://help.aliyun.com/zh/pai/' },
  { id: 'bml', label: '百度智能云 BML', page: 'https://cloud.baidu.com/product/bml', kind: '官方百度智能云品牌标识配产品名', url: 'https://bce.bdstatic.com/portal-server/common/header/portal-default.js' },
  { id: 'sagemaker', label: 'AWS SageMaker', page: 'https://aws.amazon.com/architecture/icons/', kind: '官方产品架构图标', url: awsPack },
  { id: 'azureml', label: 'Azure ML', page: 'https://learn.microsoft.com/en-us/azure/architecture/icons/', kind: '官方产品架构图标', url: azurePack },
  { id: 'crater', label: 'Crater', page: 'https://github.com/raids-lab/crater', kind: '官方项目图标', url: 'https://api.github.com/repos/raids-lab/crater/contents/frontend/public/crater.svg' },
  { id: 'kubeflow', label: 'Kubeflow', page: 'https://github.com/cncf/artwork/tree/main/projects/kubeflow', kind: 'CNCF 官方项目图标', url: 'https://api.github.com/repos/cncf/artwork/contents/projects/kubeflow/icon/color/kubeflow-icon.svg?ref=main' },
];

async function getAsset(item) {
  if (['crater', 'kubeflow'].includes(item.id)) return githubFile(item.url);
  if (item.id === 'sagemaker' || item.id === 'azureml') {
    const result = item.id === 'sagemaker'
      ? await extractSvg(item.url, /Arch_Amazon-SageMaker(?:-AI)?_\d+\.svg$/i, name => /64\//.test(name))
      : await extractSvg(item.url, /(?:Azure-Machine-Learning|Machine-Learning)\.svg$/i, name => /Azure-Machine-Learning\.svg$/i.test(name));
    item.archiveEntry = result.entry;
    return result.buffer;
  }
  const source = await download(item.url);
  const text = source.toString();
  if (item.id === 'modelarts') {
    const glyph = text.match(/<glyph\s+glyph-name="modelarts"[^>]*>/)?.[0];
    const d = glyph?.match(/\sd="([^"]+)"/)?.[1];
    if (!d) throw new Error('ModelArts 官方字形缺失');
    return Buffer.from(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1001 1001"><path fill="#252b3a" transform="translate(0 1001) scale(1 -1)" d="${d}"/></svg>`);
  }
  if (item.id === 'pai') {
    const svg = text.match(/<svg[^>]*viewBox="0 0 4608 1024"[\s\S]*?<\/svg>/)?.[0];
    if (!svg) throw new Error('阿里云官方品牌标识缺失');
    return Buffer.from(svg);
  }
  if (item.id === 'bml') {
    let svg = (text.match(/<svg[\s\S]*?<\/svg>/g) ?? []).find(x => x.includes('logo-text'));
    if (!svg) throw new Error('百度智能云官方品牌标识缺失');
    svg = svg.replace(/\\n/g, '\n').replace('xmlns=""', 'xmlns="http://www.w3.org/2000/svg"').replace('xmlns:xlink=""', 'xmlns:xlink="http://www.w3.org/1999/xlink"');
    return Buffer.from(svg);
  }
  return source;
}

await fs.mkdir(originals, { recursive: true });
for (const item of entries) {
  const file = path.join(originals, `${item.id}.svg`);
  try {
    item.buffer = await fs.readFile(file);
  } catch (error) {
    if (error.code !== 'ENOENT') throw error;
    item.buffer = await getAsset(item);
    await fs.writeFile(file, item.buffer, { flag: 'wx' });
  }
  if (!item.buffer.toString().includes('<svg')) throw new Error(`标识文件格式异常: ${item.id}`);
  item.png = await sharp(item.buffer, { density: 300 }).resize({ width: 1040, height: 480, fit: 'inside' }).png().toBuffer();
  console.log(`已整理 ${item.label}`);
}

// 两行四列，统一图形区域与名称基线；宽标识保留完整比例。
const width = 3200;
const height = 1800;
const overlays = [];
for (const [index, item] of entries.entries()) {
  const cx = 400 + (index % 4) * 800;
  const cy = index < 4 ? 520 : 1280;
  const wide = ['pai', 'bml'].includes(item.id);
  const image = await sharp(item.png).trim().resize({ width: wide ? 570 : 300, height: 300, fit: 'inside' }).png().toBuffer();
  const info = await sharp(image).metadata();
  overlays.push({ input: image, left: Math.round(cx - info.width / 2), top: Math.round(cy - info.height / 2) });
  const label = `<svg xmlns="http://www.w3.org/2000/svg" width="800" height="110"><text x="400" y="76" text-anchor="middle" fill="#1c293a" font-family="Microsoft YaHei,Microsoft YaHei UI,Arial,sans-serif" font-size="48" font-weight="500">${item.label}</text></svg>`;
  overlays.push({ input: Buffer.from(label), left: cx - 400, top: cy + 200 });
}
const transparent = await sharp({ create: { width, height, channels: 4, background: '#ffffff00' } }).composite(overlays).png().toBuffer();
await fs.writeFile(path.join(output, '八个平台标识_横屏_透明底.png'), transparent);
await sharp(transparent).flatten({ background: '#ffffff' }).png().toFile(path.join(output, '八个平台标识_横屏_白底.png'));
await sharp(transparent).flatten({ background: '#174563' }).png().toFile(path.join(output, '深色背景检查.png'));
const manifest = entries.map(({ buffer, png, ...record }) => record);
await fs.writeFile(path.join(output, '来源记录.json'), JSON.stringify({ collectedAt: '2026-10-13', dimensions: [width, height], entries: manifest }, null, 2));
console.log(`已导出横屏合成图: ${output}`);
