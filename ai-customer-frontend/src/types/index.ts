// 全局 TypeScript 类型定义

/** 统一响应契约 */
export interface ApiResponse<T = any> {
  code: number
  message: string
  data: T
}

/** 分页响应 */
export interface PageResponse<T = any> {
  list: T[]
  total: number
  page: number
  page_size: number
}

/** 用户信息 */
export interface UserInfo {
  id: number
  username: string
  role: 'user' | 'admin'
  status: number
  created_at?: string
  updated_at?: string
}

/** 登录响应 */
export interface LoginResponse {
  access_token: string
  token_type: string
  user: UserInfo
}

/** 对话消息 */
export interface ChatMessage {
  message_id: string
  session_id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  intent?: string | null
  sources?: SourceItem[] | null
  model_used?: string | null
  tokens_used?: number | null
  created_at: string
}

/** 引用来源 */
export interface SourceItem {
  doc_id?: string
  filename?: string
  content: string
  score?: number
  chunk_id?: string
}

/** 兜底配置 */
export interface FallbackConfig {
  fallback_message: string
  show_transfer_button: boolean
  show_phone: boolean
  phone_number: string
}

/** 兜底触发数据 */
export interface FallbackData {
  reason: string
  transfer_url?: string
  phone?: string
}

/** SSE 事件回调接口 */
export interface SSECallbacks {
  onToken?: (token: string) => void
  onSource?: (sources: SourceItem[]) => void
  onFallback?: (data: FallbackData) => void
  onDone?: (messageId: string) => void
  onError?: (message: string) => void
}

/** 会话 */
export interface ChatSession {
  session_id: string
  title: string
  status: 'active' | 'closed' | 'transferred'
  created_at: string
  updated_at: string
}

/** 知识库文档 */
export interface KnowledgeDoc {
  doc_id: string
  filename: string
  file_type: string
  file_size: number
  category?: string | null
  chunk_count: number
  status: 'uploading' | 'processing' | 'indexed' | 'failed'
  error_msg?: string | null
  created_at: string
}

/** 模型配置 */
export interface ModelConfig {
  id: number
  model_name: string
  api_base: string
  temperature: number
  max_tokens: number
  enabled: boolean
  is_default: boolean
  created_at: string
  updated_at: string
}

// ===== 渠道适配层（Section 11） =====

/** 渠道配置（管理后台） */
export interface ChannelConfig {
  platform: string
  display_name: string
  enabled: boolean
  api_token?: string | null
  webhook_secret?: string | null
  app_key?: string | null
  api_base?: string | null
  remark?: string | null
  webhook_url?: string | null
}

/** 渠道总览统计 */
export interface ChannelOverview {
  today_messages: number
  active_channels: number
  avg_response_time_ms: number
  transfer_rate: number
  channels: ChannelStatusItem[]
}

/** 渠道状态项 */
export interface ChannelStatusItem {
  platform: string
  display_name: string
  enabled: boolean
  today_messages: number
  status: string
}

/** 渠道会话记录 */
export interface ChannelConversation {
  id: number
  platform: string
  external_session_id: string
  external_user_id?: string | null
  external_user_name?: string | null
  internal_session_id: string
  channel_type?: string | null
  status: string
  created_at: string
  updated_at: string
}

/** 渠道会话消息 */
export interface ChannelConversationMessage {
  id: number
  message_id?: string | null
  session_id: string
  role: string
  content: string
  intent?: string | null
  sources?: any | null
  model_used?: string | null
  tokens_used?: number | null
  created_at: string
}

/** Webhook 日志 */
export interface WebhookLog {
  id: number
  platform: string
  message_id?: string | null
  status: string
  raw_body?: string | null
  error?: string | null
  created_at: string
}
