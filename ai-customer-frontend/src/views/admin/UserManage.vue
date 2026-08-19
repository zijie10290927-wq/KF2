<template>
  <div class="user-manage">
    <h2>用户管理</h2>
    <el-card>
      <el-form inline>
        <el-form-item label="关键词">
          <el-input v-model="filter.keyword" clearable placeholder="用户名" style="width: 200px" />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="filter.role" clearable style="width: 140px">
            <el-option label="管理员" value="admin" />
            <el-option label="普通用户" value="user" />
          </el-select>
        </el-form-item>
        <el-button type="primary" @click="onSearch">查询</el-button>
      </el-form>
      <el-table :data="users" v-loading="loading" stripe>
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="username" label="用户名" min-width="160" />
        <el-table-column label="角色" width="120">
          <template #default="{ row }">
            <el-tag :type="row.role === 'admin' ? 'success' : 'info'">
              {{ row.role === 'admin' ? '管理员' : '用户' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'danger'">
              {{ row.status === 1 ? '正常' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="180">
          <template #default="{ row }">{{ row.created_at }}</template>
        </el-table-column>
        <el-table-column label="操作" width="260" fixed="right">
          <template #default="{ row }">
            <el-button
              size="small"
              :type="row.status === 1 ? 'warning' : 'success'"
              @click="onToggleStatus(row)"
            >
              {{ row.status === 1 ? '禁用' : '启用' }}
            </el-button>
            <el-button size="small" @click="onToggleRole(row)">
              {{ row.role === 'admin' ? '降为用户' : '升为管理员' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-model:current-page="filter.page"
        v-model:page-size="filter.page_size"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="loadUsers"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import request from '@/api/request'
import type { ApiResponse, PageResponse, UserInfo } from '@/types'

const loading = ref(false)
const users = ref<UserInfo[]>([])
const total = ref(0)
const filter = reactive({ keyword: '', role: '', page: 1, page_size: 20 })

async function loadUsers() {
  loading.value = true
  try {
    const res = await request.get<unknown, ApiResponse<PageResponse<UserInfo>>>(
      '/admin/users',
      { params: filter }
    )
    users.value = res.data.list
    total.value = res.data.total
  } finally {
    loading.value = false
  }
}

function onSearch() {
  filter.page = 1
  loadUsers()
}

async function onToggleStatus(row: UserInfo) {
  await request.patch(`/admin/users/${row.id}/status`, { status: row.status === 1 ? 0 : 1 })
  ElMessage.success('状态已更新')
  await loadUsers()
}

async function onToggleRole(row: UserInfo) {
  await request.patch(`/admin/users/${row.id}/role`, {
    role: row.role === 'admin' ? 'user' : 'admin',
  })
  ElMessage.success('角色已更新')
  await loadUsers()
}

onMounted(loadUsers)
</script>

<style scoped lang="scss">
.user-manage {
  .el-pagination {
    margin-top: 16px;
    justify-content: flex-end;
  }
}
</style>
