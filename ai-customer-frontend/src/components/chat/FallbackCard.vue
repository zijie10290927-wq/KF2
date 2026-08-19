<template>
  <div class="fallback-card">
    <div class="title">⚠️ 抱歉，暂时无法回答该问题</div>
    <div class="message">{{ data.reason || data.transfer_url || '是否需要转人工客服？' }}</div>
    <div class="actions">
      <el-button v-if="data.transfer_url" type="primary" size="small" @click="onTransfer">
        转接人工客服
      </el-button>
      <el-button v-if="data.phone" size="small" @click="onCall">
        拨打 {{ data.phone }}
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { FallbackData } from '@/types'
defineProps<{ data: FallbackData }>()
const emit = defineEmits<{ (e: 'transfer', data: FallbackData): void }>()

function onTransfer() {
  emit('transfer', {} as FallbackData)
}
function onCall() {
  // 简单弹窗提示
}
</script>

<style scoped lang="scss">
.fallback-card {
  margin-top: 8px;
  border: 1px solid #f56c6c;
  background: #fef0f0;
  border-radius: 8px;
  padding: 12px;
  .title {
    color: #f56c6c;
    font-weight: 600;
    margin-bottom: 6px;
  }
  .message {
    color: #606266;
    font-size: 14px;
    margin-bottom: 8px;
  }
}
</style>
