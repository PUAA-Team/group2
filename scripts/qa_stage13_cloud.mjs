// 云端只读验收：除登录外不创建或修改业务记录。
import assert from "node:assert/strict";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { adminRoutes } from "./qa_stage13_admin.mjs";

const version = process.env.QA_WEB_VERSION || "stage13-1";
assert.ok(["stage13-1", "stage13-2", "stage13-3"].includes(version));
const root = "D:/model-training-demo/stage13-20261029/" + (version === "stage13-1" ? "cloud-browser" : "cloud-browser-" + version.replace("stage13-", "b"));
await mkdir(root, { recursive: true });
const login = JSON.parse(await readFile("D:/model-training-demo/server-deploy-prep-20261029/private-admin-login.json", "utf8"));
const fixture = JSON.parse(await readFile("D:/model-training-demo/server-deploy-prep-20261029/cloud-flow-01/verification.json", "utf8"));
assert.equal(fixture.url, "https://47.93.115.188:5488");
const pages = await (await fetch("http://127.0.0.1:9222/json")).json();
const socket = new WebSocket(pages.find(item => item.type === "page").webSocketDebuggerUrl);
await new Promise((resolve, reject) => { socket.addEventListener("open", resolve, { once: true }); socket.addEventListener("error", reject, { once: true }); });
let next = 0; const pending = new Map(), report = { url: fixture.url, layouts: [], screenshots: [], errors: [] };
socket.addEventListener("message", event => {
  const message = JSON.parse(event.data);
  if (message.method === "Runtime.exceptionThrown") report.errors.push(message.params.exceptionDetails.exception?.description || message.params.exceptionDetails.text);
  const callbacks = pending.get(message.id); if (!callbacks) return;
  pending.delete(message.id); clearTimeout(callbacks.timer); message.error ? callbacks.reject(new Error(message.error.message)) : callbacks.resolve(message.result);
});
function cdp(method, params = {}) { return new Promise((resolve, reject) => { const id = ++next, timer = setTimeout(() => { pending.delete(id); reject(new Error("CDP超时: " + method)); }, 20000); pending.set(id, { resolve, reject, timer }); socket.send(JSON.stringify({ id, method, params })); }); }
async function evaluate(expression) { const result = await cdp("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true }); if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text); return result.result.value; }
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
async function wait(expression) { for (let i = 0; i < 180; i++) { if (await evaluate(expression)) return; await pause(100); } throw new Error("页面等待超时: " + expression); }
async function capture(name) { const result = await cdp("Page.captureScreenshot", { format: "png", captureBeyondViewport: false }); await writeFile(join(root, name), Buffer.from(result.data, "base64")); report.screenshots.push(name); }
try {
  await cdp("Page.enable"); await cdp("Runtime.enable"); await cdp("Network.enable"); await cdp("Network.setCacheDisabled", { cacheDisabled: true });
  await cdp("Emulation.setDeviceMetricsOverride", { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false });
  await cdp("Page.navigate", { url: fixture.url + "/?deployment=" + version + "-" + Date.now() + "#/home" });
  await wait(`document.readyState==='complete' && !!document.querySelector('script[src*="${version}"]')`);
  await wait("!!document.querySelector('[data-form=login]') || !!document.querySelector('.page-heading h1')");
  if (await evaluate("!!document.querySelector('[data-form=login]')")) await evaluate(`(() => {const f=document.querySelector('[data-form=login]');f.elements.account.value=${JSON.stringify(login.account)};f.elements.password.value=${JSON.stringify(login.password)};f.requestSubmit();})()`);
  await wait("!!document.querySelector('.console-summary')");
  const routes = [["/home", ".console-summary"], ["/models", ".console-catalog"], ["/projects", ".console-catalog"], ["/datasets", ".table"], ["/datasets/new", "[data-form=dataset-import]"], ["/train/new", "[data-form=training-wizard]"], ["/runs", ".table"], ...["overview", "metrics", "logs", "outputs"].map(tab => [`/runs/${fixture.job_id}?tab=${tab}`, ".tabs"]), ...(["stage13-2", "stage13-3"].includes(version) ? adminRoutes : [])].map(([path, selector]) => [path + (path.includes('?') ? '&' : '?') + 'workspace=' + fixture.workspace_id, selector]);
  if (version === "stage13-3") {
    const data = JSON.parse(await readFile("D:/model-training-demo/stage13-20261029/cloud-data-verification.json", "utf8"));
    routes.push(...[["/annotation", ".table"], [`/annotation/${data.annotation_id}`, ".annotation-workbench"], ["/augmentation", ".table"], ["/data-operations", ".table"], [`/data-operations/${data.augmentation_id}`, ".data-thumbnail"], [`/datasets/${data.text.dataset}/samples?version=${data.text.version}`, ".table"], [`/datasets/${data.images.dataset}/samples?version=${data.images.version}`, ".data-thumbnail"]].map(([path, selector]) => [path + (path.includes('?') ? '&' : '?') + 'workspace=' + data.workspace_id, selector]));
  }
  for (const width of [1440, 1024, 390]) {
    await cdp("Emulation.setDeviceMetricsOverride", { width, height: 1000, deviceScaleFactor: 1, mobile: width < 600 });
    for (const [route, selector] of routes) {
      const pagePath = route.split('?')[0];
      await evaluate(`location.hash=${JSON.stringify("#" + route)}`); await pause(200);
      await wait(`!document.querySelector('.live-loading') && !!document.querySelector(${JSON.stringify(selector)})`);
      await evaluate("window.scrollTo(0,0)");
      const result = await evaluate("(() => ({overflow:document.documentElement.scrollWidth>innerWidth,minimumFont:Math.min(...[...document.querySelectorAll('.page-heading h1,button,input,select,th,td,label,.chip,.console-stepper strong')].filter(e=>e.getClientRects().length).map(e=>parseFloat(getComputedStyle(e).fontSize)))}))()");
      report.layouts.push({ route, width, ...result }); assert.equal(result.overflow, false, route); assert.ok(result.minimumFont >= 14, route);
      if ((pagePath === "/home" || pagePath === "/models" || route.includes("tab=metrics") || pagePath === "/train/new") && width !== 1024) await capture((pagePath === "/home" ? "home" : pagePath === "/models" ? "models" : pagePath === "/train/new" ? "training-wizard" : "training-metrics") + "-" + width + ".png");
      if (["/admin/stats", "/admin/settings"].includes(pagePath) && width !== 1024) await capture((pagePath === "/admin/stats" ? "admin-statistics" : "admin-settings") + "-" + width + ".png");
      if (width !== 1024 && route.startsWith('/annotation/')) await capture('annotation-' + width + '.png');
      if (width !== 1024 && route.startsWith('/data-operations/')) await capture('augmentation-' + width + '.png');
    }
  }
  report.persisted = await evaluate(`(async () => {const base='/api/v1/workspaces/${fixture.workspace_id}';const job=await (await fetch(base+'/jobs/${fixture.job_id}')).json();const nodes=await (await fetch(base+'/resources')).json();return {job_preserved:job.data.status==='succeeded',actual_device:job.data.device_kind,accuracy:job.data.result.accuracy,worker_online:nodes.data.some(n=>n.status==='在线'),worker_connected:nodes.data.some(n=>['在线','暂停接收'].includes(n.status)),node_status:nodes.data.map(n=>n.status)};})()`);
  assert.equal(report.persisted.job_preserved, true); assert.equal(report.persisted.actual_device, "cuda");
  assert.equal(report.persisted.worker_connected, true);
  assert.equal(report.errors.length, 0); report.success = true;
  console.log(JSON.stringify({ success: true, layouts: report.layouts.length, screenshots: report.screenshots.length, errors: 0, persisted: report.persisted }));
} finally { await writeFile(join(root, "browser-audit.json"), JSON.stringify(report, null, 2)); socket.close(); }
