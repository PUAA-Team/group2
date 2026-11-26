<script setup lang="ts">
import { computed, watch } from "vue";
import { btn, pageHeader, workspaceRequired } from "@live/components.js";
import { renderAssets, renderAssetDetail } from "@live/pages/assets.js";
import { renderAudit, renderUsers } from "@live/pages/admin.js";
import { renderHome, renderPending, renderSpace } from "@live/pages/overview.js";
import { isComputePage, renderCompute } from "@live/compute.js";
import { isWorkflowPage, renderWorkflow } from "@live/workflows.js";
import { renderDatasetImport } from "@live/dataset-import.js";
import { isManagementPage, renderManagement } from "@live/administration.js";
import { isDataPage, renderDataWorkflow } from "@live/data-workflows.js";
import { isAssistantPage, renderAssistant } from "@live/assistant.js";
import { ctx, renderTick } from "@/stores/app";

const emit = defineEmits<{ (e: "breadcrumb", hasCustom: boolean): void }>();

const pageHtml = computed(() => {
  void renderTick.value;
  if (ctx.loading) return '<div class="live-loading" role="status">正在加载…</div>';
  if (ctx.error) return pageHeader(ctx.error, "", btn("重试", "refresh"));
  if (ctx.forbidden) return pageHeader("无权访问") + '<a class="btn btn-secondary" href="#/home">返回工作台</a>';
  if (isManagementPage(ctx.path)) return renderManagement(ctx);
  if (ctx.path === "/home") return renderHome(ctx);
  if (ctx.path === "/space") return renderSpace(ctx);
  if (ctx.path === "/datasets/new") return renderDatasetImport(ctx);
  if (isDataPage(ctx.path)) return renderDataWorkflow(ctx);
  if (ctx.path === "/admin/users") return renderUsers(ctx);
  if (isComputePage(ctx.path)) return renderCompute(ctx);
  if (isWorkflowPage(ctx.path)) return renderWorkflow(ctx);
  if (isAssistantPage(ctx.path)) return renderAssistant(ctx);
  if (!ctx.workspace && (ctx.kind || ctx.path === "/admin/audit")) return pageHeader("工作空间") + workspaceRequired(ctx);
  if (ctx.path === "/admin/audit") return renderAudit(ctx);
  if (ctx.kind) return ctx.assetId ? renderAssetDetail(ctx.kind, ctx) : renderAssets(ctx.kind, ctx);
  return renderPending(ctx.path);
});

watch(
  pageHtml,
  html => {
    emit("breadcrumb", html.trimStart().startsWith('<div class="breadcrumb">'));
  },
  { immediate: true }
);
</script>

<template>
  <div class="page-surface" v-html="pageHtml" />
</template>
