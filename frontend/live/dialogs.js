import { ACTIONS, badge, btn, description, e, fieldsInfo, input, options, QUOTAS, select, table, taskOptions } from "./components.js?v=stage20a-2";
import { computeDialog } from "./compute.js?v=stage20a-2";
import { workflowDialog } from "./workflows.js?v=stage20a-2";
import { administrationDialog } from "./administration.js?v=stage20a-2";
import { dataDialog } from "./data-workflows.js?v=stage20a-2";
import { assistantDialog } from "./assistant.js?v=stage20a-2";
import { governanceDialog } from './governance.js?v=stage20a-2';
import { parameterTemplateDialog } from './parameter-templates.js?v=stage20a-2';
import { projectDialog } from './projects.js?v=stage20a-2';
import { keyDialog } from './key-management.js?v=stage20a-2';
import { queryDialog } from './query-controls.js?v=stage20a-2';

function policyFields(item = {}, personal = false) {
  const checks = (name, label) => `<fieldset class="live-check-field"><legend>${label}</legend><div class="live-checks">${ACTIONS.map(([key, text]) => `<label><input type="checkbox" name="${name}" value="${key}" ${(item[name] || []).includes(key) ? "checked" : ""}/>${e(text)}</label>`).join("")}</div></fieldset>`;
  return checks("allow_actions", personal ? "个人允许" : "基础授权") + checks("deny_actions", "显式禁用") +
    `<div class="live-field-grid">${QUOTAS.map(([key, label]) => input(label, key, item.quota?.[key] ?? "", `type="number" min="0" step="1" ${personal ? 'placeholder="继承"' : 'placeholder="0"'}`)).join("")}</div>`;
}

// 对话框 kind → 渲染函数路由表（替代原来的 || 串联；新增 kind 只需在此加一行）。
const DIALOG_RENDERERS = new Map([
  ...["project-new", "project-edit", "project-archive", "project-delete"].map(kind => [kind, projectDialog]),
  ...["keys-expiry", "keys-example"].map(kind => [kind, keyDialog]),
  ["query-filter", queryDialog],
  ...["parameter-template-list", "parameter-template-new", "parameter-template-edit", "parameter-template-archive"].map(kind => [kind, parameterTemplateDialog]),
  ...["gov-device-policy", "gov-group-budget", "gov-archive", "gov-delete", "gov-review"].map(kind => [kind, governanceDialog]),
  ...["assistant-policy", "assistant-annotation-new", "assistant-parameters-new", "assistant-logs-new", "assistant-apply"].map(kind => [kind, assistantDialog]),
  ...["data-annotation-new", "data-operation-new", "data-publish", "annotation-publish", "data-cancel"].map(kind => [kind, dataDialog]),
  ...["settings-edit", "connection-new", "connection-edit", "invite-new", "password-own", "password-reset", "profile", "workspace-edit", "workspace-invite", "workspace-join", "workspace-delete", "member-remove", "user-access", "group-members"].map(kind => [kind, administrationDialog]),
  ...["enroll-new", "local-worker", "node-edit", "node-toggle", "node-revoke", "enrollment-revoke", "local-stop"].map(kind => [kind, computeDialog]),
  ...["job-new", "job-edit", "job-stop", "job-priority", "service-invoke", "key-new", "key-revoke", "key-rotate"].map(kind => [kind, workflowDialog]),
]);

export function renderDialog(modal, ctx) {
  if (!modal) return "";
  const item = modal.item || {};
  const renderer = DIALOG_RENDERERS.get(modal.kind);
  let { title = "", fields = "", submit = "保存", wide = false, readOnly = false } = renderer ? renderer(modal, ctx) || {} : {};
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
  if (modal.kind === "model-upload") {
    title = "上传受控权重"; submit = "上传";
    fields = `<div class="notice">仅支持包含 manifest.json 与 safetensors 权重的受控 .zip 包（≤ 64 MiB）。</div>` +
      input("版本", "version", "", 'required maxlength="64" placeholder="例如 import-v1"') +
      `<div class="field"><label for="model-weight-file">选择权重包</label><input id="model-weight-file" name="file" class="input live-file" type="file" required accept=".zip" /></div>`;
  }
  if (modal.kind === "dataset-version") {
    title = "导入数据版本"; submit = "导入";
    fields = `<div class="heading-actions">${btn("下载模板", "template", item.task_type)}</div><div class="field"><label for="version-file">选择文件</label><input id="version-file" name="file" class="input live-file" type="file" required accept="${item.task_type === "llm_sft" ? ".jsonl" : item.task_type === "image_classification" ? ".zip" : ".csv"}" /></div>`;
  }
  if (modal.kind === "member") {
    title = item.user_id ? "配置空间成员" : "添加空间成员";
    const sub = item.quota || {};
    fields = input("已有用户账号", "account", item.account, `required maxlength="64" ${item.user_id ? "readonly" : ""}`) +
      select("空间角色", "role", options([["admin", "空间管理员"], ["editor", "研发成员"], ["annotator", "标注员"], ["viewer", "查看者"]], item.role || "editor")) +
      `<div class="live-field-grid">${QUOTAS.map(([key, label]) => input(`空间子配额：${label}`, `quota_${key}`, sub[key] ?? "", 'type="number" min="0" max="10000" placeholder="不另设上限"')).join("")}</div>`;
  }
  if (modal.kind === "transfer-owner") {
    title = "转让空间所有权"; submit = "确认转让";
    fields = `<div class="notice">转让后目标成员将成为空间所有者，您将保留空间管理员身份。</div>` +
      fieldsInfo([["目标成员", e(item.display_name)], ["账号", e(item.account)]]);
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
  if (modal.kind === "dataset-report") {
    title = "数据集校验报告"; readOnly = true; wide = true;
    const rows = (item.label_distribution || []).map(row => [row.label, row.count, `${((Number(row.ratio) || 0) * 100).toFixed(1)}%`]);
    fields = fieldsInfo([
      ["版本", `v${e(item.number ?? "")}`],
      ["样本数", e(item.sample_count ?? 0)],
      ["空标签样本", e(item.empty_labels ?? 0)],
      ["文件大小", `${((Number(item.size_bytes) || 0) / 1024).toFixed(1)} KiB`],
      ["完整性", badge(item.integrity_ok ? "正常" : "异常")],
      ["SHA256", `<code>${e(item.sha256 || "—")}</code>`],
    ]) + `<div class="section-heading"><h2>标签分布</h2></div>` + table(["标签", "样本数", "占比"], rows, "暂无标签样本");
  }
  return `<div class="modal-layer" id="live-modal"><div class="modal-scrim" data-action="close-modal"></div><section class="modal-panel ${wide ? "modal-wide" : ""}" role="dialog" aria-modal="true" aria-labelledby="live-dialog-title"><form data-form="dialog">
    <div class="modal-header"><h2 id="live-dialog-title">${e(title)}</h2><button class="icon-button" type="button" data-action="close-modal" aria-label="关闭">×</button></div><div class="modal-body stack"><div class="notice notice-danger" data-modal-error role="alert" hidden></div>${fields}</div><div class="modal-footer">${btn(readOnly ? "关闭" : "取消", "close-modal")}${readOnly ? "" : `<button class="btn btn-primary" type="submit">${submit}</button>`}</div></form></section></div>`;
}
