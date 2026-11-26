<script setup lang="ts">
import { computed, nextTick, watch } from "vue";
import { renderDialog } from "@live/dialogs.js";
import { ctx, renderTick } from "@/stores/app";

const dialogHtml = computed(() => {
  void renderTick.value;
  return renderDialog(ctx.ui.modal, ctx);
});

watch(
  () => ctx.ui.modal,
  async modal => {
    if (modal) {
      await nextTick();
      const el = document.querySelector(
        '[role="dialog"] input:not([readonly]),[role="dialog"] select,[role="dialog"] button'
      ) as HTMLElement | null;
      el?.focus({ preventScroll: true });
    }
  }
);
</script>

<template>
  <div v-if="dialogHtml" v-html="dialogHtml" />
</template>
