import request from './request'
import type { ApiResponse, LoginResponse, UserInfo } from '@/types'

/** 登录 */
export function login(username: string, password: string) {
  return request.post<unknown, ApiResponse<LoginResponse>>('/auth/login', {
    username,
    password,
  })
}

/** 登出 */
export function logout() {
  return request.post<unknown, ApiResponse<null>>('/auth/logout')
}

/** 当前用户信息 */
export function getMe() {
  return request.get<unknown, ApiResponse<UserInfo>>('/auth/me')
}

/** 注册 */
export function register(username: string, password: string) {
  return request.post<unknown, ApiResponse<UserInfo>>('/auth/register', {
    username,
    password,
  })
}
