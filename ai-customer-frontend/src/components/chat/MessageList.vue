<template>
  <div ref="listRef" class="message-list">
    <div v-for="msg in messages" :key="msg.message_id">
      <UserMessage v-if="msg.role === 'user'" :message="msg" />
      <AssistantMessage
        v-else-if="msg.role === 'assistant'"
        :message="msg"
        :streaming="isStreaming && msg === lastMessage"
        @transfer="$emit('transfer', $event)"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import type { ChatMessage, FallbackData } from '@/types'
import UserMessage from './UserMessage.vue'
import AssistantMessage from './AssistantMessage.vue'

const props = defineProps<{
  messages: ChatMessage[]
  isStreaming: boolean
}>()
defineEmits<{ (e: 'transfer', data: FallbackData): void }>()

const listRef = ref<HTMLElement>()
const lastMessage = computed(() => props.messages[props.messages.length - 1])

// 消息变化时自动滚动到底部
watch(
  () => props.messages.map((m) => m.content).join(''),
  () => {
    nextTick(() => {
      if (listRef.value) {
        listRef.value.scrollTop = listRef.value.scrollHeight
      }
    })
  }
)
</script>

<style scoped lang="scss">
.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 16px 24px;
}
</style>
