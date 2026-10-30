import { mkdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";

const output = "D:/model-training-demo/backend-runtime/qwen-contract-rollout-20261029/browser";
await mkdir(output, { recursive: true });
const credentials = JSON.parse(await readFile("D:/model-training-demo/backend-runtime/training-flow-20261029-01/private-browser-login.json", "utf8"));
const pages = await (await fetch("http://127.0.0.1:9222/json")).json();
const socket = new WebSocket(pages.find(item => item.type === "page").webSocketDebuggerUrl);
await new Promise((resolve, reject) => { socket.addEventListener("open", resolve, { once: true }); socket.addEventListener("error", reject, { once: true }); });
let counter = 0; const pending = new Map(), report = { errors: [], layouts: [], screenshots: [] };
socket.addEventListener("message", event => {
  const message = JSON.parse(event.data);
  if (message.method === "Runtime.exceptionThrown") report.errors.push(message.params.exceptionDetails.exception?.description || message.params.exceptionDetails.text);
  if (!pending.has(message.id)) return;
  const pair = pending.get(message.id); pending.delete(message.id);
  message.error ? pair[1](message.error) : pair[0](message.result);
});
const cdp = (method, params = {}) => new Promise((resolve, reject) => { pending.set(++counter, [resolve, reject]); socket.send(JSON.stringify({ id: counter, method, params })); });
async function evaluate(expression) {
  const value = await cdp("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
  if (value.exceptionDetails) throw new Error(value.exceptionDetails.exception?.description || value.exceptionDetails.text);
  return value.result.value;
}
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
async function wait(expression) {
  for (let index = 0; index < 150; index++) { if (await evaluate(expression)) return; await pause(100); }
  throw new Error("界面等待超时：" + expression);
}
async function capture(name) {
  const image = await cdp("Page.captureScreenshot", { format: "png", captureBeyondViewport: false });
  await writeFile(join(output, name + ".png"), Buffer.from(image.data, "base64")); report.screenshots.push(name + ".png");
}
try {
  await cdp("Runtime.enable"); await cdp("Page.enable");
  await cdp("Emulation.setDeviceMetricsOverride", { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false });
  await cdp("Page.navigate", { url: "http://127.0.0.1:8001/?contract=1#/services" });
  await wait("!!document.querySelector('[data-form=login]') || !!document.querySelector('.page-heading h1')");
  if (await evaluate("!!document.querySelector('[data-form=login]')")) await evaluate(`(() => {const f=document.querySelector('[data-form=login]');f.elements.account.value=${JSON.stringify(credentials.account)};f.elements.password.value=${JSON.stringify(credentials.password)};f.requestSubmit();})()`);
  await wait("!!document.querySelector('.page-heading h1') && !document.querySelector('.live-loading')");
  await evaluate("location.hash='#/services'"); await pause(250);
  await wait("!!document.querySelector('[data-action=workflow-new]')");
  await evaluate("document.querySelector('[data-action=workflow-new]').click()");
  await evaluate("(() => { const f=document.querySelector('[role=dialog] form'); const option=[...f.elements.model_version_id.options].find(item=>item.textContent.includes('Qwen')); if(!option) throw new Error('缺少可用Qwen'); f.elements.model_version_id.value=option.value; f.elements.model_version_id.dispatchEvent(new Event('change',{bubbles:true})); })()");
  await wait("!!document.querySelector('[name=inference_instruction]')");
  report.suggestion = await evaluate("(() => {const f=document.querySelector('[role=dialog] form');return { mode:f.elements.inference_mode.value, instruction:!!f.elements.inference_instruction.value, labels:f.elements.inference_labels.value.split('\\n').filter(Boolean).length };})()");
  if (report.suggestion.mode !== "label" || !report.suggestion.instruction || report.suggestion.labels < 2) throw new Error("部署候选未正确显示");
  for (const width of [1440, 390]) {
    await cdp("Emulation.setDeviceMetricsOverride", { width, height: 1000, deviceScaleFactor: 1, mobile: width < 600 });
    const layout = await evaluate("(() => {const d=document.querySelector('[role=dialog]');return { width:innerWidth, overflow:document.documentElement.scrollWidth>innerWidth, dialogWidth:d.getBoundingClientRect().width, footerBottom:d.querySelector('.modal-footer').getBoundingClientRect().bottom, textMinimum:Math.min(...[...d.querySelectorAll('label,input,select,textarea,button')].filter(e=>e.getClientRects().length).map(e=>parseFloat(getComputedStyle(e).fontSize))) };})()");
    if (layout.overflow || layout.dialogWidth > width || layout.footerBottom > 1001 || layout.textMinimum < 14) throw new Error("部署弹窗布局不通过");
    report.layouts.push(layout); await capture(width === 1440 ? "deployment-desktop" : "deployment-mobile");
  }
  await evaluate("(() => {const f=document.querySelector('[role=dialog] form');f.elements.inference_mode.value='generate';f.elements.inference_mode.dispatchEvent(new Event('change',{bubbles:true}));})()");
  report.generateMode = await evaluate("document.querySelector('[data-inference-labels]').hidden && !document.querySelector('[name=inference_instruction]').required");
  if (!report.generateMode) throw new Error("自由生成模式仍要求固定标签");
  await evaluate("(() => {const f=document.querySelector('[role=dialog] form');f.elements.inference_mode.value='label';f.elements.inference_mode.dispatchEvent(new Event('change',{bubbles:true}));f.elements.name.value='推理约束界面验收';f.elements.submit_now.checked=false;f.requestSubmit();})()");
  await wait("!document.querySelector('[role=dialog]') && document.body.textContent.includes('标签分类')");
  report.draftSaved = await evaluate("location.hash.startsWith('#/runs/job_') && document.body.textContent.includes('输出标签')");
  report.success = report.errors.length === 0 && report.draftSaved;
  console.log(JSON.stringify({ success: report.success, suggestion: report.suggestion, layouts: report.layouts.length, generateMode: report.generateMode, draftSaved: report.draftSaved, errors: report.errors }));
} finally {
  await writeFile(join(output, "browser-audit.json"), JSON.stringify(report, null, 2)); socket.close();
}
