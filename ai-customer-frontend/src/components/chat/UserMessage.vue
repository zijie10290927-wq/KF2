<template>
  <div class="msg-row user">
    <div class="bubble">{{ message.content }}</div>
    <div class="avatar">我</div>
  </div>
</template>

<script setup lang="ts">
import type { ChatMessage } from '@/types'
defineProps<{ message: ChatMessage }>()
</script>

<style scoped lang="scss">
.msg-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin: 12px 0;
  justify-content: flex-end;
  .bubble {
    background: #409eff;
    color: #fff;
    padding: 10px 14px;
    border-radius: 12px 12px 2px 12px;
    max-width: 70%;
    line-height: 1.6;
    word-break: break-word;
  }
  .avatar {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    background: #67c23a;
    color: #fff;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    font-size: 14px;
  }
}
</style>
