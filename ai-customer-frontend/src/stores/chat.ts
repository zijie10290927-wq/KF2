import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as chatApi from '@/api/chat'
import { streamChat } from '@/utils/sse'
import type { ChatMessage, ChatSession, FallbackData, SourceItem } from '@/types'

/** 对话状态：会话列表 / 当前会话 / 消息 / 流式状态 */
export const useChatStore = defineStore('chat', () => {
  const sessions = ref<ChatSession[]>([])
  const currentSessionId = ref<string>('')
  const messages = ref<ChatMessage[]>([])
  const isStreaming = ref(false)
  let abortController: AbortController | null = null

  const currentSession = computed(() =>
    sessions.value.find((s) => s.session_id === currentSessionId.value)
  )

  /** 加载会话列表 */
  async function loadSessions() {
    const res = await chatApi.listSessions()
    sessions.value = res.data || []
    if (!currentSessionId.value && sessions.value.length > 0) {
      await selectSession(sessions.value[0].session_id)
    }
    return sessions.value
  }

  /** 新建会话 */
  async function createSession(title = '新对话') {
    const res = await chatApi.createSession(title)
    sessions.value.unshift(res.data)
    currentSessionId.value = res.data.session_id
    messages.value = []
    return res.data
  }

  /** 选择会话 + 加载历史消息 */
  async function selectSession(sessionId: string) {
    currentSessionId.value = sessionId
    const res = await chatApi.getMessages(sessionId)
    // 后端返回分页结构 { list, total, page, page_size }，数组在 .list 字段
    const payload = res.data as any
    messages.value = Array.isArray(payload)
      ? payload
      : (payload?.list ?? [])
  }

  /** 删除会话 */
  async function deleteSession(sessionId: string) {
    await chatApi.deleteSession(sessionId)
    sessions.value = sessions.value.filter((s) => s.session_id !== sessionId)
    if (currentSessionId.value === sessionId) {
      currentSessionId.value = ''
      messages.value = []
    }
  }

  /** 发送消息并启动 SSE 流式接收 */
  async function sendMessage(content: string) {
    if (!currentSessionId.value || isStreaming.value) return
    if (!content.trim()) return

    // 立即插入用户消息（UI 即时反馈）
    const userMsg: ChatMessage = {
      message_id: 'tmp-' + Date.now(),
      session_id: currentSessionId.value,
      role: 'user',
      content,
      created_at: new Date().toISOString(),
    }
    messages.value.push(userMsg)

    // 预插入 AI 消息占位（流式追加）
    const aiMsg: ChatMessage = {
      message_id: 'tmp-ai-' + Date.now(),
      session_id: currentSessionId.value,
      role: 'assistant',
      content: '',
      created_at: new Date().toISOString(),
    }
    messages.value.push(aiMsg)

    isStreaming.value = true
    abortController = new AbortController()

    try {
      await streamChat({
        url: chatApi.streamUrl(),
        body: {
          session_id: currentSessionId.value,
          message: content,
        },
        signal: abortController.signal,
        callbacks: {
          onToken: (token) => {
            aiMsg.content += token
          },
          onSource: (sources: SourceItem[]) => {
            aiMsg.sources = sources
          },
          onFallback: (data: FallbackData) => {
            aiMsg.intent = 'fallback'
            // 由视图层展示兜底卡片，这里仅记录数据
            ;(aiMsg as any).fallback = data
          },
          onDone: (messageId) => {
            if (messageId) aiMsg.message_id = messageId
          },
          onError: (message) => {
            if (!aiMsg.content) {
              aiMsg.content = `⚠️ ${message}`
            }
          },
        },
      })
    } finally {
      isStreaming.value = false
      abortController = null
    }
  }

  /** 停止流式输出 */
  function stopStreaming() {
    if (abortController) {
      abortController.abort()
      abortController = null
    }
    isStreaming.value = false
  }

  /** 转人工客服 */
  async function transferToHuman(reason: string = '') {
    if (!currentSessionId.value) return null
    const res = await chatApi.transferToHuman(currentSessionId.value, reason)
    return res.data
  }

  /** 清空当前会话消息 */
  function clearMessages() {
    messages.value = []
  }

  return {
    sessions,
    currentSessionId,
    currentSession,
    messages,
    isStreaming,
    loadSessions,
    createSession,
    selectSession,
    deleteSession,
    sendMessage,
    stopStreaming,
    transferToHuman,
    clearMessages,
  }
})
