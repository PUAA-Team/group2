// 保存同学原始界面的实拍图片；不注入状态、不改写页面内容。
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

const work = process.argv[2];
const phase = process.argv[3] || 'online';
if (!work) throw new Error('请指定隔离验证目录');
const targets = await (await fetch('http://127.0.0.1:9320/json')).json();
const page = targets.find(item => item.type === 'page');
if (!page) throw new Error('未找到隔离浏览器');
const socket = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((resolve, reject) => {
  socket.addEventListener('open', resolve, { once: true });
  socket.addEventListener('error', reject, { once: true });
});
let id = 0;
const pending = new Map();
socket.addEventListener('message', event => {
  const message = JSON.parse(event.data);
  if (!pending.has(message.id)) return;
  const request = pending.get(message.id);
  pending.delete(message.id);
  message.error ? request.reject(new Error(message.error.message)) : request.resolve(message.result);
});
function cdp(method, params = {}) {
  return new Promise((resolve, reject) => {
    pending.set(++id, { resolve, reject });
    socket.send(JSON.stringify({ id, method, params }));
  });
}
async function evaluate(expression) {
  const result = await cdp('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true });
  if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
  return result.result.value;
}
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
const dir = join(work, 'screenshots');
await mkdir(dir, { recursive: true });
await cdp('Page.enable');
await cdp('Runtime.enable');
await cdp('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false });
await cdp('Page.navigate', { url: 'http://127.0.0.1:8875/' });
await pause(800);
await evaluate("document.getElementById('token').value='local-review-only-20261020'; document.getElementById('connect').click()");
await pause(700);
const records = [];
async function capture(name, tab) {
  if (tab) await evaluate(`document.querySelector('[data-page="${tab}"]').click()`);
  await pause(250);
  const { data } = await cdp('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
  await writeFile(join(dir, name + '.png'), Buffer.from(data, 'base64'));
  records.push({ name, tab, text: await evaluate('document.body.innerText'), time: new Date().toISOString() });
}
if (phase === 'online') {
  const evidence = JSON.parse(await readFile(join(work, 'verification.json'), 'utf8'));
  await capture('W01_控制服务首页', 'home');
  await capture('W02_训练配置', 'train');
  await capture('W03_推理配置', 'infer');
  await capture('W04_GPU节点在线', 'resources');
  await evaluate(`showLogs(${JSON.stringify(evidence.smoke_task_id)})`);
  await pause(250);
  await capture('W05_Worker任务日志');
} else {
  await capture('W06_GPU节点离线', 'resources');
}
await writeFile(join(work, `screenshots-${phase}.json`), JSON.stringify(records, null, 2));
socket.close();
console.log(JSON.stringify({ phase, captures: records.map(item => item.name) }));
