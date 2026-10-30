import test from "node:test";
import assert from "node:assert/strict";
import { SEED_STATE, TASKS } from "../js/data.js";
import { renderHome } from "../js/pages/home.js";
import { renderDatasetDetail, renderDatasetList, renderDatasetNew } from "../js/pages/datasets.js";
import { renderProjectDetail, renderProjectList } from "../js/pages/projects.js";
import { renderRunDetail, renderRunList, renderTrainWizard } from "../js/pages/training.js";
import { renderModelDetail, renderModelList } from "../js/pages/models.js";
import { renderServiceDetail, renderServiceList } from "../js/pages/services.js";
import { renderModal } from "../js/modals.js";
import { renderAudit, renderResources, renderUsers } from "../js/pages/admin.js";

const state = structuredClone(SEED_STATE);
const ui = { search: "", datasetType: "全部类型", runStatus: "全部状态", modelTab: "prebuilt", modelGroup: "全部类型", wizardGroup: "图像" };
const draft = { projectId: "pr-helmet", name: "测试训练", taskId: "object-detection", modelId: "yolov8n-pre", datasetId: "ds-helmet", gpu: "GPU 02", epochs: 50, batch: 8, lr: 0.001 };

test("主要页面均能生成非空内容", () => {
  const pages = [
    renderHome(state), renderDatasetList(state, ui), renderDatasetNew(ui),
    renderDatasetDetail(state, state.datasets[0].id), renderProjectList(state, ui),
    renderProjectDetail(state, state.projects[0].id), renderRunList(state, ui),
    renderRunDetail(state, state.runs[0].id), renderModelList(state, ui),
    renderModelDetail(state, TASKS[0].models[0].id), renderServiceList(state),
    renderModal({ kind: "service-new" }, state), renderServiceDetail(state, state.services[0].id, ui),
    renderResources(state), renderUsers(state), renderAudit(state)
  ];
  pages.forEach((html, index) => assert.ok(html.length > 200, `页面 ${index + 1} 内容不足`));
});

test("工作台统计卡片只保留指标与数值", () => {
  const html = renderHome(state);
  assert.doesNotMatch(html, /metric-note|已建立的项目|包含排队任务|可查看模型产物|已完成数据处理/);
});

test("训练配置四个步骤均能渲染", () => {
  for (let step = 0; step < 4; step++) {
    const html = renderTrainWizard(state, draft, step, ui);
    assert.match(html, /新建训练/);
    assert.match(html, /当前配置/);
  }
});

test("未知详情编号提供返回入口", () => {
  assert.match(renderDatasetDetail(state, "missing"), /返回数据集/);
  assert.match(renderRunDetail(state, "missing"), /返回训练任务/);
  assert.match(renderServiceDetail(state, "missing", ui), /返回推理服务/);
});

test("新建服务不显示其他服务的历史调用", () => {
  const isolated = structuredClone(state);
  isolated.services = [{ id: "svc-new", name: "新服务", runId: "run-1035", status: "运行中", version: "v1", resource: "CPU", calls: 0, created: "09-29", history: [] }];
  const html = renderServiceDetail(isolated, "svc-new", ui);
  assert.doesNotMatch(html, /09-28 15:42/);
  assert.match(html, /暂无调用记录/);
});
