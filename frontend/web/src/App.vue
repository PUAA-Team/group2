<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { pageTitle } from "@live/components.js";
import { bootstrapApp, ctx, renderTick } from "@/stores/app";
import AppShell from "@/components/AppShell.vue";
import AuthView from "@/components/AuthView.vue";
import ModalHost from "@/components/ModalHost.vue";
import ToastHost from "@/components/ToastHost.vue";
import WorkspaceContent from "@/views/WorkspaceContent.vue";

const hasCustomBreadcrumb = ref(false);
const title = computed(() => pageTitle(ctx.path || "/home"));

watch(
  [() => ctx.session, () => ctx.setup.initialized, title, renderTick],
  () => {
    if (!ctx.session) {
      document.title = `${ctx.setup.initialized ? "登录" : "首次设置"} · 模训平台`;
      return;
    }
    const heading = document.querySelector(".page-heading h1")?.textContent;
    document.title = `${heading || title.value || "工作台"} · 模训平台`;
  },
  { flush: "post" }
);

onMounted(() => {
  bootstrapApp();
});
</script>

<template>
  <AuthView v-if="!ctx.session" />
  <AppShell v-else :title="title" :has-custom-breadcrumb="hasCustomBreadcrumb">
    <WorkspaceContent @breadcrumb="hasCustomBreadcrumb = $event" />
  </AppShell>
  <ModalHost />
  <ToastHost />
</template>
