import dayjs from 'dayjs'

/** 格式化日期时间 */
export function formatDateTime(iso: string | undefined | null): string {
  if (!iso) return '-'
  return dayjs(iso).format('YYYY-MM-DD HH:mm:ss')
}

/** 格式化文件大小 */
export function formatFileSize(bytes: number | undefined | null): string {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let i = 0
  let size = bytes
  while (size >= 1024 && i < units.length - 1) {
    size /= 1024
    i++
  }
  return `${size.toFixed(1)} ${units[i]}`
}

/** 文档状态映射为 Element Plus tag 类型 */
export function docStatusTagType(status: string): 'info' | 'warning' | 'success' | 'danger' {
  const map: Record<string, 'info' | 'warning' | 'success' | 'danger'> = {
    uploading: 'info',
    processing: 'warning',
    indexed: 'success',
    failed: 'danger',
  }
  return map[status] || 'info'
}

/** 文档状态中文标签 */
export function docStatusLabel(status: string): string {
  const map: Record<string, string> = {
    uploading: '上传中',
    processing: '处理中',
    indexed: '已索引',
    failed: '失败',
  }
  return map[status] || status
}
