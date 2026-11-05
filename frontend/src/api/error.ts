import axios from 'axios'

/** 从后端错误响应中提取中文提示，避免把技术细节直接暴露给用户。 */
export function extractError(error: unknown, fallback = '操作失败，请稍后重试'): string {
  if (axios.isAxiosError(error)) {
    const detail = (error.response?.data as { detail?: unknown } | undefined)?.detail
    if (typeof detail === 'string' && detail) return detail
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0] as { msg?: string }
      if (first?.msg) return first.msg
    }
    if (!error.response) return '无法连接后端服务，请确认后端已启动'
  }
  return fallback
}
