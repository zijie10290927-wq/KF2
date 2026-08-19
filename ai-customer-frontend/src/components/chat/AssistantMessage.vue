<template>
  <div class="msg-row assistant">
    <div class="avatar">AI</div>
    <div class="content-wrap">
      <div class="bubble">
        <MarkdownRenderer v-if="message.content" :content="message.content" />
        <TypingIndicator v-else-if="streaming" />
        <span v-else class="empty">（无内容）</span>
      </div>
      <div v-if="message.sources && message.sources.length" class="sources">
        <div class="sources-title">📚 引用来源</div>
        <div v-for="(s, i) in message.sources" :key="i" class="source-item">
          <span v-if="s.filename" class="filename">{{ s.filename }}</span>
          <span class="snippet">{{ s.content.slice(0, 120) }}...</span>
        </div>
      </div>
      <FallbackCard v-if="(message as any).fallback" :data="(message as any).fallback" @transfer="onTransfer" />
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ChatMessage, FallbackData } from '@/types'
import MarkdownRenderer from '@/components/common/MarkdownRenderer.vue'
import TypingIndicator from './TypingIndicator.vue'
import FallbackCard from './FallbackCard.vue'

defineProps<{ message: ChatMessage; streaming?: boolean }>()
const emit = defineEmits<{ (e: 'transfer', data: FallbackData): void }>()

function onTransfer(data: FallbackData) {
  emit('transfer', data)
}
</script>

<style scoped lang="scss">
.msg-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin: 12px 0;
  .avatar {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    background: #409eff;
    color: #fff;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    font-size: 14px;
  }
  .content-wrap {
    max-width: 70%;
  }
  .bubble {
    background: #fff;
    border: 1px solid #ebeef5;
    padding: 10px 14px;
    border-radius: 12px 12px 12px 2px;
    line-height: 1.6;
    word-break: break-word;
    .empty {
      color: #c0c4cc;
      font-size: 13px;
    }
  }
  .sources {
    margin-top: 8px;
    background: #f4f4f5;
    border-radius: 8px;
    padding: 8px 12px;
    .sources-title {
      font-size: 12px;
      color: #909399;
      margin-bottom: 4px;
    }
    .source-item {
      font-size: 12px;
      color: #606266;
      margin: 4px 0;
      .filename {
        color: #409eff;
        margin-right: 6px;
      }
      .snippet {
        color: #909399;
      }
    }
  }
}
</style>
