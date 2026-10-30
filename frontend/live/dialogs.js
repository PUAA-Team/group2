import { ACTIONS, btn, description, e, input, options, QUOTAS, select, taskOptions } from "./components.js?v=stage13-3a";
import { computeDialog } from "./compute.js?v=stage13-3a";
import { workflowDialog } from "./workflows.js?v=stage13-3a";
import { administrationDialog } from "./administration.js?v=stage13-3a";
import { dataDialog } from "./data-workflows.js?v=stage13-3a";

function policyFields(item = {}, personal = false) {
  const checks = (name, label) => `<fieldset class="live-check-field"><legend>${label}</legend><div class="live-checks">${ACTIONS.map(([key, text]) => `<label><input type="checkbox" name="${name}" value="${key}" ${(item[name] || []).includes(key) ? "checked" : ""}/>${e(text)}</label>`).join("")}</div></fieldset>`;
  return checks("allow_actions", personal ? "个人允许" : "基础授权") + checks("deny_actions", "显式禁用") +
    `<div class="live-field-grid">${QUOTAS.map(([key, label]) => input(label, key, item.quota?.[key] ?? "", `type="number" min="0" step="1" ${personal ? 'placeholder="继承"' : 'placeholder="0"'}`)).join("")}</div>`;
}

export function renderDialog(modal, ctx) {
  if (!modal) return "";
  const item = modal.item || {};
  let { title = "", fields = "", submit = "保存", wide = false, readOnly = false } = dataDialog(modal, ctx) || administrationDialog(modal, ctx) || computeDialog(modal, ctx) || workflowDialog(modal, ctx) || {};
  if (modal.kind === "workspace-new") { title = "创建工作空间"; fields = input("空间名称", "name", "", 'required maxlength="100"'); submit = "创建"; }
  if (["model-new", "dataset-new"].includes(modal.kind)) {
    const model = modal.kind === "model-new";
    title = model ? "新增模型" : "新增数据集";
    fields = input("名称", "name", "", 'required maxlength="100"') + select("任务", "task_type", taskOptions("text_classification"), "data-task-choice");
    if (model) fields += select("训练模板", "trainer_id", options(ctx.templates.filter(t => t.task_type === "text_classification").map(t => [t.id, t.name]))) + input("模型来源", "source_ref", "", 'required maxlength="1000" placeholder="组织/模型名或来源地址"');
    fields += description(); submit = "登记";
  }
  if (modal.kind === "asset-edit") { title = "修改名称与说明"; fields = input("名称", "name", item.name, 'required maxlength="100"') + description(item.description); }
  if (modal.kind === "model-version") { title = "登记模型版本"; fields = input("版本", "version", "", 'required maxlength="64" placeholder="例如 v1.0"') + input("模型来源", "source_ref", item.source_ref, 'required maxlength="1000"'); submit = "登记"; }
  if (modal.kind === "dataset-version") {
    title = "导入数据版本"; submit = "导入";
    fields = `<div class="heading-actions">${btn("下载模板", "template", item.task_type)}</div><div class="field"><label for="version-file">选择文件</label><input id="version-file" name="file" class="input live-file" type="file" required accept="${item.task_type === "llm_sft" ? ".jsonl" : item.task_type === "image_classification" ? ".zip" : ".csv"}" /></div>`;
  }
  if (modal.kind === "member") {
    title = item.user_id ? "修改成员角色" : "添加空间成员";
    fields = input("已有用户账号", "account", item.account, `required maxlength="64" ${item.user_id ? "readonly" : ""}`) + select("空间角色", "role", options([["editor", "编辑者"], ["viewer", "查看者"]], item.role || "editor"));
  }
  if (["group-new", "group-edit"].includes(modal.kind)) { title = modal.kind === "group-new" ? "新增用户组" : "配置用户组"; fields = input("用户组名称", "name", item.name, 'required maxlength="100"') + policyFields(item); wide = true; }
  if (["user-new", "user-edit"].includes(modal.kind)) {
    const editing = modal.kind === "user-edit"; title = editing ? "配置用户" : "新增用户"; wide = true;
    const groupChoices = [["", "未分组"], ...ctx.groups.map(group => [group.id, group.name])];
    if (item.group_id && !ctx.groups.some(group => group.id === item.group_id)) groupChoices.push([item.group_id, "当前用户组"]);
    fields = `<div class="live-field-grid">${input("姓名", "display_name", item.display_name, 'required maxlength="100"')}${editing ? "" : input("账号", "account", "", 'required minlength="3" maxlength="64" pattern="[a-zA-Z0-9][a-zA-Z0-9_.-]{2,63}"')}${select("平台角色", "is_admin", options([["false", "成员"], ["true", "管理员"]], String(item.is_admin || false)))}${select("用户组", "group_id", options(groupChoices, item.group_id || ""))}</div>`;
    if (!editing) fields += input("初始密码（至少 12 位）", "password", "", 'required type="password" minlength="12" maxlength="256" autocomplete="new-password"');
    fields += policyFields(item, true);
  }
  if (modal.kind === "toggle-user") {
    title = item.active ? "停用用户" : "启用用户"; submit = item.active ? "确认停用" : "确认启用";
    fields = `<dl class="info-list"><div><dt>用户</dt><dd>${e(item.display_name)}</dd></div><div><dt>账号</dt><dd>${e(item.account)}</dd></div></dl>`;
  }
  if (modal.kind === "examples") {
    title = "添加示例资产"; submit = "添加";
    fields = `<div class="live-checks live-checks-stacked"><label><input type="checkbox" name="examples" value="text" checked />文本分类</label><label><input type="checkbox" name="examples" value="sft" checked />Qwen LoRA</label><label><input type="checkbox" name="examples" value="image" checked />图像分类</label></div>`;
  }
  return `<div class="modal-layer" id="live-modal"><div class="modal-scrim" data-action="close-modal"></div><section class="modal-panel ${wide ? "modal-wide" : ""}" role="dialog" aria-modal="true" aria-labelledby="live-dialog-title"><form data-form="dialog">
    <div class="modal-header"><h2 id="live-dialog-title">${e(title)}</h2><button class="icon-button" type="button" data-action="close-modal" aria-label="关闭">×</button></div><div class="modal-body stack"><div class="notice notice-danger" data-modal-error role="alert" hidden></div>${fields}</div><div class="modal-footer">${btn(readOnly ? "关闭" : "取消", "close-modal")}${readOnly ? "" : `<button class="btn btn-primary" type="submit">${submit}</button>`}</div></form></section></div>`;
}
