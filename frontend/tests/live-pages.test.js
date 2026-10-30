import test from "node:test";
import assert from "node:assert/strict";
import { renderAuth } from "../live/pages/auth.js";
import { renderAssets, renderAssetDetail } from "../live/pages/assets.js";
import { renderHome, renderPending, renderSpace } from "../live/pages/overview.js";
import { renderDialog } from "../live/dialogs.js";
import { renderUsers } from "../live/pages/admin.js";
import { loadPreferences, savePreferences } from "../live/preferences.js";

const workspace = { id: "wsp_1", name: "研发组", owner_id: "usr_1" };
const session = { user: { id: "usr_1", display_name: "甲方", is_admin: true }, access: { actions: ["workspaces.create"] } };
const ctx = { workspace, workspaces: [workspace], session, templates: [{ id: "text-classifier-v1", task_type: "text_classification", name: "文本分类" }], groups: [], q: "", access: { actions: ["models.write", "datasets.write", "members.manage"], quota: {}, role: "admin" }, data: { data: [] } };

test("真实登录无默认密码或演示身份，首次设置可在页面完成", () => {
  const login = renderAuth({ initialized: true });
  assert.ok(login.includes('name="account"')); assert.ok(!login.includes('type="email"'));
  assert.ok(!login.includes("演示账号") && !login.includes("Admin123"));
  const setup = renderAuth({ initialized: false, enabled: true });
  assert.ok(setup.includes("设置管理员") && setup.includes('name="workspace_name"'));
  assert.ok(setup.includes('minlength="12"'));
  assert.ok(renderAuth({ initialized: false, enabled: false }).includes("请联系管理员"));
});

test("模型页面使用真实记录并转义，写入按钮受权限控制", () => {
  const item = { id: "mdl_1", name: '<script>alert("x")</script>', task_type: "text_classification", trainer_id: "text-classifier-v1", source_ref: "team/model" };
  const html = renderAssets("models", { ...ctx, data: { data: [item] } });
  assert.ok(html.includes("&lt;script&gt;") && !html.includes("<script>"));
  assert.ok(html.includes("新增模型") && html.includes("team/model"));
  const readonly = renderAssets("models", { ...ctx, access: { actions: ["models.read"] }, data: { data: [item] } });
  assert.ok(!readonly.includes("新增模型") && !readonly.includes('data-action="edit-asset"'));
});

test("数据详情使用服务端版本与样本，图像数据支持导入", () => {
  const item = { id: "dat_1", name: "样本", task_type: "text_classification" };
  const html = renderAssetDetail("datasets", { ...ctx, data: { item, versions: { data: [{ id: "dvr_1", number: 2, filename: "real.csv", format: "csv", sample_count: 7, size_bytes: 512, status: "needs_annotation" }] }, preview: { total: 7, samples: [{ text: "<b>数据</b>", label: "" }] } } });
  assert.ok(html.includes("real.csv") && html.includes("data-status=\"待标注\""));
  assert.ok(html.includes("&lt;b&gt;数据&lt;/b&gt;") && !html.includes("<b>数据</b>"));
  const image = renderAssetDetail("datasets", { ...ctx, data: { item: { ...item, task_type: "image_classification" }, versions: { data: [] } } });
  assert.match(image, /href="#\/datasets\/new\?dataset=dat_1">导入版本/);
});

test("新增和权限设置均通过弹窗，待接入页面没有模拟指标", () => {
  for (const kind of ["workspace-new", "model-new", "dataset-new", "user-new", "user-edit", "group-new", "group-edit", "member", "toggle-user", "examples"]) {
    const html = renderDialog({ kind, item: {} }, ctx);
    assert.ok(html.includes('role="dialog"') && html.includes('data-form="dialog"'), kind);
    assert.ok(!html.includes('<h2 id="live-dialog-title"></h2>'), kind);
  }
  assert.ok(renderPending("/runs").includes("训练执行待接入"));
  assert.ok(!renderPending("/runs").includes("accuracy"));
  assert.ok(renderHome({ ...ctx, data: {} }).includes("添加示例资产"));
  assert.ok(renderSpace({ ...ctx, data: { members: { data: [] } } }).includes("空间成员"));
});

test("浏览器偏好仅保存布局和选中空间，全部分组默认展开", () => {
  const storage = { value: null, getItem() { return this.value; }, setItem(key, value) { this.value = value; } };
  const initial = loadPreferences(storage); assert.ok(Object.values(initial.navOpen).every(Boolean));
  savePreferences(storage, { ...initial, workspaceId: "wsp_1", csrf: "secret", users: [{ password: "secret" }] });
  assert.ok(!storage.value.includes("secret") && !storage.value.includes("users"));
  storage.value = "broken"; assert.equal(loadPreferences(storage).workspaceId, "");
});

test("无法读取用户组时编辑用户仍保留当前分组", () => {
  const item = { id: "usr_2", account: "member", display_name: "成员", group_id: "grp_restricted", allow_actions: [], deny_actions: [], quota: {} };
  const html = renderDialog({ kind: "user-edit", item }, { ...ctx, groups: [] });
  assert.ok(html.includes('value="grp_restricted" selected'), "缺少组列表也不能默认清空已有分组");
  assert.ok(renderUsers({ ...ctx, data: { data: [item] }, groups: [], tab: "users" }).includes("受限用户组"));
});
