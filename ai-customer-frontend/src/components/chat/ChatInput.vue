<template>
  <div class="chat-input">
    <textarea
      v-model="text"
      class="textarea"
      placeholder="输入您的问题... (Enter 发送，Shift+Enter 换行)"
      :disabled="disabled"
      @keydown.enter.exact.prevent="onSend"
    />
    <div class="actions">
      <el-button v-if="disabled" type="danger" plain size="small" @click="$emit('stop')">
        停止
      </el-button>
      <el-button type="primary" :disabled="disabled || !text.trim()" @click="onSend">
        发送
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const props = defineProps<{ disabled?: boolean }>()
const emit = defineEmits<{ (e: 'send', content: string): void; (e: 'stop'): void }>()

const text = ref('')

function onSend() {
  const content = text.value.trim()
  if (!content || props.disabled) return
  emit('send', content)
  text.value = ''
}
</script>

<style scoped lang="scss">
.chat-input {
  border-top: 1px solid #ebeef5;
  background: #fff;
  padding: 12px 16px;
  .textarea {
    width: 100%;
    min-height: 60px;
    max-height: 140px;
    resize: none;
    border: 1px solid #dcdfe6;
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 14px;
    outline: none;
    &:focus {
      border-color: #409eff;
    }
  }
  .actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    margin-top: 8px;
  }
}
</style>
