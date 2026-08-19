import request from './request'
import type { ApiResponse, ChatMessage, ChatSession } from '@/types'

/** 创建会话 */
export function createSession(title: string = '新对话') {
  return request.post<unknown, ApiResponse<ChatSession>>('/chat/sessions', { title })
}

/** 会话列表 */
export function listSessions() {
  return request.get<unknown, ApiResponse<ChatSession[]>>('/chat/sessions')
}

/** 获取会话消息 */
export function getMessages(sessionId: string) {
  return request.get<unknown, ApiResponse<ChatMessage[]>>(
    `/chat/sessions/${sessionId}/messages`
  )
}

/** 删除会话 */
export function deleteSession(sessionId: string) {
  return request.delete<unknown, ApiResponse<null>>(`/chat/sessions/${sessionId}`)
}

/** 转人工 */
export function transferToHuman(sessionId: string, reason: string = '') {
  return request.post<unknown, ApiResponse<{ transfer_url?: string; phone?: string }>>(
    '/chat/transfer-human',
    { session_id: sessionId, reason }
  )
}

// SSE 流式对话端点（直接拼绝对 URL 给 fetch 使用）
export function streamUrl(): string {
  const base = (import.meta.env.VITE_API_BASE_URL || '') + '/api/v1'
  return `${base}/chat/stream`
}
