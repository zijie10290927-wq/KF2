<template>
  <div class="chat-logs">
    <h2>对话记录</h2>
    <el-card>
      <el-form inline>
        <el-form-item label="会话ID">
          <el-input v-model="filter.session_id" clearable placeholder="session_id" style="width: 280px" />
        </el-form-item>
        <el-form-item label="意图">
          <el-input v-model="filter.intent" clearable style="width: 140px" />
        </el-form-item>
        <el-button type="primary" @click="onSearch">查询</el-button>
      </el-form>
      <el-table :data="logs" v-loading="loading" stripe>
        <el-table-column prop="message_id" label="消息ID" min-width="180" show-overflow-tooltip />
        <el-table-column prop="session_id" label="会话ID" min-width="180" show-overflow-tooltip />
        <el-table-column prop="role" label="角色" width="80" />
        <el-table-column prop="intent" label="意图" width="100" />
        <el-table-column prop="model_used" label="模型" width="120" />
        <el-table-column label="内容" min-width="280">
          <template #default="{ row }">
            <span class="content-snippet">{{ row.content.slice(0, 80) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="时间" width="180">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-model:current-page="filter.page"
        v-model:page-size="filter.page_size"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="loadLogs"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import request from '@/api/request'
import { formatDateTime } from '@/utils/format'
import type { ApiResponse, ChatMessage, PageResponse } from '@/types'

const loading = ref(false)
const logs = ref<ChatMessage[]>([])
const total = ref(0)
const filter = reactive({
  session_id: '',
  intent: '',
  page: 1,
  page_size: 20,
})

async function loadLogs() {
  loading.value = true
  try {
    const res = await request.get<unknown, ApiResponse<PageResponse<ChatMessage>>>(
      '/admin/chat/logs',
      { params: filter }
    )
    logs.value = res.data.list
    total.value = res.data.total
  } finally {
    loading.value = false
  }
}

function onSearch() {
  filter.page = 1
  loadLogs()
}

onMounted(loadLogs)
</script>

<style scoped lang="scss">
.chat-logs {
  .content-snippet {
    color: #606266;
  }
  .el-pagination {
    margin-top: 16px;
    justify-content: flex-end;
  }
}
</style>
