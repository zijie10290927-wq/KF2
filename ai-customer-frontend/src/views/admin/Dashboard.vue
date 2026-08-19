<template>
  <div class="dashboard">
    <h2>仪表盘</h2>
    <el-row :gutter="16">
      <el-col :span="6">
        <el-card>
          <div class="stat-label">会话总数</div>
          <div class="stat-value">{{ stats.sessions }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card>
          <div class="stat-label">知识库文档</div>
          <div class="stat-value">{{ stats.docs }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card>
          <div class="stat-label">启用模型</div>
          <div class="stat-value">{{ stats.models }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card>
          <div class="stat-label">注册用户</div>
          <div class="stat-value">{{ stats.users }}</div>
        </el-card>
      </el-col>
    </el-row>
    <el-card class="welcome-card">
      <h3>欢迎来到 AI 智能客服管理后台</h3>
      <p>从左侧菜单进入各管理页面，详细统计图表将在 P2 阶段补全。</p>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { reactive } from 'vue'

// P2 阶段接入真实统计 API
const stats = reactive({
  sessions: '-',
  docs: '-',
  models: '-',
  users: '-',
})
</script>

<style scoped lang="scss">
.dashboard {
  .stat-label {
    color: #909399;
    font-size: 13px;
  }
  .stat-value {
    font-size: 24px;
    font-weight: 600;
    color: #303133;
    margin-top: 8px;
  }
  .welcome-card {
    margin-top: 16px;
    h3 {
      margin: 0 0 8px;
    }
    p {
      color: #909399;
      margin: 0;
    }
  }
}
</style>
