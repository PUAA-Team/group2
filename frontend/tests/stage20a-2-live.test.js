import test from "node:test";
import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { ASSET_VERSION } from "../live/ui/version.js";
import { NAV_GROUPS, ADMIN_NAV, badge, icon, shell } from "../live/ui/ui.js";
import { table, raw, e } from "../live/components.js";
import { renderDialog } from "../live/dialogs.js";

const liveDir = join(dirname(fileURLToPath(import.meta.url)), "..", "live");
function liveFiles(dir = liveDir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap(entry =>
    entry.isDirectory() ? liveFiles(join(dir, entry.name)) : [join(dir, entry.name)]);
}
const sources = liveFiles().filter(file => file.endsWith(".js") || file.endsWith(".html"));

test("live/ 内所有 ?v= 与 ui/version.js 的单一构建常量一致", () => {
  assert.match(ASSET_VERSION, /^[a-z0-9][a-z0-9._-]*$/);
  const versions = new Map();
  for (const file of sources) {
    for (const match of readFileSync(file, "utf8").matchAll(/\?v=([A-Za-z0-9._-]+)/g)) {
      versions.set(match[1], [...(versions.get(match[1]) || []), file]);
    }
  }
  assert.deepEqual([...versions.keys()], [ASSET_VERSION], "存在与 ASSET_VERSION 不一致的缓存版本标识");
});

test("live/ 不再引用原型目录 ../js/ 与 design-review/", () => {
  const offenders = sources.filter(file => {
    const text = readFileSync(file, "utf8");
    return text.includes("../js/") || text.includes("design-review");
  });
  assert.deepEqual(offenders, []);
});

test("table() 默认转义单元格，raw() 标记受信任片段", () => {
  const escaped = table(["名称"], [["<script>alert(1)</script>"]]);
  assert.ok(escaped.includes("&lt;script&gt;alert(1)&lt;/script&gt;"));
  assert.ok(!escaped.includes("<script>alert(1)</script>"));
  const trusted = table(["状态"], [[raw(badge("运行中"))]]);
  assert.ok(trusted.includes('class="badge badge-info"'));
  assert.ok(trusted.includes("运行中"));
  const mixed = table(["名称", "数量"], [[raw(e("<b>甲</b>")), 3]]);
  assert.ok(mixed.includes("&lt;b&gt;甲&lt;/b&gt;"));
  assert.ok(mixed.includes("<td>3</td>"));
  assert.ok(!mixed.includes("&amp;lt;b&gt;"));
  const headed = table(["<b>标题</b>"], [["x"]]);
  assert.ok(headed.includes("&lt;b&gt;标题&lt;/b&gt;"));
});

test("ui/ 原语从 live/ui 导出，shell 渲染导航", () => {
  assert.ok(Array.isArray(NAV_GROUPS) && NAV_GROUPS.length > 0);
  assert.ok(Array.isArray(ADMIN_NAV) && ADMIN_NAV.length > 0);
  assert.ok(icon("home").includes("<svg"));
  assert.ok(badge("运行中").includes("badge-info"));
  const html = shell("/home", "<p>内容</p>", "工作台", { name: "甲", role: "成员" }, {});
  assert.ok(html.includes("概览") && html.includes("工作台"));
});

test("对话框路由表覆盖各模块 kind，未知 kind 不抛错", () => {
  const ctx = { data: {}, groups: [], workspaces: [], templates: [], session: { user: { is_admin: false } } };
  assert.equal(renderDialog({ kind: "project-new", item: {} }, ctx).includes("新建项目"), true);
  assert.equal(renderDialog({ kind: "project-archive", item: { name: "甲", archived: false } }, ctx).includes("归档项目"), true);
  assert.equal(renderDialog({ kind: "gov-archive", item: { name: "甲", archived: false } }, ctx).includes("归档资产"), true);
  assert.equal(renderDialog({ kind: "job-stop", item: { name: "甲", status: "running" } }, ctx).includes("停止任务"), true);
  assert.equal(renderDialog({ kind: "data-cancel", item: { name: "甲", status: "queued" } }, ctx).includes("取消数据处理"), true);
  assert.equal(renderDialog({ kind: "keys-expiry", item: { name: "甲", expires_at: "2027-01-01T00:00:00.000Z" } }, ctx).includes("调整有效期"), true);
  assert.ok(renderDialog({ kind: "not-a-dialog", item: {} }, ctx).includes('id="live-modal"'));
  assert.ok(renderDialog({ kind: "not-a-dialog", item: {} }, ctx).includes('<h2 id="live-dialog-title"></h2>'));
});
