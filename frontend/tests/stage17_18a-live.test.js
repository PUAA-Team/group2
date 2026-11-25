import test from "node:test";
import assert from "node:assert/strict";
import { pageTitle } from "../live/components.js";
import { NAV_GROUPS } from "../js/ui.js";
import { renderHome, renderSpace } from "../live/pages/overview.js";
import { renderAssetDetail } from "../live/pages/assets.js";
import { renderManagement } from "../live/administration.js";
import { renderDialog } from "../live/dialogs.js";

test("Stage 18A: /assistants 具备侧栏入口与页面标题", () => {
  assert.equal(pageTitle("/assistants"), "智能辅助");
  assert.equal(pageTitle("/assistants/req_1"), "智能辅助");
  const allLinks = NAV_GROUPS.flatMap(g => g.children.map(([, href]) => href));
  assert.ok(allLinks.includes("/assistants"));
});

test("Stage 18A: 工作台展示待处理事项且用户空间展示我的近期任务", () => {
  const ctx = {
    workspace: { id: "ws1", name: "测试空间", owner_id: "u1" },
    workspaces: [{ id: "ws1", name: "测试空间" }],
    session: { user: { id: "u1", display_name: "李工" }, access: { actions: ["workspaces.create"] } },
    access: { actions: ["training.read", "training.write", "datasets.read"], quota: { gpu_count: 1, concurrent_jobs: 2, storage_gib: 10 } },
    data: {
      counts: { projects: 1, active: 0, queued: 0, succeeded: 1, datasets: 1 },
      pending_items: [
        { key: "join_requests", label: "待审批加入申请", count: 2, href: "/space" },
        { key: "annotation_batches", label: "进行中标注批次", count: 1, href: "/annotation" },
      ],
      recent_jobs: [],
      activity: [],
      myJobs: [{ id: "job1", name: "个人文本训练", task_type: "text_classification", status: "succeeded", created_at: "2026-11-26T00:00:00Z" }],
    },
  };
  const homeHtml = renderHome(ctx);
  assert.ok(homeHtml.includes("待处理事项"));
  assert.ok(homeHtml.includes("待审批加入申请"));
  assert.ok(homeHtml.includes("进行中标注批次"));

  const spaceHtml = renderSpace(ctx);
  assert.ok(spaceHtml.includes("我的近期任务"));
  assert.ok(spaceHtml.includes("个人文本训练"));
});

test("Stage 18A & 17A: 统计面板筛选器、校验报告弹窗与受控权重上传弹窗", () => {
  const statsHtml = renderManagement({
    path: "/admin/stats",
    params: new URLSearchParams({ creator: "owner" }),
    workspaces: [{ id: "ws1", name: "默认空间" }],
    data: { counts: { users: 1, datasets: 1, models: 1, jobs: 2, active: 0, failed: 0 }, trend: [], states: {}, workspaces: [] },
  });
  assert.ok(statsHtml.includes('data-action="query-filter"'));
  assert.ok(statsHtml.includes("创建人：owner"));

  const dsHtml = renderAssetDetail("datasets", {
    workspace: { id: "ws1" },
    access: { actions: ["datasets.write"] },
    data: {
      item: { id: "ds1", name: "情感数据", task_type: "text_classification", status: "available", description: "" },
      versions: { data: [{ id: "v1", number: 1, filename: "train.csv", format: "csv", sample_count: 10, size_bytes: 1024, status: "available" }] },
    },
  });
  assert.ok(dsHtml.includes('data-action="dataset-report"'));

  const reportDialog = renderDialog({
    kind: "dataset-report",
    item: { number: 1, sample_count: 10, empty_labels: 1, size_bytes: 2048, integrity_ok: true, sha256: "abc123", label_distribution: [{ label: "pos", count: 6, ratio: 0.6 }, { label: "neg", count: 3, ratio: 0.3 }] },
  }, { data: {} });
  assert.ok(reportDialog.includes("数据集校验报告"));
  assert.ok(reportDialog.includes("60.0%"));
  assert.ok(reportDialog.includes("abc123"));

  const uploadDialog = renderDialog({ kind: "model-upload", item: { id: "m1" } }, { data: {} });
  assert.ok(uploadDialog.includes("上传受控权重"));
  assert.ok(uploadDialog.includes('accept=".zip"'));
});
