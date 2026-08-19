<template>
  <div class="knowledge-manage">
    <div class="header">
      <h2>知识库管理</h2>
      <el-upload
        :show-file-list="false"
        :before-upload="onUpload"
        :http-request="() => {}"
        accept=".pdf,.docx,.doc,.txt,.md"
      >
        <el-button type="primary" :icon="Upload">上传文档</el-button>
      </el-upload>
    </div>

    <el-card>
      <el-form inline>
        <el-form-item label="状态">
          <el-select v-model="filter.status" clearable placeholder="全部" style="width: 140px">
            <el-option label="上传中" value="uploading" />
            <el-option label="处理中" value="processing" />
            <el-option label="已索引" value="indexed" />
            <el-option label="失败" value="failed" />
          </el-select>
        </el-form-item>
        <el-form-item label="关键词">
          <el-input v-model="filter.keyword" clearable placeholder="文件名" style="width: 200px" />
        </el-form-item>
        <el-button type="primary" @click="loadDocs">查询</el-button>
        <el-button @click="resetFilter">重置</el-button>
      </el-form>

      <el-table :data="docs" v-loading="loading" stripe>
        <el-table-column prop="filename" label="文件名" min-width="180" />
        <el-table-column prop="file_type" label="类型" width="80" />
        <el-table-column label="大小" width="100">
          <template #default="{ row }">{{ formatFileSize(row.file_size) }}</template>
        </el-table-column>
        <el-table-column prop="category" label="分类" width="100" />
        <el-table-column prop="chunk_count" label="分块" width="80" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="docStatusTagType(row.status)">
              {{ docStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="上传时间" width="180">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="onReindex(row.doc_id)">重建索引</el-button>
            <el-popconfirm title="确认删除？" @confirm="onDelete(row.doc_id)">
              <template #reference>
                <el-button size="small" type="danger">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="filter.page"
        v-model:page-size="filter.page_size"
        :total="total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next"
        @size-change="loadDocs"
        @current-change="loadDocs"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Upload } from '@element-plus/icons-vue'
import { listDocs, uploadDoc, deleteDoc, reindexDoc } from '@/api/knowledge'
import { formatDateTime, formatFileSize, docStatusTagType, docStatusLabel } from '@/utils/format'
import type { KnowledgeDoc } from '@/types'

const docs = ref<KnowledgeDoc[]>([])
const total = ref(0)
const loading = ref(false)
const filter = reactive({
  page: 1,
  page_size: 10,
  status: '',
  keyword: '',
  category: '',
})

async function loadDocs() {
  loading.value = true
  try {
    const res = await listDocs(filter)
    docs.value = res.data.list
    total.value = res.data.total
  } catch {
    /* 拦截器处理 */
  } finally {
    loading.value = false
  }
}

async function onUpload(file: File) {
  try {
    await uploadDoc(file, filter.category)
    ElMessage.success('上传成功，正在后台处理')
    await loadDocs()
    // 3 秒后刷新一次（处理中 → 已索引）
    setTimeout(loadDocs, 3000)
  } catch {
    /* 拦截器处理 */
  }
  return false // 阻止默认上传
}

async function onDelete(docId: string) {
  try {
    await deleteDoc(docId)
    ElMessage.success('删除成功')
    await loadDocs()
  } catch {
    /* ignore */
  }
}

async function onReindex(docId: string) {
  try {
    await reindexDoc(docId)
    ElMessage.success('已触发重建索引')
    setTimeout(loadDocs, 3000)
  } catch {
    /* ignore */
  }
}

function resetFilter() {
  filter.status = ''
  filter.keyword = ''
  filter.category = ''
  filter.page = 1
  loadDocs()
}

onMounted(loadDocs)
</script>

<style scoped lang="scss">
.knowledge-manage {
  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
    h2 {
      margin: 0;
    }
  }
  .el-pagination {
    margin-top: 16px;
    justify-content: flex-end;
  }
}
</style>
