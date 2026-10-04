<!-- TICKET-029: 登录表单改用 element-plus（el-form/el-select/el-input/el-button），
     对外仍只 emit authenticated / error / register，业务逻辑不变。
     视觉重做（第一阶段）：由 PublicShell 提供全屏渐变背景，本页只负责居中白卡片。 -->
<script setup>
import { ref } from 'vue'

const props = defineProps({
  client: { type: Object, required: true },
})
const emit = defineEmits(['authenticated', 'error', 'register'])

const ROLE_OPTIONS = [
  { value: 'user', label: '患者' },
  { value: 'doctor', label: '医生' },
  { value: 'admin', label: '管理员' },
]

const username = ref('')
const password = ref('')
const role = ref('user')
const error = ref(null)
const submitting = ref(false)

async function submit() {
  error.value = null
  submitting.value = true
  try {
    const data = await props.client.login({
      username: username.value,
      password: password.value,
      role: role.value,
    })
    emit('authenticated', data)
  } catch (failure) {
    error.value = failure.message ?? '登录失败'
    emit('error', failure)
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <el-card class="auth-card" shadow="never">
    <div class="auth-card__brand">
      <span class="auth-card__logo">＋</span>
      <div>
        <h1 class="auth-card__title">欢迎回来</h1>
        <p class="auth-card__subtitle">登录后即可使用 AI 问诊与健康服务</p>
      </div>
    </div>

    <el-form class="auth-form" label-position="top" @submit.prevent="submit">
      <el-form-item label="角色">
        <el-select v-model="role" data-role :teleported="false">
          <el-option
            v-for="option in ROLE_OPTIONS"
            :key="option.value"
            :value="option.value"
            :label="option.label"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="用户名">
        <el-input v-model="username" data-username autocomplete="username" />
      </el-form-item>
      <el-form-item label="口令">
        <el-input
          v-model="password"
          data-password
          type="password"
          show-password
          autocomplete="current-password"
        />
      </el-form-item>
      <p v-if="error" data-error class="auth-form__error">{{ error }}</p>
      <el-button
        class="auth-form__submit"
        type="primary"
        native-type="submit"
        size="large"
        :loading="submitting"
      >
        登录
      </el-button>
      <div class="auth-form__footer">
        <span>还没有账号？</span>
        <el-button link type="primary" data-register @click="emit('register')">
          患者注册 →
        </el-button>
      </div>
    </el-form>
  </el-card>
</template>

<style scoped>
.auth-card {
  width: 420px;
  max-width: 100%;
  border: 1px solid rgba(255, 255, 255, 0.7);
  border-radius: var(--ms-radius-lg);
  box-shadow: var(--ms-shadow-lg);
}

.auth-card :deep(.el-card__body) {
  padding: 36px 32px 28px;
}

.auth-card__brand {
  display: flex;
  align-items: center;
  gap: var(--ms-space-3);
  margin-bottom: var(--ms-space-6);
}

.auth-card__logo {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  border-radius: 12px;
  background: var(--ms-gradient);
  color: #fff;
  font-size: 20px;
  font-weight: 600;
}

.auth-card__title {
  margin: 0;
  font-size: var(--ms-font-xl);
  font-weight: 700;
}

.auth-card__subtitle {
  margin: 2px 0 0;
  color: var(--ms-text-muted);
  font-size: var(--ms-font-sm);
}

.auth-form__submit {
  width: 100%;
}

.auth-form__error {
  margin: 0 0 12px;
  color: var(--el-color-danger);
  font-size: var(--ms-font-sm);
}

.auth-form__footer {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  margin-top: var(--ms-space-3);
  color: var(--ms-text-muted);
  font-size: var(--ms-font-sm);
}
</style>
