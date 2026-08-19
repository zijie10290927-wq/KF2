<template>
  <div class="loading-spinner" :class="{ inline }">
    <span class="dot" />
    <span class="dot" />
    <span class="dot" />
  </div>
</template>

<script setup lang="ts">
defineProps<{ inline?: boolean }>()
</script>

<style scoped lang="scss">
.loading-spinner {
  display: flex;
  gap: 4px;
  align-items: center;
  padding: 4px 0;
  &.inline {
    display: inline-flex;
  }
  .dot {
    width: 6px;
    height: 6px;
    background: #909399;
    border-radius: 50%;
    animation: bounce 1.4s infinite ease-in-out both;
  }
  .dot:nth-child(1) {
    animation-delay: -0.32s;
  }
  .dot:nth-child(2) {
    animation-delay: -0.16s;
  }
}
@keyframes bounce {
  0%,
  80%,
  100% {
    transform: scale(0);
  }
  40% {
    transform: scale(1);
  }
}
</style>
