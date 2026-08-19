import axios, {
  AxiosError,
  type AxiosInstance,
  type AxiosResponse,
  type InternalAxiosRequestConfig,
} from 'axios'
import { ElMessage } from 'element-plus'
import type { ApiResponse } from '@/types'

const TOKEN_KEY = 'ai_customer_token'

const baseURL = (import.meta.env.VITE_API_BASE_URL || '') + '/api/v1'

/** Axios 实例 */
const request: AxiosInstance = axios.create({
  baseURL,
  timeout: 30000,
})

// 请求拦截器：注入 Bearer Token
request.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem(TOKEN_KEY)
    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// 响应拦截器：统一处理 code / 401 / 429
// 注：返回 data 而非 response，调用方使用 request.xxx<T, ApiResponse<X>> 形式接收
request.interceptors.response.use(
  (response: AxiosResponse) => {
    const data = response.data as ApiResponse
    if (data.code !== 0) {
      ElMessage.error(data.message || '请求失败')
      return Promise.reject(new Error(data.message || '请求失败'))
    }
    return data as unknown as AxiosResponse
  },
  (error: AxiosError<ApiResponse>) => {
    if (!error.response) {
      ElMessage.error('网络异常，请稍后重试')
      return Promise.reject(error)
    }
    const { status, data } = error.response
    if (status === 401) {
      localStorage.removeItem(TOKEN_KEY)
      ElMessage.error('登录已过期，请重新登录')
      window.location.href = '/login'
      return Promise.reject(error)
    }
    if (status === 429) {
      ElMessage.error('请求过于频繁，请稍后重试')
      return Promise.reject(error)
    }
    const msg = data?.message || `请求失败 (${status})`
    ElMessage.error(msg)
    return Promise.reject(error)
  }
)

export default request
