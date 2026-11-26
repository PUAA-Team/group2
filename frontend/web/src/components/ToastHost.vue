<script setup lang="ts">
import { toastMessage } from "@/stores/app";
</script>

<template>
  <div v-if="toastMessage" id="live-toast" class="live-toast" role="status">
    {{ toastMessage }}
  </div>
</template>
