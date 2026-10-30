import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { badge, shell } from "../js/ui.js";
import { SEED_STATE } from "../js/data.js";
import { renderSpace } from "../js/pages/workspace.js";
import { renderModelList } from "../js/pages/models.js";
import { renderRunList, renderTrainWizard } from "../js/pages/training.js";
import { renderUsers } from "../js/pages/admin-access.js";

const read = path => readFileSync(new URL(path, import.meta.url), "utf8");

test("收窄侧栏隐藏已展开的二级菜单，保留分组状态", () => {
  const css = read("../styles/layout.css");
  assert.match(css, /\.sidebar-collapsed \.nav-section(?:\.open)? \.nav-children\s*\{[^}]*display:\s*none/);
  const html = shell("/runs", "内容", "训练任务", SEED_STATE.users[0], { sidebarCollapsed: true });
  assert.match(html, /sidebar-collapsed/);
  assert.equal((html.match(/class="nav-section open"/g) || []).length, 5);
});

test("侧栏可滚动但不显示长条滚动条", () => {
  const css = read("../styles/layout.css");
  assert.match(css, /scrollbar-width:\s*none/);
  assert.match(css, /\.sidebar-nav::-webkit-scrollbar\s*\{[^}]*display:\s*none/);
});

test("状态采用圆形符号且保留无障碍名称", () => {
  for (const label of ["运行中", "已完成", "排队中", "失败", "已停止", "已取消", "停用"]) {
    const html = badge(label);
    assert.match(html, /<circle /);
    assert.ok(html.includes(`aria-label="${label}"`));
    assert.match(html, /tabindex="0"/);
    assert.match(html, /class="status-label"/);
  }
});

test("控制台使用深青绿与适度圆角", () => {
  const css = read("../styles/base.css");
  assert.match(css, /--blue:\s*#276d62/);
  assert.match(css, /--radius-panel:\s*8px/);
  assert.match(css, /--radius-control:\s*6px/);
  assert.match(css, /\.table \.badge \.status-label[^}]*display:\s*none/s);
});

test("手机菜单重绘保留抽屉，关闭时不可被键盘选中", () => {
  const app = read("../js/app.js");
  const css = read("../styles/layout.css");
  assert.ok(app.includes('menuOpen && raw === currentRoute'), "同路由重绘需保留抽屉状态");
  assert.ok(app.includes('ui.sidebarCollapsed && window.innerWidth >= 1024'), "手机分组切换不触发桌面展开");
  assert.match(css, /\.sidebar,\.sidebar-collapsed \.sidebar\s*\{[^}]*visibility:\s*hidden/);
  assert.match(css, /\.menu-open \.sidebar\s*\{[^}]*visibility:\s*visible/);
});

test("主体使用中性色，状态色与主色分别定义", () => {
  const css = read("../styles/pages.css");
  assert.match(css, /\.metric-value,\.metric-value\.blue,\.metric-value\.green,\.metric-value\.amber\s*\{[^}]*color:\s*#30363d/);
  assert.match(read("../styles/base.css"), /\.badge-info\s*\{[^}]*color:\s*#3d718a/);
  assert.match(read("../styles/base.css"), /--link:\s*#1664c0/);
});

test("主体按区块布局，实体名称有明确的蓝色入口", () => {
  const layout = read("../styles/layout.css");
  assert.match(layout, /\.page-surface\s*\{[^}]*background:\s*transparent[^}]*border:\s*0/);
  assert.match(read("../styles/base.css"), /\.table a\.row-link[^}]*font-weight:\s*600[^}]*color:\s*var\(--link\)/);
});

test("完整原型入口、样式和模块引用版本一致", () => {
  const html = read("../index.html");
  const version = html.match(/app\.js\?v=(console-\d+)/)?.[1];
  assert.ok(version);
  assert.equal((html.match(new RegExp(`css\\?v=${version}`, "g")) || []).length, 4);
  const files = readdirSync(new URL("../js/", import.meta.url), { recursive: true, withFileTypes: true }).filter(item => item.isFile() && item.name.endsWith(".js"));
  for (const file of files) {
    const source = readFileSync(`${file.parentPath}/${file.name}`, "utf8");
    const paths = [...source.matchAll(/from "(\.[^"]+)"/g)].map(match => match[1]);
    assert.ok(paths.every(path => path.endsWith(`?v=${version}`)), file.name);
  }
});

test("删除解释小字，短信息使用标签，业务信息保持明确字段", () => {
  assert.doesNotMatch(renderSpace(SEED_STATE, SEED_STATE.users[1]), /组与个人上限取较小值|metric-note/);
  const models = renderModelList(SEED_STATE, {});
  assert.doesNotMatch(models, /图片文件夹|<p>|model-task|查看配置/);
  assert.match(models, /class="chip"/);
  const users = renderUsers(SEED_STATE);
  assert.doesNotMatch(users, /class="secondary"/);
  assert.match(users, /<th>邮箱<\/th>/);
  assert.match(renderRunList(SEED_STATE, {}), /<th>模型<\/th>/);
  const draft = { taskId: "object-detection", modelId: "yolov8n-pre", projectId: "new", datasetId: "ds-helmet" };
  for (const step of [0,1,2]) assert.doesNotMatch(renderTrainWizard(SEED_STATE, draft, step, {}), /<small|class="hint"/);
});

test("正式原型全部文字样式至少14px", () => {
  for (const file of ["base.css", "layout.css", "pages.css", "auth.css"]) {
    const css = read(`../styles/${file}`);
    const sizes = [...css.matchAll(/(?:font-size:\s*|font:\s*)([\d.]+)px/g)].map(match => Number(match[1]));
    assert.ok(sizes.every(size => size >= 14), `${file} 存在小字`);
  }
});

test("详情或向导自带面包屑时不重复添加第二层", () => {
  const html = shell("/datasets/new", '<div class="breadcrumb">数据集 / 导入</div>', "导入数据集", SEED_STATE.users[0]);
  assert.equal(html.includes('class="console-crumb"'), false);
});
