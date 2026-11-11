import test from "node:test";
import assert from "node:assert/strict";
import { assistantDialog, renderAssistant, saveAssistant } from "../live/assistant.js";
import { renderAnnotation } from "../live/annotation-view.js";
import { saveAnnotation } from "../live/data-actions.js";

const context = () => ({ path: "/assistants/r1", page: 1, params: new URLSearchParams(), workspace: { id: "w1" },
  session: { user: { id: "u1" } }, access: { actions: ["assistants.use", "datasets.write", "training.write"] },
  data: { id: "r1", purpose: "annotation", status: "preview", created_by: "u1", source: {},
    preview: { text: '<script>alert(1)</script>', images: [{ index: 0, data_url: "data:image/png;base64,AA==" }] } } });

test("智能辅助展示实际外发图像、转义文本；仅创建人可确认及采纳", () => {
  const ctx = context();
  let html = renderAssistant(ctx);
  assert.ok(html.includes('src="data:image/png;base64,AA=="'));
  assert.ok(html.includes("&lt;script&gt;") && !html.includes("<script>"));
  assert.ok(html.includes('data-action="assistant-confirm"'));
  ctx.data.status = "succeeded"; ctx.data.created_by = "other";
  html = renderAssistant(ctx);
  assert.ok(!html.includes('data-action="assistant-apply"'));
});

test("配置连接严格使用空间白名单，图像单次最多四张", () => {
  const ctx = context();
  ctx.assistantOptions = { policy: { enabled: true, connection_ids: ["allowed"], max_samples: 20 },
    connections: [{ id: "allowed", name: "已授权", capabilities: ["vision"] }, { id: "other", name: "未授权", capabilities: ["vision"] }] };
  ctx.data = { dataset: { task_type: "image_classification" }, samples: Array.from({ length: 10 }, (_, index) => ({ index })) };
  const dialog = assistantDialog({ kind: "assistant-annotation-new" }, ctx);
  assert.ok(!dialog.fields.includes('value="other"'));
  assert.equal((dialog.fields.match(/name="sample_indices"/g) || []).length, 4);
});

test("取消所有候选勾选时阻断采纳请求", async () => {
  const ctx = context(); let called = false;
  await assert.rejects(() => saveAssistant({ request() { called = true; } },
    { kind: "assistant-apply", workspaceId: "w1", item: ctx.data }, new FormData(), ctx), /请选择/);
  assert.equal(called, false);
});

test("指令标注保留输入修订并使用真实字段提交", async () => {
  const ctx = context(); ctx.path = "/annotation/b1";
  ctx.data = { id: "b1", name: "指令", status: "open", dataset: { name: "数据", task_type: "llm_sft" },
    source_version: { number: 1 }, counts: { total: 1 }, can_edit: true, labels: [],
    samples: [{ index: 0, source: { instruction: "原指令", input: "原输入", output: "输出" }, result: { edits: { input: "已修改" } } }] };
  assert.ok(renderAnnotation(ctx).includes('name="instruction"'));
  assert.ok(renderAnnotation(ctx).includes("已修改"));
  // FormData由浏览器提供，测试中只替换构造以核对载荷，不启动浏览器。
  const Original = globalThis.FormData;
  globalThis.FormData = class { get() { return "新输出"; } };
  try {
    let body;
    await saveAnnotation({ async request(path, options) { body = options.body; } }, ctx,
      { dataset: { sampleIndex: "0", revision: "1" }, elements: { namedItem(key) { return { value: key === "input" ? "" : "新指令" }; } } }, false);
    assert.deepEqual(body.edits, { instruction: "新指令", input: "" });
  } finally { globalThis.FormData = Original; }
});
