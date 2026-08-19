<template>
  <div class="admin-layout">
    <aside class="sidebar">
      <div class="logo">⚙️ 管理后台</div>
      <el-menu
        :default-active="route.path"
        class="menu"
        router
      >
        <el-menu-item index="/admin/dashboard">
          <el-icon><DataLine /></el-icon>
          <span>仪表盘</span>
        </el-menu-item>
        <el-menu-item index="/admin/knowledge">
          <el-icon><Document /></el-icon>
          <span>知识库管理</span>
        </el-menu-item>
        <el-menu-item index="/admin/model">
          <el-icon><Setting /></el-icon>
          <span>模型配置</span>
        </el-menu-item>
        <el-menu-item index="/admin/fallback">
          <el-icon><ChatDotRound /></el-icon>
          <span>兜底话术</span>
        </el-menu-item>
        <el-menu-item index="/admin/chat-logs">
          <el-icon><Tickets /></el-icon>
          <span>对话记录</span>
        </el-menu-item>
        <el-menu-item index="/admin/users">
          <el-icon><User /></el-icon>
          <span>用户管理</span>
        </el-menu-item>
        <el-menu-item index="/admin/channels">
          <el-icon><Connection /></el-icon>
          <span>渠道管理</span>
        </el-menu-item>
      </el-menu>
      <div class="back-chat">
        <el-button text @click="router.push('/chat')">
          ← 返回对话
        </el-button>
      </div>
    </aside>
    <main class="content">
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import {
  Connection,
  DataLine,
  Document,
  Setting,
  ChatDotRound,
  Tickets,
  User,
} from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
</script>

<style scoped lang="scss">
.admin-layout {
  display: flex;
  height: 100vh;
  background: #f5f7fa;
}
.sidebar {
  width: 220px;
  background: #fff;
  border-right: 1px solid #ebeef5;
  display: flex;
  flex-direction: column;
  .logo {
    height: 56px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 16px;
    font-weight: 600;
    border-bottom: 1px solid #ebeef5;
    color: #303133;
  }
  .menu {
    flex: 1;
    border-right: none;
  }
  .back-chat {
    padding: 12px;
    border-top: 1px solid #ebeef5;
  }
}
.content {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}
</style>
