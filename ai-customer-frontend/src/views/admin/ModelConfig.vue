<template>
  <div class="model-config">
    <div class="header">
      <h2>模型配置</h2>
      <el-button type="primary" :icon="Plus" @click="onCreate">新增模型</el-button>
    </div>
    <el-card>
      <el-table :data="models" v-loading="loading" stripe>
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="model_name" label="模型名" min-width="160" />
        <el-table-column prop="api_base" label="API Base" min-width="220" show-overflow-tooltip />
        <el-table-column prop="temperature" label="温度" width="80" />
        <el-table-column prop="max_tokens" label="MaxTokens" width="110" />
        <el-table-column label="启用" width="100">
          <template #default="{ row }">
            <el-switch
              :model-value="row.enabled"
              @change="(v: any) => onToggle(row.id, v)"
            />
          </template>
        </el-table-column>
        <el-table-column label="默认" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.is_default" type="success">默认</el-tag>
            <el-button v-else size="small" text @click="onSetDefault(row.id)">设为默认</el-button>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="onEdit(row)">编辑</el-button>
            <el-popconfirm title="确认删除？" @confirm="onDelete(row.id)">
              <template #reference>
                <el-button size="small" type="danger">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑模型' : '新增模型'" width="520px">
      <el-form :model="form" label-width="120px">
        <el-form-item label="模型名" required>
          <el-input v-model="form.model_name" :disabled="isEdit" placeholder="如 gpt-4o-mini" />
        </el-form-item>
        <el-form-item label="API Base" required>
          <el-input v-model="form.api_base" placeholder="https://api.openai.com/v1" />
        </el-form-item>
        <el-form-item label="API Key" :required="!isEdit">
          <el-input
            v-model="form.api_key"
            type="password"
            show-password
            :placeholder="isEdit ? '留空则不修改' : 'sk-xxx'"
          />
        </el-form-item>
        <el-form-item label="Temperature">
          <el-input-number v-model="form.temperature" :min="0" :max="1" :step="0.1" />
        </el-form-item>
        <el-form-item label="Max Tokens">
          <el-input-number v-model="form.max_tokens" :min="1" :max="32768" :step="256" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.enabled" />
        </el-form-item>
        <el-form-item label="设为默认">
          <el-switch v-model="form.is_default" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="onSubmit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import {
  listModels,
  createModel,
  updateModel,
  deleteModel,
  toggleModel,
  setDefaultModel,
} from '@/api/model'
import type { ModelConfig } from '@/types'

const models = ref<ModelConfig[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const submitting = ref(false)
const isEdit = ref(false)
const editingId = ref<number>(0)

const form = reactive({
  model_name: '',
  api_base: '',
  api_key: '',
  temperature: 0.7,
  max_tokens: 2048,
  enabled: true,
  is_default: false,
})

async function loadModels() {
  loading.value = true
  try {
    const res = await listModels(false)
    models.value = res.data
  } finally {
    loading.value = false
  }
}

function resetForm() {
  form.model_name = ''
  form.api_base = ''
  form.api_key = ''
  form.temperature = 0.7
  form.max_tokens = 2048
  form.enabled = true
  form.is_default = false
}

function onCreate() {
  isEdit.value = false
  resetForm()
  dialogVisible.value = true
}

function onEdit(row: ModelConfig) {
  isEdit.value = true
  editingId.value = row.id
  form.model_name = row.model_name
  form.api_base = row.api_base
  form.api_key = ''
  form.temperature = Number(row.temperature)
  form.max_tokens = row.max_tokens
  form.enabled = row.enabled
  form.is_default = row.is_default
  dialogVisible.value = true
}

async function onSubmit() {
  submitting.value = true
  try {
    if (isEdit.value) {
      // B6 修复：编辑时空 api_key 不提交（「留空则不修改」），防止密钥被意外清空
      const payload = { ...form }
      if (!payload.api_key) delete (payload as Record<string, unknown>).api_key
      await updateModel(editingId.value, payload)
      ElMessage.success('更新成功')
    } else {
      await createModel({ ...form })
      ElMessage.success('新增成功')
    }
    dialogVisible.value = false
    await loadModels()
  } finally {
    submitting.value = false
  }
}

async function onDelete(id: number) {
  await deleteModel(id)
  ElMessage.success('删除成功')
  await loadModels()
}

async function onToggle(id: number, enabled: boolean) {
  await toggleModel(id, enabled)
  await loadModels()
}

async function onSetDefault(id: number) {
  await setDefaultModel(id)
  ElMessage.success('已设为默认')
  await loadModels()
}

onMounted(loadModels)
</script>

<style scoped lang="scss">
.model-config {
  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
    h2 {
      margin: 0;
    }
  }
}
</style>
