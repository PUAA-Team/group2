// 在已启动调试端口 9222 的本地 Chrome 中检查页面溢出和关键入口。
import { mkdir, writeFile } from "node:fs/promises";
import { join, resolve, sep } from "node:path";

const captureRoot = resolve("D:\\model-training-demo\\qa-browser-profile");
const captureDir = resolve(captureRoot, "captures", `stage3-${Date.now()}`);
const screenshots = [];
const saveScreenshots = process.argv.includes("--screenshots");
if (saveScreenshots) {
  if (!captureDir.startsWith(`${captureRoot}${sep}`)) throw new Error("截图目录超出隔离配置目录");
  await mkdir(captureDir, { recursive: true });
}
const targets = await (await fetch("http://127.0.0.1:9222/json")).json();
const page = targets.find(item => item.type === "page");
if (!page) throw new Error("未找到可检查的浏览器标签页");

const socket = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((resolve, reject) => { socket.addEventListener("open", resolve, { once: true }); socket.addEventListener("error", reject, { once: true }); });
let nextId = 1;
const pending = new Map();
socket.addEventListener("message", event => {
  const message = JSON.parse(event.data);
  if (!message.id || !pending.has(message.id)) return;
  const { resolve, reject } = pending.get(message.id);
  pending.delete(message.id);
  message.error ? reject(new Error(message.error.message)) : resolve(message.result);
});
const cdp = (method, params = {}) => new Promise((resolve, reject) => {
  const id = nextId++;
  pending.set(id, { resolve, reject });
  socket.send(JSON.stringify({ id, method, params }));
});
const evaluate = async expression => {
  const result = await cdp("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.text);
  return result.result.value;
};
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
const navigate = async route => { await cdp("Page.navigate", { url: `http://localhost:8765/?qa=${Date.now()}#${route}` }); await pause(250); };
const capture = async name => {
  if (!saveScreenshots) return;
  const { data } = await cdp("Page.captureScreenshot", { format: "png", captureBeyondViewport: false });
  const path = join(captureDir, `${name}.png`);
  await writeFile(path, Buffer.from(data, "base64"));
  screenshots.push(path);
};

await cdp("Page.enable");
await cdp("Runtime.enable");
await cdp("Emulation.setDeviceMetricsOverride", { width: 1280, height: 900, deviceScaleFactor: 1, mobile: false });
await evaluate("sessionStorage.removeItem('model-training-demo-session')");
await navigate("/login");
await capture("login-desktop");
const login = await evaluate("(() => { const button = document.querySelector('[data-action=demo-login][data-account=\"admin@example.test\"]'); if (!button) return false; button.click(); return true; })()");
await pause(250);
const output = { loginClicked: login, loggedIn: await evaluate("document.querySelector('.topbar-user')?.textContent === '平台管理员'"), checks: [], extraRoutes: [], screenshots };
await navigate("/home");
await capture("home-desktop");
output.menuInitial = await evaluate("({ open: document.querySelectorAll('.nav-section.open').length, stripe: getComputedStyle(document.querySelector('.nav-child.active')).borderLeftWidth, primary: getComputedStyle(document.querySelector('.btn-primary')).backgroundColor })");
await evaluate("document.querySelector('.sidebar-nav').scrollTop = 180");
const beforeRouteScroll = await evaluate("document.querySelector('.sidebar-nav').scrollTop");
await evaluate("location.hash = '#/admin/users'");
await pause(100);
const afterRouteScroll = await evaluate("document.querySelector('.sidebar-nav').scrollTop");
await evaluate("document.querySelector('[data-action=collapse-sidebar]').click()");
const collapsedOpen = await evaluate("document.querySelectorAll('.nav-section.open').length");
await evaluate("document.querySelector('[data-action=collapse-sidebar]').click()");
output.menuState = { beforeRouteScroll, afterRouteScroll, collapsedOpen, expandedOpen: await evaluate("document.querySelectorAll('.nav-section.open').length"), expandedScroll: await evaluate("document.querySelector('.sidebar-nav').scrollTop") };
await evaluate("document.querySelector('[data-action=open-modal][data-modal=user-new]').click()");
await capture("user-modal-desktop");
output.userModal = await evaluate("({ visible: !!document.querySelector('[role=dialog]'), inlineForm: !!document.querySelector('.content #user-new-form'), inputBorder: getComputedStyle(document.querySelector('#user-new-form .input')).borderTopWidth, selectAppearance: getComputedStyle(document.querySelector('#user-new-form .select')).appearance })");
await evaluate("document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))");
output.modalClosedByEscape = await evaluate("!document.querySelector('[role=dialog]')");
await evaluate("document.querySelector('[data-action=admin-users-tab][data-tab=groups]').click()");
await evaluate("document.querySelector('[data-action=open-modal][data-modal=group-new]').click()");
output.groupModal = await evaluate("!!document.querySelector('#group-new-form[role=dialog], [role=dialog] #group-new-form')");
await evaluate("document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))");
for (const width of [1280, 768, 390]) {
  await cdp("Emulation.setDeviceMetricsOverride", { width, height: 900, deviceScaleFactor: 1, mobile: width < 600 });
  for (const route of ["/home", "/datasets", "/train/new", "/models", "/admin/resources", "/admin/users"]) {
    await navigate(route);
    if (route === "/train/new" && width === 390) await capture("train-mobile");
    const result = await evaluate("({ title: document.title, pageWidth: document.documentElement.scrollWidth, heading: document.querySelector('h1')?.textContent, visible: !!document.querySelector('.content') })");
    output.checks.push({ width, route, ...result });
  }
}
await cdp("Emulation.setDeviceMetricsOverride", { width: 390, height: 844, deviceScaleFactor: 1, mobile: true });
await navigate("/admin/users");
await evaluate("document.querySelector('[data-action=open-modal][data-modal=user-new]').click()");
await capture("user-modal-mobile");
output.mobileModal = await evaluate("({ width: document.querySelector('.modal-panel').getBoundingClientRect().width, viewport: innerWidth, footerVisible: !!document.querySelector('.modal-footer button[type=submit]'), footerBottom: document.querySelector('.modal-footer').getBoundingClientRect().bottom, viewportHeight: innerHeight, overflow: document.documentElement.scrollWidth > innerWidth })");
await evaluate("document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))");
await cdp("Emulation.setDeviceMetricsOverride", { width: 1280, height: 900, deviceScaleFactor: 1, mobile: false });
for (const route of ["/space", "/monitor", "/annotation", "/augmentation", "/projects", "/runs", "/evaluation", "/services", "/api-keys", "/admin/stats", "/admin/data", "/admin/models", "/admin/jobs", "/admin/audit", "/admin/settings"]) {
  await navigate(route);
  output.extraRoutes.push({ route, heading: await evaluate("document.querySelector('h1')?.textContent") });
}
await navigate("/admin/resources");
await evaluate("document.querySelector('[data-action=resource-tab][data-tab=connect]')?.click()");
await pause(80);
await capture("gpu-connect-desktop");
output.gpuConnect = await evaluate("({command:document.querySelector('.join-command')?.textContent,warning:document.querySelector('.notice-warning')?.textContent})");
await evaluate("document.querySelector('[data-action=logout]')?.click()");
await pause(200);
output.afterLogout = await evaluate("({title:document.title,hasDemoButton:!!document.querySelector('[data-action=demo-login][data-account=\"lin@example.test\"]')})");
await evaluate("document.querySelector('[data-action=demo-login][data-account=\"lin@example.test\"]')?.click()");
await pause(300);
output.afterUserLogin = await evaluate("({title:document.title,user:document.querySelector('.topbar-user')?.textContent})");
await navigate("/admin/users");
output.normalUser = await evaluate("({title:document.title,heading:document.querySelector('h1')?.textContent,adminMenu:!!document.querySelector('.nav-divider')})");
socket.close();
console.log(JSON.stringify(output, null, 2));
const failures = output.checks.filter(item => item.pageWidth > item.width);
if (!output.loginClicked || !output.loggedIn || output.extraRoutes.some(item => !item.heading || item.heading === "页面不存在") || !output.normalUser.title.startsWith("无权访问") || output.normalUser.adminMenu) process.exitCode = 1;
if (output.menuInitial.open !== 5 || output.menuInitial.stripe !== "0px" || output.menuState.afterRouteScroll !== output.menuState.beforeRouteScroll || output.menuState.collapsedOpen !== 5 || output.menuState.expandedOpen !== 5 || output.menuState.expandedScroll !== output.menuState.beforeRouteScroll || !output.userModal.visible || output.userModal.inlineForm || output.userModal.inputBorder === "0px" || output.userModal.selectAppearance !== "none" || !output.modalClosedByEscape || !output.groupModal || output.mobileModal.width > output.mobileModal.viewport || !output.mobileModal.footerVisible || Math.abs(output.mobileModal.footerBottom - output.mobileModal.viewportHeight) > 2 || output.mobileModal.overflow) process.exitCode = 1;
if (failures.length) {
  console.error(`响应式溢出：${failures.map(item => `${item.width}px ${item.route} → ${item.pageWidth}px`).join("，")}`);
  process.exitCode = 1;
}
