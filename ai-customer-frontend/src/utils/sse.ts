/**
 * SSE 流式接收工具（核心）
 *
 * 实现思路：基于 XMLHttpRequest + onprogress（不用 fetch + ReadableStream，
 * 因为 Chrome 对 fetch 流的 SSE 连接关闭时报 net::ERR_ABORTED）。
 *
 * 关键：收到 done/error 终止事件后，不主动调用 xhr.abort()，而是等待后端
 * 自然关闭连接（后端在 yield done 后 generator 返回，StreamingResponse 关闭
 * HTTP 连接，浏览器收到 EOF 触发 onload）。这样可避免 Chrome 在 Network 面板
 * 报 net::ERR_ABORTED（abort() 即使是主动调用也会被 Chrome 标记为错误）。
 *
 * 事件协议（后端按 \n\n 分割）：
 *   - answer   → onToken(content)
 *   - source   → onSource(sources)
 *   - fallback → onFallback(data)
 *   - done     → onDone(message_id)
 *   - error    → onError(message)
 */

import type { SSECallbacks } from '@/types'

const TOKEN_KEY = 'ai_customer_token'

// 后端发送 done 后关闭连接的安全超时（ms）。
// 正常情况 <100ms，设 5s 兜底防止后端异常时前端长时间挂起。
const DONE_CLOSE_TIMEOUT_MS = 5000

interface StreamOptions {
  url: string
  body: any
  callbacks: SSECallbacks
  signal?: AbortSignal
}

/**
 * 发起 SSE 流式请求并按事件回调。
 * @param opts 请求配置（url / body / callbacks / signal）
 */
export function streamChat(opts: StreamOptions): Promise<void> {
  const { url, body, callbacks, signal } = opts
  const token = localStorage.getItem(TOKEN_KEY) || ''

  return new Promise<void>((resolve) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', url, true)
    xhr.setRequestHeader('Content-Type', 'application/json')
    xhr.setRequestHeader('Accept', 'text/event-stream')
    if (token) {
      xhr.setRequestHeader('Authorization', `Bearer ${token}`)
    }
    xhr.responseType = 'text'

    let buffer = ''
    let done = false
    let lastProcessedLength = 0
    let resolved = false
    let closeTimer: number | null = null

    const finish = () => {
      if (resolved) return
      resolved = true
      if (closeTimer !== null) {
        clearTimeout(closeTimer)
        closeTimer = null
      }
      resolve()
    }

    // 处理 buffer 中的完整 SSE 事件
    function processBuffer() {
      const segments = buffer.split('\n\n')
      // 保留最后未完整的段
      buffer = segments.pop() || ''

      for (const seg of segments) {
        const lines = seg.split('\n')
        for (const line of lines) {
          const trimmed = line.trim()
          if (!trimmed.startsWith('data:')) continue
          const jsonStr = trimmed.slice(5).trim()
          if (!jsonStr) continue
          try {
            const evt = JSON.parse(jsonStr)
            if (dispatchEvent(evt, callbacks)) {
              // 收到 done/error 终止事件：不主动 abort，
              // 等待后端关闭连接触发 onload。
              // 设置安全超时兜底，避免后端异常时挂起。
              done = true
              closeTimer = window.setTimeout(() => {
                // 超时仍未收到 onload，强制结束（不调 abort 以避免 ERR_ABORTED）
                finish()
              }, DONE_CLOSE_TIMEOUT_MS)
              return
            }
          } catch {
            // 忽略无法解析的事件
          }
        }
      }
    }

    // 增量接收数据
    xhr.onprogress = () => {
      if (done) return
      // xhr.responseText 是累积的，取新增部分
      const fullText = xhr.responseText
      if (fullText.length > lastProcessedLength) {
        buffer += fullText.substring(lastProcessedLength)
        lastProcessedLength = fullText.length
        processBuffer()
      }
    }

    // 请求完成（后端关闭连接，正常结束）
    xhr.onload = () => {
      // 先处理残留 buffer（可能含 done/error 事件）
      if (buffer.trim()) {
        const segments = buffer.split('\n\n')
        for (const seg of segments) {
          const lines = seg.split('\n')
          for (const line of lines) {
            const trimmed = line.trim()
            if (!trimmed.startsWith('data:')) continue
            const jsonStr = trimmed.slice(5).trim()
            if (!jsonStr) continue
            try {
              const evt = JSON.parse(jsonStr)
              dispatchEvent(evt, callbacks)
            } catch {
              /* ignore */
            }
          }
        }
        buffer = ''
      }
      // 如果已收到 done，直接结束
      if (done) {
        finish()
        return
      }
      // 未收到 done 但连接已关闭：HTTP 错误处理
      if (xhr.status === 401) {
        localStorage.removeItem(TOKEN_KEY)
        window.location.href = '/login'
      } else if (xhr.status === 403) {
        callbacks.onError?.('没有权限访问')
      } else if (xhr.status === 429) {
        callbacks.onError?.('请求过于频繁，请稍后重试')
      } else if (xhr.status >= 500) {
        callbacks.onError?.('服务器内部错误')
      } else if (xhr.status >= 400) {
        callbacks.onError?.(`HTTP ${xhr.status}`)
      }
      finish()
    }

    // 请求出错
    xhr.onerror = () => {
      if (done) {
        finish()
        return
      }
      callbacks.onError?.('网络异常，请稍后重试')
      finish()
    }

    // 请求被 abort（仅由外部 AbortSignal 触发）
    xhr.onabort = () => {
      if (!done) {
        // 用户主动取消
        callbacks.onDone?.('')
      }
      finish()
    }

    // 外部 AbortSignal（用户切换会话/导航离开时）
    if (signal) {
      if (signal.aborted) {
        callbacks.onDone?.('')
        finish()
        return
      }
      signal.addEventListener('abort', () => {
        xhr.abort()
      }, { once: true })
    }

    xhr.send(JSON.stringify(body))
  })
}

/**
 * 按 type 分发事件到对应回调。
 * @param evt 解析后的事件对象 { type, ... }
 * @param cb 回调集合
 * @returns true 如果是终止事件（done/error），应停止读取
 */
function dispatchEvent(evt: any, cb: SSECallbacks): boolean {
  switch (evt.type) {
    case 'answer':
      cb.onToken?.(evt.content || '')
      break
    case 'source':
      cb.onSource?.(evt.sources || [])
      break
    case 'fallback':
      cb.onFallback?.(evt.data || {})
      break
    case 'done':
      cb.onDone?.(evt.message_id || '')
      return true
    case 'error':
      cb.onError?.(evt.message || '流式响应错误')
      return true
    default:
      // 未知事件类型忽略
      break
  }
  return false
}
