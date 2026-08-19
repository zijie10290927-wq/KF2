import request from './request'
import type { ApiResponse, KnowledgeDoc, PageResponse } from '@/types'

/** 分页文档列表 */
export function listDocs(params: {
  page?: number
  page_size?: number
  status?: string
  category?: string
  keyword?: string
}) {
  return request.get<unknown, ApiResponse<PageResponse<KnowledgeDoc>>>('/admin/knowledge/docs', {
    params,
  })
}

/** 文档详情 */
export function getDoc(docId: string) {
  return request.get<unknown, ApiResponse<KnowledgeDoc>>(`/admin/knowledge/docs/${docId}`)
}

/** 删除文档 */
export function deleteDoc(docId: string) {
  return request.delete<unknown, ApiResponse<null>>(`/admin/knowledge/docs/${docId}`)
}

/** 重建索引 */
export function reindexDoc(docId: string) {
  return request.post<unknown, ApiResponse<null>>(`/admin/knowledge/docs/${docId}/reindex`)
}

/** 上传文档（multipart/form-data） */
export function uploadDoc(file: File, category: string = '', chunkSize = 0, overlap = 0) {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('category', category)
  formData.append('chunk_size', String(chunkSize))
  formData.append('overlap', String(overlap))
  return request.post<unknown, ApiResponse<{ doc_id: string; status: string }>>(
    '/admin/knowledge/upload',
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' } }
  )
}
