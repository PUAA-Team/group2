import test from "node:test";
import assert from "node:assert/strict";
import { addDataset, addRun, addService, advanceRun, getState, processDataset, recordServiceTest, resetDemo, toggleUser } from "../js/state.js";

test("数据集处理、训练和服务演示形成可追踪流程", () => {
  resetDemo();
  const dataset = addDataset({ name: "测试图片", taskId: "image-classification", files: ["images.zip"], count: 30 });
  assert.equal(dataset.status, "待处理");
  processDataset(dataset.id, ["检查格式", "训练集 80%"]);
  assert.equal(dataset.status, "可训练");
  assert.equal(dataset.version, 2);

  const run = addRun({ projectId: "new", projectName: "测试项目", name: "测试训练", taskId: "image-classification", modelId: "mobilenet", datasetId: dataset.id, gpu: "GPU 02", epochs: 20, batch: 8, lr: 0.001 });
  assert.equal(run.status, "排队中");
  advanceRun(run.id);
  assert.equal(run.status, "运行中");
  advanceRun(run.id);
  assert.equal(run.status, "已完成");

  const service = addService({ name: "测试服务", runId: run.id, resource: "CPU · 2 核 4 GB" });
  assert.equal(service.status, "运行中");
  assert.equal(service.calls, 0);
  recordServiceTest(service.id);
  assert.equal(service.calls, 1);
  assert.equal(service.history.length, 1);
  assert.ok(getState().audit.length >= 5);
  resetDemo();
});

test("演示管理员不会被停用", () => {
  resetDemo();
  const admin = getState().users.find(user => user.role === "管理员");
  assert.ok(admin);
  toggleUser(admin.id);
  assert.equal(admin.status, "启用");
  resetDemo();
});
