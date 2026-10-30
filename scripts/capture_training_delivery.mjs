import { copyFile, mkdir, readFile, writeFile } from "node:fs/promises";
import { resolve, join } from "node:path";

const root = "D:/model-training-demo/backend-runtime/training-flow-20261029-01";
const initial = JSON.parse(await readFile(join(root, "verification.json"), "utf8"));
const qwen = JSON.parse(await readFile(join(root, "verification-qwen.json"), "utf8"));
const output = resolve("docs/stage7/previews"); await mkdir(output, { recursive: true });
const targets = await (await fetch("http://127.0.0.1:9222/json")).json();
const socket = new WebSocket(targets.find(item => item.type === "page").webSocketDebuggerUrl);
await new Promise(resolve => socket.addEventListener("open", resolve, { once: true }));
const pending = new Map(); let id = 0;
socket.addEventListener("message", event => { const m = JSON.parse(event.data); if (pending.has(m.id)) { const pair = pending.get(m.id); pending.delete(m.id); m.error ? pair[1](m.error) : pair[0](m.result); } });
const cdp = (method, params = {}) => new Promise((resolve, reject) => { pending.set(++id, [resolve, reject]); socket.send(JSON.stringify({ id, method, params })); });
const evaluate = async expression => (await cdp("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true })).result.value;
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
try {
  await cdp("Emulation.setDeviceMetricsOverride", { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false });
  const pages = [["resources", "/admin/resources"], ["training", "/runs/" + initial.jobs.find(j => j.kind === "train").id], ["qwen", "/runs/" + qwen.jobs.find(j => j.kind === "train").id]];
  for (const [name, path] of pages) {
    await cdp("Page.navigate", { url: "http://127.0.0.1:8001/?delivery=" + Date.now() + "#" + path });
    for (let i = 0; i < 100; i++) { if (await evaluate("!!document.querySelector('.page-heading h1') && !document.querySelector('.live-loading')")) break; await pause(100); }
    await pause(200);
    const image = await cdp("Page.captureScreenshot", { format: "png", captureBeyondViewport: false });
    await writeFile(join(output, name + ".png"), Buffer.from(image.data, "base64"));
  }
  await copyFile(join(root, "browser/training-dialog-mobile.png"), join(output, "training-mobile.png"));
  await copyFile(join(root, "browser/browser-audit.json"), join(output, "browser-audit.json"));
  console.log(JSON.stringify({ screenshots: pages.length + 1, output }));
} finally { socket.close(); }
