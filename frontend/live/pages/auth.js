import { e, icon, input } from "../components.js?v=stage15-1";

export function renderAuth({ initialized = true, enabled = false, registration = false, invitation = "", invitations_enabled = false, self_registration_enabled = false, platform_name = "模训平台" } = {}, error = "") {
  const setup = !initialized && enabled;
  const locked = !initialized && !enabled;
  const register = initialized && registration;
  const canRegister = invitations_enabled || self_registration_enabled;
  return `<div class="auth-layout"><section class="auth-aside"><div class="auth-brand"><span class="auth-brand-mark">模</span><span>${e(platform_name)}</span></div><div class="auth-aside-content"><h1>模型研发<br/>工作空间</h1></div><div></div></section>
    <main class="auth-main"><div class="auth-mobile-brand"><span class="auth-brand-mark">模</span>${e(platform_name)}</div><div class="auth-box"><div class="auth-intro"><h2>${setup ? "设置管理员" : register ? (self_registration_enabled ? "注册账号" : "邀请注册") : "登录工作空间"}</h2></div>
    <div data-auth-error class="notice notice-danger" role="alert" ${error ? "" : "hidden"}>${e(error)}</div>
    ${locked || register && !canRegister ? `<div class="notice">${locked ? "请联系管理员完成初始化" : "注册已关闭"}</div>` : `<form class="auth-form" data-form="${setup ? "setup" : register ? "register" : "login"}">
      ${register && (invitations_enabled || invitation) ? input(self_registration_enabled ? "邀请码（选填）" : "邀请码", "invitation", invitation, `${self_registration_enabled ? "" : "required "}minlength="20" maxlength="200" autocomplete="off"`) : ""}
      ${input("账号", "account", setup ? "admin" : "", 'required maxlength="64" autocomplete="username" pattern="[a-zA-Z0-9][a-zA-Z0-9_.-]{2,63}"')}
      ${setup || register ? input("姓名", "display_name", "", 'required maxlength="100" autocomplete="name"') : ""}${setup ? input("工作空间名称", "workspace_name", "研发工作空间", 'required maxlength="100"') : ""}
      <div class="field"><label for="live-password">${setup || register ? "密码（至少 12 位）" : "密码"}</label><div class="password-wrap"><input id="live-password" name="password" type="password" class="input" required maxlength="256" ${setup || register ? 'minlength="12"' : ""} autocomplete="${setup || register ? "new-password" : "current-password"}" /><button class="password-toggle" type="button" data-action="toggle-password" aria-label="显示密码">${icon("eye", 17)}</button></div></div>
      ${setup || register ? input("确认密码", "confirm", "", 'type="password" required minlength="12" maxlength="256" autocomplete="new-password"') : ""}
      <button class="btn btn-primary auth-submit" type="submit">${setup ? "创建并进入" : register ? "注册并进入" : "登录"}${icon("arrow", 16)}</button></form>`}${initialized ? `<div class="auth-switch"><a href="#/login">账号登录</a>${canRegister ? `<a href="#/register">${self_registration_enabled ? "注册账号" : "邀请注册"}</a>` : ""}</div>` : ""}</div></main></div>`;
}
