<template>
  <div class="login-page">
    <div class="login-card">
      <h2>AI 智能客服</h2>
      <p class="subtitle">请登录后开始对话</p>
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        @submit.prevent="onSubmit"
      >
        <el-form-item label="用户名" prop="username">
          <el-input
            v-model="form.username"
            placeholder="请输入用户名"
            :prefix-icon="User"
            size="large"
          />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="请输入密码"
            :prefix-icon="Lock"
            size="large"
            show-password
            @keyup.enter="onSubmit"
          />
        </el-form-item>
        <el-button
          type="primary"
          size="large"
          class="submit"
          :loading="loading"
          @click="onSubmit"
        >
          登录
        </el-button>
        <div class="register">
          <span>还没有账号？</span>
          <el-link type="primary" @click="onRegister">注册</el-link>
        </div>
      </el-form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, type FormInstance } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { register } from '@/api/auth'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const formRef = ref<FormInstance>()
const loading = ref(false)
const form = reactive({
  username: '',
  password: '',
})
const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少 6 位', trigger: 'blur' },
  ],
}

async function onSubmit() {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    loading.value = true
    try {
      await authStore.login(form.username, form.password)
      ElMessage.success('登录成功')
      const redirect = (route.query.redirect as string) || '/chat'
      router.push(redirect)
    } catch {
      // 拦截器已弹出错误
    } finally {
      loading.value = false
    }
  })
}

async function onRegister() {
  if (!form.username || !form.password) {
    ElMessage.warning('请填写用户名和密码后再注册')
    return
  }
  try {
    await register(form.username, form.password)
    ElMessage.success('注册成功，请登录')
  } catch {
    /* 拦截器处理错误 */
  }
}
</script>

<style scoped lang="scss">
.login-page {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}
.login-card {
  width: 380px;
  background: #fff;
  border-radius: 12px;
  padding: 32px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
  h2 {
    text-align: center;
    color: #303133;
    margin: 0 0 8px;
  }
  .subtitle {
    text-align: center;
    color: #909399;
    margin: 0 0 24px;
    font-size: 14px;
  }
  .submit {
    width: 100%;
    margin-top: 8px;
  }
  .register {
    text-align: center;
    margin-top: 16px;
    font-size: 14px;
    color: #909399;
  }
}
</style>
