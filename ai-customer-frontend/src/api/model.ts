import request from './request'
import type { ApiResponse, ModelConfig, FallbackConfig } from '@/types'

/** 模型列表 */
export function listModels(enabledOnly = false) {
  return request.get<unknown, ApiResponse<ModelConfig[]>>('/admin/config/model', {
    params: { enabled_only: enabledOnly },
  })
}

/** 新增模型 */
export function createModel(payload: Partial<ModelConfig> & { api_key: string }) {
  return request.post<unknown, ApiResponse<ModelConfig>>('/admin/config/model', payload)
}

/** 更新模型 */
export function updateModel(
  id: number,
  payload: Partial<ModelConfig> & { api_key?: string }
) {
  return request.put<unknown, ApiResponse<ModelConfig>>(`/admin/config/model/${id}`, payload)
}

/** 删除模型 */
export function deleteModel(id: number) {
  return request.delete<unknown, ApiResponse<null>>(`/admin/config/model/${id}`)
}

/** 启用/禁用 */
export function toggleModel(id: number, enabled: boolean) {
  return request.patch<unknown, ApiResponse<ModelConfig>>(
    `/admin/config/model/${id}/toggle`,
    { enabled }
  )
}

/** 设为默认 */
export function setDefaultModel(id: number) {
  return request.patch<unknown, ApiResponse<ModelConfig>>(`/admin/config/model/${id}/default`)
}

/** 获取兜底配置 */
export function getFallbackConfig() {
  return request.get<unknown, ApiResponse<FallbackConfig>>('/admin/config/fallback-message')
}

/** 更新兜底配置 */
export function updateFallbackConfig(payload: Partial<FallbackConfig>) {
  return request.put<unknown, ApiResponse<FallbackConfig>>(
    '/admin/config/fallback-message',
    payload
  )
}
