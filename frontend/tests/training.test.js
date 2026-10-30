import test from "node:test";
import assert from "node:assert/strict";
import { SEED_STATE } from "../js/data.js";
import { renderTrainWizard } from "../js/pages/training.js";

const draft = {
  projectId: "pr-helmet", projectName: "", name: "安全帽检测 · 新实验",
  taskId: "object-detection", modelId: "yolov8n-pre", datasetId: "ds-helmet",
  gpu: "GPU 02", epochs: 50, batch: 8, lr: 0.001
};

test("参数步骤展示当前任务的超参数", () => {
  const html = renderTrainWizard(SEED_STATE, draft, 2, {});
  assert.match(html, /训练轮次/);
  assert.match(html, /批大小/);
  assert.match(html, /学习率/);
});
