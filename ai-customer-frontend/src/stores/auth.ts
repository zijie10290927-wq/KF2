import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as authApi from '@/api/auth'
import type { UserInfo } from '@/types'

const TOKEN_KEY = 'ai_customer_token'

/** 认证状态：token + userInfo */
export const useAuthStore = defineStore('auth', () => {
  const token = ref<string>(localStorage.getItem(TOKEN_KEY) || '')
  const userInfo = ref<UserInfo | null>(null)

  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => userInfo.value?.role === 'admin')

  /** 设置 Token 并持久化 */
  function setToken(t: string) {
    token.value = t
    localStorage.setItem(TOKEN_KEY, t)
  }

  /** 清除 Token */
  function clearToken() {
    token.value = ''
    localStorage.removeItem(TOKEN_KEY)
  }

  /** 登录 */
  async function login(username: string, password: string) {
    const res = await authApi.login(username, password)
    setToken(res.data.access_token)
    userInfo.value = res.data.user
    return res.data
  }

  /** 登出 */
  async function logout() {
    try {
      await authApi.logout()
    } catch {
      /* 忽略网络错误 */
    }
    clearToken()
    userInfo.value = null
  }

  /** 拉取当前用户信息 */
  async function fetchMe() {
    if (!token.value) return null
    try {
      const res = await authApi.getMe()
      userInfo.value = res.data
      return res.data
    } catch {
      clearToken()
      return null
    }
  }

  return {
    token,
    userInfo,
    isLoggedIn,
    isAdmin,
    setToken,
    clearToken,
    login,
    logout,
    fetchMe,
  }
})
