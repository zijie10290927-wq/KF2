<template>
  <div class="fallback-config">
    <h2>兜底话术配置</h2>
    <el-card v-loading="loading">
      <el-form :model="form" label-width="120px">
        <el-form-item label="兜底话术">
          <el-input v-model="form.fallback_message" type="textarea" :rows="4" />
        </el-form-item>
        <el-form-item label="显示转人工">
          <el-switch v-model="form.show_transfer_button" />
        </el-form-item>
        <el-form-item label="显示电话">
          <el-switch v-model="form.show_phone" />
        </el-form-item>
        <el-form-item label="客服电话">
          <el-input v-model="form.phone_number" placeholder="400-xxx-xxxx" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="saving" @click="onSave">保存</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getFallbackConfig, updateFallbackConfig } from '@/api/model'
import type { FallbackConfig } from '@/types'

const loading = ref(false)
const saving = ref(false)
const form = reactive<FallbackConfig>({
  fallback_message: '',
  show_transfer_button: true,
  show_phone: true,
  phone_number: '',
})

async function load() {
  loading.value = true
  try {
    const res = await getFallbackConfig()
    Object.assign(form, res.data)
  } finally {
    loading.value = false
  }
}

async function onSave() {
  saving.value = true
  try {
    await updateFallbackConfig({ ...form })
    ElMessage.success('保存成功')
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>
