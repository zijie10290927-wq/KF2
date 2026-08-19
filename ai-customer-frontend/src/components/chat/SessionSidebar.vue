<template>
  <div class="session-sidebar">
    <div class="header">
      <span>会话列表</span>
      <el-button type="primary" size="small" @click="$emit('create')">+ 新建</el-button>
    </div>
    <div class="list">
      <div
        v-for="s in sessions"
        :key="s.session_id"
        class="item"
        :class="{ active: s.session_id === currentId }"
        @click="$emit('select', s.session_id)"
      >
        <div class="title">{{ s.title }}</div>
        <div class="time">{{ formatDateTime(s.updated_at) }}</div>
      </div>
      <div v-if="!sessions.length" class="empty">暂无会话</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ChatSession } from '@/types'
import { formatDateTime } from '@/utils/format'

defineProps<{
  sessions: ChatSession[]
  currentId: string
}>()
defineEmits<{
  (e: 'create'): void
  (e: 'select', id: string): void
}>()
</script>

<style scoped lang="scss">
.session-sidebar {
  width: 240px;
  border-right: 1px solid #ebeef5;
  background: #fff;
  display: flex;
  flex-direction: column;
  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 16px;
    border-bottom: 1px solid #ebeef5;
    font-weight: 600;
  }
  .list {
    flex: 1;
    overflow-y: auto;
    padding: 4px;
  }
  .item {
    padding: 8px 12px;
    border-radius: 6px;
    cursor: pointer;
    &.active {
      background: #ecf5ff;
    }
    &:hover {
      background: #f5f7fa;
    }
    .title {
      font-size: 14px;
      color: #303133;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .time {
      font-size: 12px;
      color: #909399;
      margin-top: 2px;
    }
  }
  .empty {
    text-align: center;
    color: #c0c4cc;
    padding: 24px;
    font-size: 13px;
  }
}
</style>
