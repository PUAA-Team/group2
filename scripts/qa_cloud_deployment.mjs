import { mkdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";

const root = "D:/model-training-demo/server-deploy-prep-20261029";
const output = join(root, "browser");
await mkdir(output, { recursive: true });
const credentials = JSON.parse(await readFile(join(root, "private-admin-login.json"), "utf8"));
const flow = JSON.parse(await readFile(join(root, "cloud-flow-01/verification.json"), "utf8"));
const targets = await (await fetch("http://127.0.0.1:9222/json")).json();
const socket = new WebSocket(targets.find(item => item.type === "page").webSocketDebuggerUrl);
await new Promise((resolve, reject) => { socket.addEventListener("open", resolve, { once: true }); socket.addEventListener("error", reject, { once: true }); });
let next = 0;
const pending = new Map(), report = { url: flow.url, errors: [], layouts: [], screenshots: [] };
socket.addEventListener("message", event => {
  const message = JSON.parse(event.data);
  if (message.method === "Runtime.exceptionThrown") report.errors.push(message.params.exceptionDetails.exception?.description || message.params.exceptionDetails.text);
  const callbacks = pending.get(message.id);
  if (!callbacks) return;
  pending.delete(message.id);
  message.error ? callbacks[1](new Error(message.error.message)) : callbacks[0](message.result);
});
const cdp = (method, params = {}) => new Promise((resolve, reject) => { pending.set(++next, [resolve, reject]); socket.send(JSON.stringify({ id: next, method, params })); });
async function evaluate(expression) {
  const response = await cdp("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
  if (response.exceptionDetails) throw new Error(response.exceptionDetails.exception?.description || response.exceptionDetails.text);
  return response.result.value;
}
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
async function wait(expression) {
  for (let index = 0; index < 150; index++) { if (await evaluate(expression)) return; await pause(100); }
  throw new Error("页面等待超时");
}
async function capture(name) {
  const response = await cdp("Page.captureScreenshot", { format: "png", captureBeyondViewport: false });
  await writeFile(join(output, name), Buffer.from(response.data, "base64"));
  report.screenshots.push(name);
}
try {
  await cdp("Page.enable"); await cdp("Runtime.enable"); await cdp("Network.enable");
  await cdp("Network.setCacheDisabled", { cacheDisabled: true });
  await cdp("Emulation.setDeviceMetricsOverride", { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false });
  const navigation = await cdp("Page.navigate", { url: flow.url + "/?deployment=20261029-04#/home" });
  if (navigation.errorText) throw new Error("导航未完成：" + navigation.errorText);
  await wait("document.readyState==='complete' && !!document.querySelector('script[src*=\"app.js?v=cloud-1\"]')");
  await wait("!!document.querySelector('[data-form=login]') || !!document.querySelector('.page-heading h1')");
  if (await evaluate("!!document.querySelector('[data-form=login]')")) {
    await evaluate(`(() => { const form=document.querySelector('[data-form=login]'); form.elements.account.value=${JSON.stringify(credentials.account)}; form.elements.password.value=${JSON.stringify(credentials.password)}; form.requestSubmit(); })()`);
  }
  await wait("!!document.querySelector('.page-heading h1') && !document.querySelector('.live-loading')");
  report.environmentLabel = await evaluate("document.body.textContent.includes('本机环境')");
  if (report.environmentLabel) throw new Error("远端页面误标为本机环境");
  const routes = ["/home", "/admin/resources", "/datasets", "/models", "/runs?project=" + flow.project_id, "/runs/" + flow.job_id];
  for (const width of [1440, 390]) {
    await cdp("Emulation.setDeviceMetricsOverride", { width, height: 1000, deviceScaleFactor: 1, mobile: width < 600 });
    for (const route of routes) {
      await evaluate(`location.hash=${JSON.stringify("#" + route)}`);
      await pause(500);
      await wait("!!document.querySelector('.page-heading h1') && !document.querySelector('.live-loading')");
      const layout = await evaluate("(() => ({width:innerWidth, overflow:document.documentElement.scrollWidth>innerWidth, heading:document.querySelector('.page-heading h1').textContent, minimumInspectedFont:Math.min(...[...document.querySelectorAll('h1,button,input,select,th,td,label')].filter(item=>item.getClientRects().length).map(item=>parseFloat(getComputedStyle(item).fontSize))) }))()");
      report.layouts.push({ route, ...layout });
      if (layout.overflow || layout.minimumInspectedFont < 14) throw new Error("页面尺寸或文字检查未通过：" + route);
      if (route === "/admin/resources" && width === 1440) await capture("cloud-resources.png");
      if (route === "/runs/" + flow.job_id) {
        await wait(`document.body.textContent.includes(${JSON.stringify(flow.job.name)})`);
        const resultTitle = await evaluate("(() => { const item=[...document.querySelectorAll('.section-heading h2')].find(item=>item.textContent==='执行结果'); return {width:item.getBoundingClientRect().width,font:parseFloat(getComputedStyle(item).fontSize)}; })()");
        if (resultTitle.width < resultTitle.font * 4) throw new Error("执行结果标题被按钮挤压换行");
        await capture(width === 1440 ? "cloud-training-desktop.png" : "cloud-training-mobile.png");
      }
    }
  }
  report.success = report.errors.length === 0;
  if (!report.success) throw new Error("页面存在JavaScript异常");
  console.log(JSON.stringify({ success: true, layouts: report.layouts.length, screenshots: report.screenshots.length, errors: report.errors.length }));
} finally {
  await writeFile(join(output, "browser-audit.json"), JSON.stringify(report, null, 2));
  socket.close();
}
