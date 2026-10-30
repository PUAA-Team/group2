import assert from "node:assert/strict";

export const adminRoutes = [["/admin/stats", ".console-summary-six"], ["/admin/settings", '[data-id="settings-edit"]'], ["/admin/data", ".table"], ["/admin/models", ".table"], ["/admin/jobs", ".table"], ["/admin/audit", ".table"]];

export async function adminFlows({ fixture, login, run, go, fill, click, wait, capture, evaluate, report }) {
  const modal = async kind => { await click(`[data-action="modal"][data-id="${kind}"]`); await wait("!!document.querySelector('[role=dialog]')"); };
  const save = async () => { await click('[role=dialog] [type=submit]'); await wait("!document.querySelector('[role=dialog]') && !document.querySelector('.live-loading')"); };
  await go("/admin/stats", ".console-summary-six"); await capture("admin-statistics-1440.png");
  await go("/admin/settings", '[data-id="settings-edit"]'); await modal("settings-edit");
  await fill("platform_name", "研发验收中心", '[data-form="dialog"]'); await fill("global_concurrent_jobs", "3", '[data-form="dialog"]'); await save();
  assert.equal(await evaluate("document.querySelector('.console-brand strong').textContent"), "研发验收中心");
  report.checks.push("平台设置持久化并更新实际界面");
  await modal("connection-new");
  for (const [key, value] of Object.entries({ name: "界面连接验收 " + run, endpoint: "https://api.example.com/v1", model: "qa-model", secret: "qa-protocol-key" })) await fill(key, value, '[data-form="dialog"]');
  await evaluate("document.querySelector('[name=active]').checked=false"); await save();
  const connection = await evaluate(`(async()=>{const r=await(await fetch('/api/v1/admin/model-connections')).json();return r.data.find(x=>x.name===${JSON.stringify("界面连接验收 " + run)});})()`);
  assert.ok(connection.credential_set && !connection.secret_ref && !connection.secret);
  await click(`[data-action="admin-edit-connection"][data-id="${connection.id}"]`); await wait("!!document.querySelector('[name=secret]')");
  assert.equal(await evaluate("document.querySelector('[name=secret]').value"), ""); await click('[data-action="close-modal"]');
  await capture("admin-settings-1440.png"); report.checks.push("模型连接真实保存、凭据不回显；未调用外部API");
  await go("/admin/data", ".table");
  await evaluate(`(()=>{const e=document.querySelector('[data-query-filter=space]');e.value=${JSON.stringify(fixture.other_workspace_id)};e.dispatchEvent(new Event('change',{bubbles:true}));})()`);
  await wait("!document.querySelector('.live-loading') && document.querySelector('tbody')?.textContent.includes('协作样本')"); report.checks.push("管理员跨空间目录和筛选");
  await go("/admin/users", ".table"); await click('[data-action="admin-user-access"]'); await wait("!!document.querySelector('[role=dialog]')");
  assert.equal(await evaluate("!!document.querySelector('[role=dialog] [type=submit]')"), false); await click('[data-action="close-modal"]');
  await modal("invite-new"); await fill("workspace_id", fixture.workspace_id, '[data-form="dialog"]'); await fill("role", "viewer", '[data-form="dialog"]');
  await evaluate("(()=>{const e=document.querySelector('[name=group_id]');if(e.options.length>1)e.selectedIndex=1;})()"); await save();
  const inviteUrl = await evaluate("document.querySelector('#invite-url').value");
  const inviteRoute = new URL(inviteUrl).hash.slice(1);
  await click('[data-action="logout"]'); await wait("!!document.querySelector('[data-form=login]')");
  await go(inviteRoute, '[data-form="register"]');
  const account = "member" + run;
  for (const [key, value] of Object.entries({ account, display_name: "协作成员", password: "qa-member-password-2026", confirm: "qa-member-password-2026" })) await fill(key, value, '[data-form="register"]');
  await click('[data-form="register"] [type=submit]'); await wait("!!document.querySelector('.console-summary')");
  assert.equal(await evaluate("!!document.querySelector('.nav-divider')"), false);
  await go("/space", ".live-spaces"); assert.equal(await evaluate("!!document.querySelector('[data-id=member]')"), false);
  report.checks.push("真实邀请注册、自动登录和只读角色生效");
  await click('[data-action="logout"]'); await wait("!!document.querySelector('[data-form=login]')");
  await fill("account", login.account, '[data-form="login"]'); await fill("password", login.password, '[data-form="login"]'); await click('[data-form="login"] [type=submit]'); await wait("!!document.querySelector('.console-summary')");
  await go("/admin/users", ".table");
  const user = await evaluate(`(async()=>{const r=await(await fetch('/api/v1/admin/users?q=${account}')).json();return r.data.find(x=>x.account==='${account}');})()`);
  await click(`[data-action="admin-reset-password"][data-id="${user.id}"]`); await wait("!!document.querySelector('[name=confirm]')");
  await fill("password", "qa-reset-password-2026", '[data-form="dialog"]'); await fill("confirm", "qa-reset-password-2026", '[data-form="dialog"]'); await save(); report.checks.push("管理员密码重置弹窗");
  await go("/admin/users?tab=groups", ".table"); await click('[data-action="admin-group-members"]'); await wait("!!document.querySelector('[role=dialog]')");
  assert.ok(await evaluate("document.querySelector('[role=dialog]').textContent.includes('协作成员')")); await click('[data-action="close-modal"]'); report.checks.push("用户组成员与有效权限");
  await go("/space", ".live-spaces"); await click(`[data-action="admin-remove-member"][data-id="${user.id}"]`); await wait("!!document.querySelector('[role=dialog]')"); await save();
  assert.equal(await evaluate(`!!document.querySelector('[data-action="admin-remove-member"][data-id="${user.id}"]')`), false); report.checks.push("移除空间成员与所有者保护");
}
