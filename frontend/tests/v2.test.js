import test from "node:test";
import assert from "node:assert/strict";
import { SEED_STATE, TASKS } from "../js/data.js";
import { addGroup, addNode, addUser, effectiveAccess, getState, probeNode, resetDemo, setUserAccess } from "../js/state.js";
import { shell } from "../js/ui.js";
import { renderModal } from "../js/modals.js";
import { renderAuth } from "../js/pages/auth.js";
import { renderSpace, renderMonitor } from "../js/pages/workspace.js";
import { renderAnnotation, renderAugmentation } from "../js/pages/data-tools.js";
import { renderEvaluation } from "../js/pages/evaluation.js";
import { renderApiKeys } from "../js/pages/api-keys.js";
import { renderResources, JOIN_COMMAND } from "../js/pages/admin-resources.js";
import { renderUsers } from "../js/pages/admin-access.js";
import { renderStats, renderAdminData, renderAdminModels, renderAdminJobs, renderSettings } from "../js/pages/admin-overview.js";

test("登录注册与两级菜单按角色呈现", () => {
  assert.match(renderAuth("login"), /演示账号/);
  assert.match(renderAuth("register"), /创建账号/);
  const userHtml = shell("/home", "内容", "工作台", SEED_STATE.users[1]);
  const adminHtml = shell("/admin/stats", "内容", "统计面板", SEED_STATE.users[0]);
  for (const label of ["概览", "用户空间", "在线标注", "数据增强", "模型评估", "API KEY管理"]) assert.ok(userHtml.includes(label));
  assert.doesNotMatch(userHtml, /统计面板/);
  assert.match(adminHtml, /统计面板/);
  assert.match(adminHtml, /系统设置/);
  const viewerHtml = shell("/home", "内容", "工作台", SEED_STATE.users[3], {}, effectiveAccess(SEED_STATE.users[3], SEED_STATE).permissions);
  assert.doesNotMatch(viewerHtml, /训练项目|在线标注|API KEY管理/);
  assert.match(viewerHtml, /资源监控/);
});

test("用户组为基础、个人禁用优先且配额取较小值", () => {
  resetDemo();
  const user = getState().users.find(item => item.id === "user-lin");
  assert.ok(effectiveAccess(user).permissions.has("services.deploy"));
  setUserAccess(user.id, { modes: { "services.deploy": "deny", "datasets.read": "allow" }, gpu: 1, jobs: 2 });
  const access = effectiveAccess(user);
  assert.equal(access.permissions.has("services.deploy"), false);
  assert.equal(access.permissions.has("datasets.read"), true);
  assert.deepEqual(access.quota, { gpu: 1, jobs: 2 });
  const group = addGroup({ name: "测试组", permissions: ["datasets.read"], gpu: 3, jobs: 5 });
  setUserAccess(user.id, { groupId: group.id, modes: { "train.submit": "allow" }, gpu: 2, jobs: 6 });
  assert.equal(effectiveAccess(user).permissions.has("train.submit"), true);
  assert.deepEqual(effectiveAccess(user).quota, { gpu: 2, jobs: 5 });
  resetDemo();
});

test("GPU 接入是可复制的非执行示意，并可模拟探测", () => {
  assert.match(JOIN_COMMAND, /<平台地址>/);
  assert.doesNotMatch(JOIN_COMMAND, /curl|powershell|bash/i);
  resetDemo();
  const node = addNode({ name: "测试节点", address: "gpu-test", profile: "a100" });
  assert.equal(node.status, "待探测");
  probeNode(node.id);
  assert.equal(getState().nodes.find(item => item.id === node.id).status, "已接入");
  assert.match(renderResources(getState(), { resourceTab: "connect" }), /不可执行/);
  resetDemo();
});

test("新业务页面均有可用内容，Qwen 预置模型进入任务目录", () => {
  const state = structuredClone(SEED_STATE), user = state.users[1];
  const pages = [renderSpace(state, user), renderMonitor(state), renderAnnotation(state), renderAugmentation(state), renderEvaluation(state, {}), renderApiKeys(state, user, {}), renderUsers(state, {}), renderStats(state), renderAdminData(state), renderAdminModels(state), renderAdminJobs(state), renderSettings(state)];
  pages.forEach((html, index) => assert.ok(html.length > 200, `新页面 ${index + 1} 内容不足`));
  assert.ok(TASKS.some(task => task.group === "大语言模型" && task.models.some(model => model.name === "Qwen2.5-0.5B-Instruct")));
  assert.ok(TASKS.find(task => task.id === "text-classification").models.some(model => model.id === "qwen25-05b"));
});

test("菜单首次全部展开，页面副标题不再显示", () => {
  const html = shell("/home", "内容", "工作台", SEED_STATE.users[1]);
  assert.equal((html.match(/class="nav-section open"/g) || []).length, 5);
  assert.doesNotMatch(html, /Model Studio/);
  assert.doesNotMatch(renderUsers(SEED_STATE), /组权限为基础，个人允许或禁用覆盖组结果/);
});

test("新增用户的角色与所选用户组保持一致", () => {
  resetDemo();
  const user = addUser({ name: "验收用户", account: "qa-viewer@example.test", groupId: "group-viewer", salt: "test", passwordHash: "test" });
  assert.equal(user.role, "只读");
  assert.equal(user.groupId, "group-viewer");
  setUserAccess(user.id, { groupId: "group-dev" });
  assert.equal(user.role, "开发者");
  resetDemo();
});

test("常规创建和配置使用弹窗，数据增强按类型显示方式", () => {
  const state = structuredClone(SEED_STATE);
  const page = renderUsers(state);
  assert.match(page, /data-modal="user-new"/);
  assert.doesNotMatch(page, /id="user-access-form"/);
  const html = renderModal({ kind: "augmentation-new" }, state, { augmentationDataset: "ds-intent" });
  const methodSelect = html.match(/<select class="select" name="method"[\s\S]*?<\/select>/)?.[0] || "";
  assert.match(methodSelect, /同义词替换/);
  assert.doesNotMatch(methodSelect, /水平翻转/);
  assert.match(renderModal({ kind: "user-access", id: "user-lin" }, state), /role="dialog"/);
});
