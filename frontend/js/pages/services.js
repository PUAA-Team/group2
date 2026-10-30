import { taskById } from "../data.js?v=console-4";
import { badge, card, emptyState, escapeHtml as e, icon, linkButton, pageHeader } from "../ui.js?v=console-4";

export function renderServiceList(state) {
  const rows = state.services.map(service => {
    const run = state.runs.find(item => item.id === service.runId);
    return `<tr><td><a class="row-link" href="#/services/${e(service.id)}">${e(service.name)}</a></td><td>${e(taskById(run?.taskId)?.name || "—")}</td><td>${badge(service.status)}</td><td>${e(service.version)}</td><td>${e(service.resource)}</td><td>${e(service.calls)}</td><td>${e(service.created)}</td></tr>`;
  }).join("");
  const action = '<button class="btn btn-primary" data-action="open-modal" data-modal="service-new">创建服务</button>';
  return `${pageHeader("在线服务", "", action)}${card(rows ? `<div class="table-scroll"><table class="table"><thead><tr><th>服务名称</th><th>任务类型</th><th>状态</th><th>版本</th><th>资源</th><th>调用次数</th><th>创建时间</th></tr></thead><tbody>${rows}</tbody></table></div>` : emptyState("还没有在线服务", "从已完成的模型版本创建第一个服务。"))}`;
}

export function renderServiceDetail(state, id, ui) {
  const service = state.services.find(item => item.id === id);
  if (!service) return emptyState("服务不存在", "返回服务列表重新选择。", linkButton("返回推理服务", "#/services"));
  const run = state.runs.find(item => item.id === service.runId);
  const task = taskById(run?.taskId);
  const example = task?.group === "文本" ? "请输入一段待识别的文本" : task?.group === "表格" ? '{"feature_a": 0.3, "feature_b": 12}' : "选择图片后提交测试";
  const result = ui.serviceResult ? `<div class="section-heading"><h2>响应结果</h2></div><pre class="service-test-result">${e(ui.serviceResult)}</pre>` : "";
  const history = (service.history || []).map(item => `<tr><td>${e(item.time)}</td><td>${badge(item.result)}</td><td>${e(item.latency)}</td><td>${e(item.source)}</td></tr>`).join("");
  return `<div class="breadcrumb"><a href="#/services">推理服务</a>${icon("chevron", 13)}<span>${e(service.name)}</span></div>
    <div class="detail-header"><div><div class="detail-title"><h1>${e(service.name)}</h1>${badge(service.status)}</div></div></div>
    <div class="grid-2">${card(`<div class="card-header"><h2>服务信息</h2></div><dl class="info-list"><div><dt>模型来源</dt><dd><a class="card-link" href="#/runs/${e(run?.id || "")}?tab=outputs">${e(run?.name || "—")}</a></dd></div><div><dt>适用任务</dt><dd>${e(task?.name || "—")}</dd></div><div><dt>模型版本</dt><dd>${e(service.version)}</dd></div><div><dt>创建时间</dt><dd>${e(service.created)}</dd></div><div><dt>资源规格</dt><dd>${e(service.resource)}</dd></div><div><dt>调用次数</dt><dd>${e(service.calls)}</dd></div><div><dt>认证方式</dt><dd>演示模式</dd></div></dl><hr/><div class="field"><span>接口示意</span><code class="template-preview">POST /api/inference/${e(service.id)}/predict</code></div>`)}
      ${card(`<div class="card-header"><h2>在线测试</h2></div><form id="service-test-form" data-service-id="${e(service.id)}"><div class="field"><label for="test-input">测试输入</label><textarea id="test-input" name="input" class="textarea" placeholder="${e(example)}" required></textarea></div><button class="btn btn-primary rounded-lg text-sm font-medium transition-colors" style="margin-top:14px" type="submit">运行演示测试</button></form>${result}`)}</div>
    <div class="section-heading"><h2>调用记录</h2></div>${card(history ? `<div class="table-scroll"><table class="table"><thead><tr><th>时间</th><th>结果</th><th>耗时</th><th>来源</th></tr></thead><tbody>${history}</tbody></table></div>` : emptyState("暂无调用记录", "运行在线测试后会显示记录。"))}`;
}
