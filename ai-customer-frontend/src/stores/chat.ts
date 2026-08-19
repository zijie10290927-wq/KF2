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
  /**
   * 流序号（B5 竞态修复）：
   * 每次 stopStreaming / 新 sendMessage 都会自增。
   * 只有「当前代」的流允许重置全局状态 / 写入消息，
   * 旧流的迟到回调与 finally 一律作废，避免：
   * 1) 切换会话后旧流 token 写进新会话消息
   * 2) 旧流 finally 把新流的 isStreaming 错误清掉
   */
  let streamSeq = 0

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
    stopStreaming() // B5: 切换前终止旧流，避免旧流回调污染新会话
    const res = await chatApi.createSession(title)
    sessions.value.unshift(res.data)
    currentSessionId.value = res.data.session_id
    messages.value = []
    return res.data
  }

  /** 选择会话 + 加载历史消息 */
  async function selectSession(sessionId: string) {
    if (currentSessionId.value === sessionId) return
    stopStreaming() // B5: 切换会话立即终止旧流，否则 isStreaming 卡住且旧流继续写入
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
    if (currentSessionId.value === sessionId) {
      stopStreaming() // B5: 删除当前会话时终止进行中的流
    }
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
    const myStream = ++streamSeq
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
            if (streamSeq !== myStream) return // B5: 旧流迟到 token 丢弃
            aiMsg.content += token
          },
          onSource: (sources: SourceItem[]) => {
            if (streamSeq !== myStream) return
            aiMsg.sources = sources
          },
          onFallback: (data: FallbackData) => {
            if (streamSeq !== myStream) return
            aiMsg.intent = 'fallback'
            // 由视图层展示兜底卡片，这里仅记录数据
            ;(aiMsg as any).fallback = data
          },
          onDone: (messageId) => {
            if (streamSeq !== myStream) return
            if (messageId) aiMsg.message_id = messageId
          },
          onError: (message) => {
            if (streamSeq !== myStream) return
            if (!aiMsg.content) {
              aiMsg.content = `⚠️ ${message}`
            }
          },
        },
      })
    } finally {
      // B5: 只有「当前代」的流才能重置全局状态，
      // 否则旧流的 finally 会把新流的 isStreaming/abortController 清掉
      if (streamSeq === myStream) {
        isStreaming.value = false
        abortController = null
      }
    }
  }

  /** 停止流式输出 */
  function stopStreaming() {
    if (abortController) {
      streamSeq++ // 作废旧流的回调与 finally 写入权
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
