// 仅操作 8001 独立验收服务；所有账号、文件和截图保存在 D 盘。
import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import { join, resolve, sep } from "node:path";
import { randomUUID } from "node:crypto";

const qaRoot = resolve(process.env.LIVE_QA_ROOT || "D:/model-training-demo/backend-runtime/web-qa-20261028");
assert.ok(qaRoot.toLowerCase().startsWith((resolve("D:/model-training-demo/backend-runtime") + sep).toLowerCase()), "验收文件必须在 D 盘后端运行目录内");
const origin = "http://127.0.0.1:8001";
const output = { checks: [], responsive: [], screenshots: [], exceptions: [] };
const targets = await (await fetch("http://127.0.0.1:9222/json")).json();
const target = targets.find(item => item.type === "page" && item.url.startsWith(origin));
assert.ok(target, "未找到独立验收标签页");
const socket = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve, reject) => { socket.addEventListener("open", resolve, { once: true }); socket.addEventListener("error", reject, { once: true }); });
let seq = 0;
const pending = new Map();
socket.addEventListener("message", event => {
  const message = JSON.parse(event.data);
  if (message.method === "Runtime.exceptionThrown") output.exceptions.push(message.params.exceptionDetails.text);
  const call = pending.get(message.id);
  if (!call) return;
  pending.delete(message.id); clearTimeout(call.timer);
  message.error ? call.reject(new Error(message.error.message)) : call.resolve(message.result);
});
const cdp = (method, params = {}) => new Promise((resolve, reject) => {
  const id = ++seq;
  const timer = setTimeout(() => { pending.delete(id); reject(new Error(`CDP 超时：${method}`)); }, 20000);
  pending.set(id, { resolve, reject, timer }); socket.send(JSON.stringify({ id, method, params }));
});
const evaluate = async expression => {
  const result = await cdp("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.text);
  return result.result.value;
};
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
async function until(expression, label) {
  const deadline = Date.now() + 20000;
  while (Date.now() < deadline) { if (await evaluate(expression)) return; await pause(80); }
  throw new Error(`等待失败：${label}`);
}
async function go(route) {
  await evaluate(`location.hash=${JSON.stringify(`#${route}`)}`); await pause(100);
  await until(`!document.querySelector('.live-loading') && !!document.querySelector('.page-heading h1')`, route);
  await evaluate("window.scrollTo(0,0)");
}
async function click(selector) {
  await evaluate(`(() => { const element=document.querySelector(${JSON.stringify(selector)}); if(!element) throw new Error('missing control'); element.click(); })()`);
}
async function fill(values, selector = '[data-form="dialog"]') {
  await evaluate(`(() => { const form=document.querySelector(${JSON.stringify(selector)}); for(const [key,value] of Object.entries(${JSON.stringify(values)})){ const input=form.elements.namedItem(key); input.value=value; input.dispatchEvent(new Event('change',{bubbles:true})); } })()`);
}
async function submit(selector = '[data-form="dialog"]') {
  await evaluate(`document.querySelector(${JSON.stringify(selector)}).requestSubmit()`);
}
async function saved() { await until(`!document.querySelector('[role=dialog]') && !document.querySelector('.live-loading')`, "保存完成"); }
async function modal(kind) {
  await click(`[data-action="modal"][data-id="${kind}"]`); await until("!!document.querySelector('[role=dialog]')", kind);
  assert.equal(await evaluate("!!document.getElementById('live-toast')"), false, "上次提示不能遮挡新弹窗");
}
async function capture(name) {
  const { data } = await cdp("Page.captureScreenshot", { format: "png", captureBeyondViewport: false });
  const path = join(qaRoot, "previews", `${name}.png`); await writeFile(path, Buffer.from(data, "base64")); output.screenshots.push(path);
}
async function attach(path) {
  const { root } = await cdp("DOM.getDocument");
  const { nodeId } = await cdp("DOM.querySelector", { nodeId: root.nodeId, selector: "#version-file" });
  await cdp("DOM.setFileInputFiles", { nodeId, files: [path] });
}
const apiRead = path => evaluate(`fetch('/api/v1'+${JSON.stringify(path)}).then(r=>r.json())`);
const check = (name, details = true) => output.checks.push({ name, details });
const password = `QA-${randomUUID()}`;

try {
  await mkdir(join(qaRoot, "previews"), { recursive: true });
  await cdp("Page.enable"); await cdp("Runtime.enable");
  await cdp("Emulation.setDeviceMetricsOverride", { width: 1440, height: 960, deviceScaleFactor: 1, mobile: false });
  await cdp("Page.navigate", { url: `${origin}/` });
  await until("!!document.querySelector('[data-form=setup]')", "首次设置页");
  await capture("setup-desktop");
  await fill({ account: "qaadmin", display_name: "产品验收", workspace_name: "研发验证", password, confirm: password }, '[data-form="setup"]');
  await submit('[data-form="setup"]');
  await until("document.querySelector('.topbar-user')?.textContent==='产品验收' && !document.querySelector('.live-loading')", "首次设置并进入");
  const workspaceId = await evaluate("document.querySelector('[data-workspace-select]').value");
  assert.ok(workspaceId.startsWith("wsp_")); check("设置管理员、登录并创建真实空间");

  await go("/admin/users?tab=groups"); await modal("group-new");
  await fill({ name: "研发组", gpu_count: 2, concurrent_jobs: 3, storage_gib: 50 });
  await evaluate(`document.querySelectorAll('[name=allow_actions]').forEach(input=>{input.checked=!['users.manage','groups.manage'].includes(input.value)})`);
  await capture("group-dialog-desktop"); await submit(); await saved();
  assert.ok(await evaluate("document.querySelector('.table').textContent.includes('研发组')")); check("真实用户组与资源上限");
  await go("/admin/users"); await modal("user-new");
  await fill({ account: "qadev", display_name: "开发成员", password, gpu_count: 1, concurrent_jobs: 2 });
  await evaluate(`document.querySelector('[name=group_id]').value=[...document.querySelector('[name=group_id]').options].find(item=>item.textContent==='研发组').value;document.querySelector('[name=deny_actions][value="models.write"]').checked=true`);
  await submit(); await saved(); check("创建真实用户、个人上限及显式禁用");
  await capture("users-desktop");
  await go("/space"); await modal("member"); await fill({ account: "qadev", role: "viewer" }); await submit(); await saved();
  assert.ok(await evaluate("document.querySelector('.table').textContent.includes('查看者')")); check("已有账号加入空间并设置角色");

  await go("/home"); await modal("examples"); await submit(); await saved();
  const models = await apiRead(`/workspaces/${workspaceId}/models`), datasets = await apiRead(`/workspaces/${workspaceId}/datasets`);
  assert.equal(models.pagination.total, 3); assert.equal(datasets.pagination.total, 2);
  await modal("examples"); await submit(); await saved();
  assert.equal((await apiRead(`/workspaces/${workspaceId}/models`)).pagination.total, 3);
  check("示例资产真实持久化，重复添加保持数量"); await capture("home-desktop");

  await go("/models"); await modal("model-new"); await fill({ name: "自定义分类器", source_ref: "team/custom-classifier" }); await submit(); await saved();
  const modelId = await evaluate("location.hash.split('/')[2]");
  await modal("model-version"); await fill({ version: "v1.0", source_ref: "team/custom-classifier@commit1" }); await submit(); await saved();
  await click('[data-action="edit-asset"]'); await fill({ name: "项目分类模型", description: "反馈分类试验" }); await submit(); await saved();
  assert.equal((await apiRead(`/workspaces/${workspaceId}/models/${modelId}`)).data.revision, 2);
  check("模型登记、来源版本及并发 revision 更新"); await capture("model-detail-desktop");

  await go("/datasets"); await modal("dataset-new"); await fill({ name: "补充反馈" }); await submit(); await saved();
  const datasetId = await evaluate("location.hash.split('/')[2]");
  const invalid = join(qaRoot, "files/invalid.csv"), valid = join(qaRoot, "files/train.csv"), second = join(qaRoot, "files/train-v2.csv");
  await writeFile(invalid, "wrong,label\na,b\n");
  await writeFile(valid, "text,label\n操作简单,正向\n一条未标注反馈,\n<img src=x onerror=window.qaXss=true>,负向\n");
  await writeFile(second, "text,label\n操作简单,正向\n一条已标注反馈,负向\n上传完成,正向\n");
  await modal("dataset-version"); await attach(invalid); await submit();
  await until("!!document.querySelector('[data-modal-error]:not([hidden])') && !document.querySelector('[data-form=dialog] [type=submit]').disabled", "错误文件反馈");
  assert.equal((await apiRead(`/workspaces/${workspaceId}/datasets/${datasetId}/versions`)).pagination.total, 0);
  assert.equal(await evaluate("document.querySelector('#version-file').files[0].name"), "invalid.csv");
  check("上传错误保持表单，不生成可用版本");
  await attach(valid); await submit(); await saved();
  let versions = (await apiRead(`/workspaces/${workspaceId}/datasets/${datasetId}/versions`)).data;
  assert.equal(versions[0].sample_count, 3); assert.equal(versions[0].status, "needs_annotation");
  await click('[data-action="preview"]'); await until("!!document.getElementById('samples')", "样本预览");
  assert.equal(await evaluate("!!window.qaXss || !!document.querySelector('.live-sample img')"), false);
  await evaluate("window.scrollTo(0,0)"); await capture("dataset-detail-desktop");
  check("真实 CSV 统计、待标注状态、转义样本预览");
  await cdp("Page.reload", { ignoreCache: true });
  await until("!!document.querySelector('[data-action=preview]') && !document.querySelector('.live-loading')", "刷新持久化");
  await modal("dataset-version"); await attach(second); await submit(); await saved();
  versions = (await apiRead(`/workspaces/${workspaceId}/datasets/${datasetId}/versions`)).data;
  assert.equal(versions.length, 2); assert.equal(versions[0].status, "needs_annotation"); assert.equal(versions[1].status, "available");
  const original = await apiRead(`/workspaces/${workspaceId}/datasets/${datasetId}/versions/${versions[0].id}/preview`);
  assert.equal(original.data.samples[1].label, ""); check("刷新与不可变历史版本");
  await evaluate("document.querySelector('.badge').focus()");
  await until("!document.getElementById('status-tooltip').hidden", "状态焦点提示");
  assert.equal(await evaluate("getComputedStyle(document.querySelector('.table .status-label')).display"), "none"); check("列表状态只显示符号且焦点可读文字");

  const sft = datasets.data.find(item => item.task_type === "llm_sft");
  await go(`/datasets/${sft.id}`); await click('[data-action="preview"]'); await until("!!document.getElementById('samples')", "JSONL 预览");
  assert.ok(await evaluate("document.querySelector('#samples').nextElementSibling.textContent.includes('instruction')")); check("JSONL 真实导入与预览");
  await go("/admin/audit"); assert.ok(await evaluate("document.querySelector('.table').textContent.includes('导入数据版本')")); check("真实操作审计");

  await go("/home"); await evaluate("document.querySelector('.sidebar-nav').scrollTop=180");
  const before = await evaluate("document.querySelector('.sidebar-nav').scrollTop");
  await go("/admin/users"); const after = await evaluate("document.querySelector('.sidebar-nav').scrollTop");
  await click('[data-action="collapse-sidebar"]');
  assert.equal(await evaluate("getComputedStyle(document.querySelector('.sidebar .nav-label')).display"), "none");
  await click('[data-action="collapse-sidebar"]');
  assert.equal(await evaluate("document.querySelector('.sidebar-nav').scrollTop"), before);
  assert.equal(after, before); check("菜单切换、折叠与滚动保留", { before, after });

  for (const width of [1440, 1024, 390]) {
    await cdp("Emulation.setDeviceMetricsOverride", { width, height: 960, deviceScaleFactor: 1, mobile: width < 600 });
    for (const route of ["/home", "/space", "/models", "/datasets", `/datasets/${datasetId}`, "/admin/users", "/admin/users?tab=groups", "/admin/audit", "/runs"]) {
      await go(route);
      const metrics = await evaluate(`({width:document.documentElement.scrollWidth,heading:document.querySelector('.page-heading h1')?.textContent,small:[...document.querySelectorAll('.content span,.content td,.content th,.content button,.content label')].filter(el=>el.getClientRects().length&&parseFloat(getComputedStyle(el).fontSize)<14).length})`);
      assert.ok(metrics.width <= width, `${route} overflow at ${width}: ${metrics.width}`); assert.equal(metrics.small, 0);
      output.responsive.push({ width, route, ...metrics });
    }
    await go("/admin/users"); await modal("user-new");
    const modalMetrics = await evaluate("({width:document.querySelector('[role=dialog]').getBoundingClientRect().width,bodyWidth:document.documentElement.scrollWidth,height:innerHeight,footer:document.querySelector('.modal-footer').getBoundingClientRect().bottom,inert:document.querySelector('#shell').inert})");
    assert.ok(modalMetrics.width <= width && modalMetrics.bodyWidth <= width && modalMetrics.footer <= 960 && modalMetrics.inert);
    output.responsive.push({ width, modal: modalMetrics });
    if (width === 390) await capture("user-dialog-mobile");
    await cdp("Input.dispatchKeyEvent", { type: "keyDown", key: "Escape", code: "Escape" });
    await until("!document.querySelector('[role=dialog]')", "ESC 关闭弹窗");
  }
  await cdp("Emulation.setDeviceMetricsOverride", { width: 1440, height: 960, deviceScaleFactor: 1, mobile: false });
  await click('[data-action="logout"]'); await until("!!document.querySelector('[data-form=login]')", "退出登录");
  await fill({ account: "qadev", password }, '[data-form="login"]'); await submit('[data-form="login"]');
  await until("document.querySelector('.topbar-user')?.textContent==='开发成员' && !document.querySelector('.live-loading')", "成员登录");
  assert.equal(await evaluate("!!document.querySelector('.nav-divider')"), false);
  await go("/models"); assert.equal(await evaluate("!!document.querySelector('[data-id=model-new]')"), false);
  await go("/datasets"); assert.equal(await evaluate("!!document.querySelector('[data-id=dataset-new]')"), false);
  await go("/admin/users"); assert.equal(await evaluate("document.querySelector('.page-heading h1').textContent"), "无权访问");
  const access = (await apiRead(`/workspaces/${workspaceId}/access`)).data;
  assert.equal(access.quota.gpu_count, 1); assert.ok(!access.actions.includes("models.write"));
  check("普通成员、查看者和显式禁用均不能越权");
  assert.deepEqual(output.exceptions, []);
  output.success = true;
} catch (error) {
  output.success = false; output.failure = error.message;
  output.page = await evaluate("({url:location.href,heading:document.querySelector('.page-heading h1')?.textContent,error:document.querySelector('[data-modal-error]:not([hidden]),[data-auth-error]:not([hidden])')?.textContent})").catch(() => ({}));
  await capture("failure").catch(() => {}); process.exitCode = 1;
} finally {
  await writeFile(join(qaRoot, "browser-audit.json"), JSON.stringify(output, null, 2));
  console.log(JSON.stringify({ success: output.success, checks: output.checks.length, responsive: output.responsive.length, failure: output.failure, page: output.page, report: join(qaRoot, "browser-audit.json") }));
  socket.close();
}
