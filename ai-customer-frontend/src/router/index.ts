import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/chat',
  },
  {
    path: '/chat',
    name: 'Chat',
    component: () => import('@/views/chat/ChatView.vue'),
    meta: { title: 'AI 智能客服', requiresAuth: true },
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { title: '登录', requiresAuth: false },
  },
  {
    path: '/admin',
    component: () => import('@/views/admin/AdminLayout.vue'),
    meta: { requiresAuth: true, requiresAdmin: true },
    redirect: '/admin/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/admin/Dashboard.vue'),
        meta: { title: '仪表盘', requiresAdmin: true },
      },
      {
        path: 'knowledge',
        name: 'KnowledgeManage',
        component: () => import('@/views/admin/KnowledgeManage.vue'),
        meta: { title: '知识库管理', requiresAdmin: true },
      },
      {
        path: 'model',
        name: 'ModelConfig',
        component: () => import('@/views/admin/ModelConfig.vue'),
        meta: { title: '模型配置', requiresAdmin: true },
      },
      {
        path: 'fallback',
        name: 'FallbackConfig',
        component: () => import('@/views/admin/FallbackConfig.vue'),
        meta: { title: '兜底话术', requiresAdmin: true },
      },
      {
        path: 'chat-logs',
        name: 'ChatLogs',
        component: () => import('@/views/admin/ChatLogs.vue'),
        meta: { title: '对话记录', requiresAdmin: true },
      },
      {
        path: 'users',
        name: 'UserManage',
        component: () => import('@/views/admin/UserManage.vue'),
        meta: { title: '用户管理', requiresAdmin: true },
      },
      {
        path: 'channels',
        name: 'ChannelManagement',
        component: () => import('@/views/admin/ChannelManagement.vue'),
        meta: { title: '渠道管理', requiresAdmin: true },
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/chat',
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 全局前置守卫：登录 + 权限校验
router.beforeEach(async (to, from, next) => {
  const authStore = useAuthStore()

  // 已有 token 但未加载用户信息时，先拉取
  if (authStore.isLoggedIn && !authStore.userInfo) {
    await authStore.fetchMe()
  }

  if (to.meta.requiresAuth && !authStore.isLoggedIn) {
    next({ name: 'Login', query: { redirect: to.fullPath } })
    return
  }

  if (to.meta.requiresAdmin && !authStore.isAdmin) {
    next({ name: 'Chat' })
    return
  }

  if (to.meta.title) {
    document.title = `${to.meta.title} - AI 智能客服`
  }
  next()
})

export default router
