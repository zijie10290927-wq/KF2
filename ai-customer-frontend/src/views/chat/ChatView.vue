<template>
  <div class="chat-view">
    <SessionSidebar
      :sessions="chatStore.sessions"
      :current-id="chatStore.currentSessionId"
      @create="onCreateSession"
      @select="chatStore.selectSession"
    />
    <div class="chat-main">
      <div class="chat-header">
        <div class="title">{{ chatStore.currentSession?.title || 'AI 智能客服' }}</div>
        <div class="user-actions">
          <el-dropdown @command="onUserCommand">
            <span class="user-info">
              {{ authStore.userInfo?.username || '用户' }}
              <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item v-if="authStore.isAdmin" command="admin">管理后台</el-dropdown-item>
                <el-dropdown-item command="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </div>
      <div class="chat-body">
        <div v-if="!chatStore.currentSessionId && !chatStore.messages.length" class="welcome">
          <h2>👋 欢迎使用 AI 智能客服</h2>
          <p>请先创建会话或选择历史会话开始对话</p>
          <el-button type="primary" size="large" @click="onCreateSession">
            开始新对话
          </el-button>
        </div>
        <template v-else>
          <MessageList
            :messages="chatStore.messages"
            :is-streaming="chatStore.isStreaming"
            @transfer="onTransfer"
          />
          <ChatInput
            :disabled="chatStore.isStreaming"
            @send="chatStore.sendMessage"
            @stop="chatStore.stopStreaming"
          />
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowDown } from '@element-plus/icons-vue'
import { useChatStore } from '@/stores/chat'
import { useAuthStore } from '@/stores/auth'
import SessionSidebar from '@/components/chat/SessionSidebar.vue'
import MessageList from '@/components/chat/MessageList.vue'
import ChatInput from '@/components/chat/ChatInput.vue'
import type { FallbackData } from '@/types'

const router = useRouter()
const chatStore = useChatStore()
const authStore = useAuthStore()

onMounted(async () => {
  try {
    await chatStore.loadSessions()
    if (!chatStore.sessions.length) {
      await chatStore.createSession()
    }
  } catch (e: any) {
    // 会话列表加载失败不阻塞页面
    ElMessage.warning('会话列表加载失败，可点击「新建」开始')
  }
})

async function onCreateSession() {
  try {
    await chatStore.createSession()
  } catch (e: any) {
    ElMessage.error('创建会话失败')
  }
}

async function onTransfer(_data: FallbackData) {
  try {
    const res = await chatStore.transferToHuman('用户主动转人工')
    if (res?.transfer_url) {
      window.open(res.transfer_url, '_blank')
    } else if (res?.phone) {
      ElMessage.success(`人工客服电话：${res.phone}`)
    } else {
      ElMessage.success('已转接人工客服，请稍候')
    }
  } catch {
    ElMessage.error('转人工失败')
  }
}

async function onUserCommand(command: string) {
  if (command === 'logout') {
    await authStore.logout()
    router.push('/login')
  } else if (command === 'admin') {
    router.push('/admin/dashboard')
  }
}
</script>

<style scoped lang="scss">
.chat-view {
  display: flex;
  height: 100vh;
  background: #f5f7fa;
}
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.chat-header {
  height: 56px;
  background: #fff;
  border-bottom: 1px solid #ebeef5;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  .title {
    font-size: 16px;
    font-weight: 600;
    color: #303133;
  }
  .user-info {
    cursor: pointer;
    color: #606266;
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }
}
.chat-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.welcome {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  color: #606266;
  h2 {
    color: #303133;
    margin: 0;
  }
}
</style>
