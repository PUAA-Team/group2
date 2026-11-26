<script setup lang="ts">
import { computed } from "vue";
import { renderAuth } from "@live/pages/auth.js";
import { ctx, renderTick } from "@/stores/app";

const authHtml = computed(() => {
  void renderTick.value;
  return renderAuth(ctx.setup, ctx.error);
});
</script>

<template>
  <div v-if="ctx.loading" class="live-loading" role="status">正在连接平台…</div>
  <div v-else v-html="authHtml" />
</template>
