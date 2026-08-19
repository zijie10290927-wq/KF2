import request from './request'
import type {
  ApiResponse,
  ChannelConfig,
  ChannelConversation,
  ChannelConversationMessage,
  ChannelOverview,
  WebhookLog,
} from '@/types'

/** 渠道总览统计 */
export function getChannelOverview() {
  return request.get<unknown, ApiResponse<ChannelOverview>>('/admin/channels/overview')
}

/** 获取所有渠道配置列表 */
export function getChannelConfigs() {
  return request.get<unknown, ApiResponse<ChannelConfig[]>>('/admin/channels/configs')
}

/** 保存/更新渠道配置 */
export function saveChannelConfig(config: ChannelConfig) {
  return request.post<unknown, ApiResponse<ChannelConfig>>('/admin/channels/configs', config)
}

/** 启用/停用渠道 */
export function toggleChannelStatus(platform: string, enabled: boolean) {
  return request.put<unknown, ApiResponse<null>>(
    `/admin/channels/${platform}/status`,
    null,
    { params: { enabled } }
  )
}

/** 测试渠道连接 */
export function testChannelConnection(platform: string) {
  return request.post<unknown, ApiResponse<{ success: boolean; message?: string; [k: string]: any }>>(
    `/admin/channels/${platform}/test`
  )
}

/** 会话记录列表（含筛选 + 分页） */
export function getConversations(params: {
  platform?: string
  status?: string
  keyword?: string
  page: number
  page_size: number
}) {
  return request.get<unknown, ApiResponse<{ items: ChannelConversation[]; total: number; page: number; page_size: number }>>(
    '/admin/channels/conversations',
    { params }
  )
}

/** 会话消息详情 */
export function getConversationMessages(sessionId: string) {
  return request.get<unknown, ApiResponse<ChannelConversationMessage[]>>(
    `/admin/channels/conversations/${sessionId}/messages`
  )
}

/** Webhook 请求日志 */
export function getWebhookLogs(params: {
  platform?: string
  status?: string
  page: number
  page_size: number
}) {
  return request.get<unknown, ApiResponse<{ items: WebhookLog[]; total: number; page: number; page_size: number }>>(
    '/admin/channels/webhook-logs',
    { params }
  )
}
