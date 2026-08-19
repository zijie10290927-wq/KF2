<template>
  <div class="typing">
    <span class="dot" />
    <span class="dot" />
    <span class="dot" />
  </div>
</template>

<script setup lang="ts">
// AI 正在输出的打字动画占位
</script>

<style scoped lang="scss">
.typing {
  display: inline-flex;
  gap: 4px;
  padding: 8px 12px;
  .dot {
    width: 8px;
    height: 8px;
    background: #909399;
    border-radius: 50%;
    animation: typing 1.4s infinite ease-in-out both;
  }
  .dot:nth-child(2) {
    animation-delay: 0.2s;
  }
  .dot:nth-child(3) {
    animation-delay: 0.4s;
  }
}
@keyframes typing {
  0%,
  60%,
  100% {
    transform: translateY(0);
    opacity: 0.4;
  }
  30% {
    transform: translateY(-4px);
    opacity: 1;
  }
}
</style>
