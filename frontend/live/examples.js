const textRows = [
  ["操作简单，上手很快", "正向"], ["运行稳定，效果符合预期", "正向"], ["文档清晰，部署顺利", "正向"],
  ["响应时间太长", "负向"], ["上传失败，希望尽快修复", "负向"], ["日志内容难以理解", "负向"],
];
export const CSV_TEMPLATE = "text,label\n" + textRows.map(row => row.join(",")).join("\n") + "\n";
export const JSONL_TEMPLATE = [
  { instruction: "判断用户反馈的情感，回答正向或负向。", input: "操作简单，上手很快", output: "正向" },
  { instruction: "判断用户反馈的情感，回答正向或负向。", input: "上传一直失败", output: "负向" },
].map(row => JSON.stringify(row)).join("\n") + "\n";

export async function addExamples(api, workspaceId, selected) {
  const taskTypes = selected.map(key => ({ text: "text_classification", sft: "llm_sft", image: "image_classification" })[key]).filter(Boolean);
  await api.request(`/workspaces/${workspaceId}/presets`, { method: "POST", body: { task_types: taskTypes } });
}
