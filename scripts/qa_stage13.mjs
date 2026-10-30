// 仅操作D盘隔离的8002验收环境，凭据和样本不写入输出。
import assert from "node:assert/strict";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { adminFlows, adminRoutes } from "./qa_stage13_admin.mjs";
import { dataFlows } from "./qa_stage13_data.mjs";

const root = "D:/model-training-demo/stage13-20261029/qa", output = join(root, process.env.QA_OUTPUT || "browser");
await mkdir(output, { recursive: true });
const login = JSON.parse(await readFile(join(root, "private-login.json"), "utf8"));
const fixture = JSON.parse(await readFile(join(root, "fixture.json"), "utf8"));
assert.equal(fixture.url, "http://127.0.0.1:8002");
const targets = await (await fetch("http://127.0.0.1:9222/json")).json();
const socket = new WebSocket(targets.find(item => item.type === "page").webSocketDebuggerUrl);
await new Promise((resolve, reject) => { socket.addEventListener("open", resolve, { once: true }); socket.addEventListener("error", reject, { once: true }); });
let next = 0; const pending = new Map(), report = { layouts: [], screenshots: [], checks: [], errors: [] };
socket.addEventListener("message", event => {
  const item = JSON.parse(event.data);
  if (item.method === "Runtime.exceptionThrown") report.errors.push(item.params.exceptionDetails.exception?.description || item.params.exceptionDetails.text);
  const call = pending.get(item.id); if (!call) return;
  pending.delete(item.id); clearTimeout(call.timer); item.error ? call.reject(new Error(item.error.message)) : call.resolve(item.result);
});
function cdp(method, params = {}) {
  return new Promise((resolve, reject) => { const id = ++next, timer = setTimeout(() => { pending.delete(id); reject(new Error("CDP timeout: " + method)); }, 20000); pending.set(id, { resolve, reject, timer }); socket.send(JSON.stringify({ id, method, params })); });
}
async function evaluate(expression) {
  const result = await cdp("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text);
  return result.result.value;
}
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
async function until(expression) { for (let i = 0; i < 180; i++) { if (await evaluate(expression)) return; await pause(100); } throw new Error("页面等待超时: " + expression); }
async function go(route, selector) { await evaluate(`location.hash=${JSON.stringify("#" + route)}`); await pause(150); await until(`!document.querySelector('.live-loading') && !!document.querySelector(${JSON.stringify(selector)})`); await evaluate("window.scrollTo(0,0)"); }
async function click(selector) { await evaluate(`(() => {const e=document.querySelector(${JSON.stringify(selector)});if(!e)throw new Error('找不到控件');e.click();})()`); }
async function fill(name, value, selector = '[data-form="training-wizard"]') { await evaluate(`(() => {const f=document.querySelector(${JSON.stringify(selector)}),e=f.elements.namedItem(${JSON.stringify(name)});e.value=${JSON.stringify(value)};e.dispatchEvent(new Event('change',{bubbles:true}));})()`); }
async function capture(name) { await evaluate("document.getElementById('live-toast')?.remove()"); const result = await cdp("Page.captureScreenshot", { format: "png", captureBeyondViewport: false }); await writeFile(join(output, name), Buffer.from(result.data, "base64")); report.screenshots.push(name); }
try {
  await cdp("Page.enable"); await cdp("Runtime.enable"); await cdp("Network.enable"); await cdp("Network.setCacheDisabled", { cacheDisabled: true });
  await cdp("Emulation.setDeviceMetricsOverride", { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false });
  const run = Date.now();
  await cdp("Page.navigate", { url: fixture.url + "/?qa=stage13-1-" + run + "#/home" });
  await until(`document.readyState==='complete' && !!document.querySelector('script[src*="${fixture.cache_version || "stage13-1"}"]')`);
  await until("!!document.querySelector('[data-form=login]') || !!document.querySelector('.page-heading h1')");
  if (await evaluate("!!document.querySelector('[data-form=login]')")) {
    await evaluate(`(() => {const form=document.querySelector('[data-form=login]');form.elements.account.value=${JSON.stringify(login.account)};form.elements.password.value=${JSON.stringify(login.password)};form.requestSubmit();})()`);
  }
  await until("!!document.querySelector('.console-summary')");
  const routes = [["/home", ".console-summary"], ["/models", ".console-catalog"], ["/projects", ".console-catalog"], ["/datasets", ".table"], ["/datasets/new", "[data-form=dataset-import]"], ["/train/new", "[data-form=training-wizard]"], ...["overview", "metrics", "logs", "outputs"].map(tab => [`/runs/${fixture.job_id}?tab=${tab}`, ".tabs"]), ["/admin/users", ".table"], ...(["stage13-2", "stage13-3"].includes(fixture.cache_version) ? adminRoutes : [])];
  for (const width of [1440, 1024, 390]) {
    await cdp("Emulation.setDeviceMetricsOverride", { width, height: 1000, deviceScaleFactor: 1, mobile: width < 600 });
    for (const [route, selector] of routes) {
      await go(route, selector);
      const check = await evaluate("(() => ({overflow:document.documentElement.scrollWidth>innerWidth,minimumFont:Math.min(...[...document.querySelectorAll('.page-heading h1,button,input,select,th,td,label,.chip,.console-stepper strong')].filter(e=>e.getClientRects().length).map(e=>parseFloat(getComputedStyle(e).fontSize)))}))()");
      report.layouts.push({ route, width, ...check }); assert.equal(check.overflow, false, route + " has overflow"); assert.ok(check.minimumFont >= 14, route + " has small text");
      if ((route === "/home" || route === "/models" || route === "/train/new") && width !== 1024) await capture(route.slice(1).replaceAll("/", "-") + "-" + width + ".png");
    }
  }
  await cdp("Emulation.setDeviceMetricsOverride", { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false });
  await go("/train/new", "[data-form=training-wizard]");
  const runName = "浏览器真实创建的训练 " + run;
  await fill("task_type", "text_classification"); await fill("name", runName);
  await click('[data-action="wizard-next"]'); await until("!!document.querySelector('[data-wizard-dataset]')");
  await evaluate("(() => {const e=document.querySelector('[data-wizard-dataset]');e.selectedIndex=1;e.dispatchEvent(new Event('change',{bubbles:true}));})()");
  await click('[data-action="wizard-preview"]'); await until("!!document.querySelector('.template-preview')");
  await click('[data-action="wizard-next"]'); await until("!!document.querySelector('[name=epochs]')");
  await fill("epochs", "2"); await capture("wizard-parameters-1440.png");
  await click('[data-action="wizard-back"]'); await until("!!document.querySelector('[data-wizard-dataset]')");
  assert.ok(await evaluate("!!document.querySelector('[data-wizard-dataset]').value"));
  await click('[data-action="wizard-next"]'); await until("!!document.querySelector('[name=epochs]')"); assert.equal(await evaluate("document.querySelector('[name=epochs]').value"), "2");
  await click('[data-action="wizard-next"]'); await until("!!document.querySelector('[name=intent][value=draft]')");
  await click('[name=intent][value=draft]'); await until("!document.querySelector('.live-loading') && !!document.querySelector('.console-detail-grid')");
  assert.equal(await evaluate("document.querySelector('.page-heading h1').textContent"), runName); report.checks.push("四步向导、样本预览、切步保留、草稿保存");
  await click('a[href*="/train/new?copy="]'); await until("!!document.querySelector('[name=name]')"); assert.ok((await evaluate("document.querySelector('[name=name]').value")).endsWith(" · 副本")); report.checks.push("复制配置生成独立向导草稿");
  const datasetName = "浏览器导入的数据 " + run;
  await go("/datasets/new", "[data-form=dataset-import]"); await fill("name", datasetName, '[data-form="dataset-import"]');
  const dom = await cdp("DOM.getDocument"); const fileInput = await cdp("DOM.querySelector", { nodeId: dom.root.nodeId, selector: "[data-import-file]" });
  await cdp("DOM.setFileInputFiles", { nodeId: fileInput.nodeId, files: [join(root, "import.csv")] });
  await until("document.querySelector('.console-upload-zone').textContent.includes('import.csv')"); await click('[data-action="import-preview"]'); await until("!!document.querySelector('.live-table')"); await capture("dataset-preview-1440.png");
  await click('[data-form="dataset-import"] [type=submit]'); await until(`!document.querySelector('.live-loading') && document.querySelector('.page-heading h1')?.textContent===${JSON.stringify(datasetName)}`);
  assert.ok(await evaluate("document.body.textContent.includes('import.csv')")); report.checks.push("真实文件校验、预览、上传与版本登记");
  await go("/home", ".console-summary"); await evaluate("document.querySelector('.sidebar-nav').scrollTop=120");
  const scroll = await evaluate("document.querySelector('.sidebar-nav').scrollTop"); await go("/models", ".console-catalog"); assert.equal(await evaluate("document.querySelector('.sidebar-nav').scrollTop"), scroll);
  await click('[data-action="collapse-sidebar"]'); assert.equal(await evaluate("[...document.querySelectorAll('.sidebar .nav-label')].some(e=>e.getClientRects().length)"), false);
  await click('[data-action="collapse-sidebar"]'); assert.equal(await evaluate("document.querySelector('.sidebar-nav').scrollTop"), scroll); report.checks.push("菜单滚动与收窄恢复");
  if (["stage13-2", "stage13-3"].includes(fixture.cache_version)) await adminFlows({ fixture, login, run, go, fill, click, wait: until, capture, evaluate, report });
  if (fixture.cache_version === "stage13-3") {
    const data = await dataFlows({ fixture, run, go, fill, click, wait: until, capture, evaluate, report });
    for (const width of [1440, 1024, 390]) {
      await cdp("Emulation.setDeviceMetricsOverride", { width, height: 1000, deviceScaleFactor: 1, mobile: width < 600 });
      for (const [route, selector] of data.routes) {
        await go(route, selector);
        const check = await evaluate("(()=>({overflow:document.documentElement.scrollWidth>innerWidth,wrappedHeadings:[...document.querySelectorAll('.data-candidate-heading h2')].some(e=>e.getBoundingClientRect().height>parseFloat(getComputedStyle(e).lineHeight)*1.1),minimumFont:Math.min(...[...document.querySelectorAll('button,input,select,th,td,label,.chip,.annotation-text')].filter(e=>e.getClientRects().length).map(e=>parseFloat(getComputedStyle(e).fontSize)))}))()");
        report.layouts.push({ route, width, ...check }); assert.equal(check.overflow, false, route + " overflow"); assert.equal(check.wrappedHeadings, false, route + " 标题换行"); assert.ok(check.minimumFont >= 14);
        if (width !== 1024 && (route.startsWith('/annotation/') || route === data.augmentationRoute)) await capture((route.startsWith('/annotation/') ? 'annotation-workbench' : 'augmentation-workbench') + '-' + width + '.png');
      }
    }
    await writeFile(join(root, "data-fixture.json"), JSON.stringify(data, null, 2));
  }
  assert.equal(report.errors.length, 0); report.success = true;
  console.log(JSON.stringify({ success: true, layouts: report.layouts.length, flows: report.checks.length, screenshots: report.screenshots.length, errors: 0 }));
} finally { await writeFile(join(output, "browser-audit.json"), JSON.stringify(report, null, 2)); socket.close(); }
