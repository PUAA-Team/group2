import { mkdir, readFile, writeFile } from "node:fs/promises";
import { resolve, join } from "node:path";

const root = resolve(process.argv[2] || "D:/model-training-demo/backend-runtime/training-flow-20261029-01");
if (!root.toLowerCase().startsWith("d:\\model-training-demo\\")) throw new Error("浏览器验收必须保存至 D 盘");
const output = join(root, "browser"); await mkdir(output, { recursive: true });
const login = JSON.parse(await readFile(join(root, "private-browser-login.json"), "utf8"));
const verification = JSON.parse(await readFile(join(root, "verification.json"), "utf8"));
const targets = await (await fetch("http://127.0.0.1:9222/json")).json();
const target = targets.find(item => item.type === "page");
const socket = new WebSocket(target.webSocketDebuggerUrl); const pending = new Map(); let nextId = 1;
await new Promise((resolve, reject) => { socket.addEventListener("open", resolve, { once: true }); socket.addEventListener("error", reject, { once: true }); });
const report = { errors: [], pages: [], dialogs: [], screenshots: [] };
socket.addEventListener("message", event => {
  const message = JSON.parse(event.data);
  if (message.method === "Runtime.exceptionThrown") report.errors.push(message.params.exceptionDetails.exception?.description || message.params.exceptionDetails.text);
  if (!message.id || !pending.has(message.id)) return;
  const { resolve, reject } = pending.get(message.id); pending.delete(message.id);
  message.error ? reject(new Error(message.error.message)) : resolve(message.result);
});
const cdp = (method, params = {}) => new Promise((resolve, reject) => { const id = nextId++; pending.set(id, { resolve, reject }); socket.send(JSON.stringify({ id, method, params })); });
const evaluate = async expression => {
  const result = await cdp("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text);
  return result.result.value;
};
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
async function wait(expression, timeout = 20000) {
  const end = Date.now() + timeout;
  while (Date.now() < end) { if (await evaluate(expression)) return; await pause(100); }
  throw new Error("页面等待超时: " + expression);
}
async function navigate(path) {
  await evaluate(`location.hash=${JSON.stringify("#" + path)}`);
  await wait(`!!document.querySelector('.page-heading h1') && !document.querySelector('.live-loading')`);
  await pause(150);
}
async function screenshot(name) {
  const { data } = await cdp("Page.captureScreenshot", { format: "png", captureBeyondViewport: false });
  await writeFile(join(output, name + ".png"), Buffer.from(data, "base64")); report.screenshots.push(name + ".png");
}
async function closeDialog() { await evaluate("document.querySelector('[role=dialog] [data-action=close-modal]')?.click()"); }
async function click(selector) { await evaluate(`document.querySelector(${JSON.stringify(selector)}).click()`); }
const dimensions = `(() => { const d=document.querySelector('[role=dialog]'); const r=d?.getBoundingClientRect(); return { heading:document.querySelector('h1')?.textContent, overflow:document.documentElement.scrollWidth>innerWidth, dialogWidth:r?.width, dialogBottom:r?.bottom, viewportWidth:innerWidth, viewportHeight:innerHeight, minimumText:Math.min(...[...document.querySelectorAll('.content h1,.content h2,.content label,.content button,.content td,.modal-panel label,.modal-panel input,.modal-panel select')].filter(e=>e.getClientRects().length).map(e=>parseFloat(getComputedStyle(e).fontSize))) }; })()`;
try {
  await cdp("Page.enable"); await cdp("Runtime.enable");
  await cdp("Emulation.setDeviceMetricsOverride", { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false });
  await cdp("Page.navigate", { url: "http://127.0.0.1:8001/#/login" });
  await wait("!!document.querySelector('[data-form=login]') || !!document.querySelector('.sidebar')");
  if (await evaluate("!!document.querySelector('[data-form=login]')")) {
    await evaluate(`(() => { const f=document.querySelector('[data-form=login]'); f.elements.account.value=${JSON.stringify(login.account)}; f.elements.password.value=${JSON.stringify(login.password)}; f.requestSubmit(); })()`);
  }
  await wait("!!document.querySelector('.page-heading h1')");
  const detail = "/runs/" + verification.jobs.find(job => job.kind === "train").id;
  const routes = ["/home", "/admin/resources", "/projects", "/runs", detail, "/evaluation", "/services", "/api-keys", "/admin/users"];
  for (const width of [1440, 1024, 390]) {
    await cdp("Emulation.setDeviceMetricsOverride", { width, height: 1000, deviceScaleFactor: 1, mobile: width < 600 });
    for (const path of routes) {
      await navigate(path); const state = await evaluate(dimensions); report.pages.push({ width, path, ...state });
      if (state.overflow || state.minimumText < 14) throw new Error("页面排版不通过: " + JSON.stringify({ width, path, ...state }));
      if (width === 1440 && ["/admin/resources", "/runs", detail].includes(path)) await screenshot(path === detail ? "training-detail-desktop" : path === "/runs" ? "training-list-desktop" : "resources-desktop");
    }
    await navigate("/runs"); await click('[data-action="workflow-new"]'); await wait("!!document.querySelector('[role=dialog]')");
    report.dialogs.push({ width, kind: "training", ...await evaluate(dimensions) });
    await screenshot(width < 600 ? "training-dialog-mobile" : width === 1440 ? "training-dialog-desktop" : "training-dialog-tablet");
    await closeDialog();
  }
  await cdp("Emulation.setDeviceMetricsOverride", { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false });
  await navigate("/admin/resources"); await click('[data-id="enroll-new"]'); await wait("!!document.querySelector('[role=dialog]')");
  await screenshot("enrollment-dialog-desktop");
  await evaluate("document.querySelector('[role=dialog] form').requestSubmit()");
  await wait("!!document.querySelector('.compute-command')");
  report.maskedCommand = await evaluate("document.querySelector('.compute-command').textContent.includes('<一次性接入码>') && !/enr_[a-f0-9]{32}\\.[A-Za-z0-9_-]+/.test(document.querySelector('.compute-command').textContent)");
  await screenshot("enrollment-command-desktop");
  if (!report.maskedCommand) throw new Error("接入命令未掩码显示");
  await navigate("/runs"); await click('[data-action="workflow-new"]');
  await evaluate("(() => {const f=document.querySelector('[role=dialog] form');f.elements.name.value='页面提交文本训练';const option=[...f.elements.model_version_id.options].find(o=>o.textContent.includes('文本')&&o.textContent.includes('base-v1'));f.elements.model_version_id.value=option.value;f.elements.model_version_id.dispatchEvent(new Event('change',{bubbles:true}));f.elements.epochs.value=2;f.elements.device_kind.value='cpu';f.requestSubmit();})()");
  await wait("!document.querySelector('[role=dialog]') && location.hash.includes('/runs/job_')");
  await wait("document.body.textContent.includes('执行结果')", 120000);
  report.createdFromUi = true; await screenshot("ui-submitted-training-result");
  await click('[data-action="workflow-deploy"]');
  await evaluate("(() => {const f=document.querySelector('[role=dialog] form');f.elements.name.value='页面部署文本服务';f.requestSubmit();})()");
  await wait("!document.querySelector('[role=dialog]') && !!document.querySelector('[data-action=workflow-invoke]')");
  await wait("!document.querySelector('[data-action=workflow-invoke]').disabled", 120000);
  await click('[data-action="workflow-invoke"]');
  await evaluate("(() => {const f=document.querySelector('[role=dialog] form');f.elements.text.value='操作简单上手很快';f.requestSubmit();})()");
  await wait("!!document.querySelector('.execution-output') && document.querySelector('.execution-output').textContent.includes('label')", 30000);
  report.invokedFromUi = true; await screenshot("ui-service-inference-result");
  await click('[data-action="workflow-stop"]'); await evaluate("document.querySelector('[role=dialog] form').requestSubmit()");
  await wait("document.body.textContent.includes('已停止') && !document.querySelector('[role=dialog]')", 30000);
  await navigate("/admin/resources");
  report.success = report.errors.length === 0;
  console.log(JSON.stringify({ success: report.success, pages: report.pages.length, dialogs: report.dialogs.length, errors: report.errors, createdFromUi: report.createdFromUi, invokedFromUi: report.invokedFromUi }));
} finally {
  await writeFile(join(output, "browser-audit.json"), JSON.stringify(report, null, 2)); socket.close();
}
