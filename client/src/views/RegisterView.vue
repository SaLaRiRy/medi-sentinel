<!-- TICKET-029: 患者注册表单改用 element-plus，对外仍只 emit authenticated / error /
     login，业务逻辑不变。
     视觉重做（第一阶段）：由 PublicShell 提供全屏渐变背景，本页只负责居中白卡片。 -->
<script setup>
import { ref } from 'vue'

const props = defineProps({
  client: { type: Object, required: true },
})
const emit = defineEmits(['authenticated', 'error', 'login'])

const username = ref('')
const password = ref('')
const confirm = ref('')
const realName = ref('')
const phone = ref('')
const error = ref(null)
const submitting = ref(false)

async function submit() {
  error.value = null
  submitting.value = true
  try {
    const data = await props.client.register({
      username: username.value,
      password: password.value,
      confirm_password: confirm.value,
      real_name: realName.value,
      phone: phone.value,
    })
    emit('authenticated', data)
  } catch (failure) {
    error.value = failure.message ?? '注册失败'
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
        <h1 class="auth-card__title">创建患者账号</h1>
        <p class="auth-card__subtitle">注册后即可开始 AI 问诊与健康管理</p>
      </div>
    </div>

    <el-form class="auth-form" label-position="top" @submit.prevent="submit">
      <el-form-item label="用户名">
        <el-input v-model="username" data-username autocomplete="username" />
      </el-form-item>
      <el-form-item label="口令">
        <el-input
          v-model="password"
          data-password
          type="password"
          show-password
          autocomplete="new-password"
        />
      </el-form-item>
      <el-form-item label="确认口令">
        <el-input
          v-model="confirm"
          data-confirm
          type="password"
          show-password
          autocomplete="new-password"
        />
      </el-form-item>
      <el-form-item label="真实姓名">
        <el-input v-model="realName" data-real-name />
      </el-form-item>
      <el-form-item label="手机号">
        <el-input v-model="phone" data-phone />
      </el-form-item>
      <p v-if="error" data-error class="auth-form__error">{{ error }}</p>
      <el-button
        class="auth-form__submit"
        type="primary"
        native-type="submit"
        size="large"
        :loading="submitting"
      >
        注册
      </el-button>
      <div class="auth-form__footer">
        <span>已有账号？</span>
        <el-button link type="primary" data-login @click="emit('login')">返回登录</el-button>
      </div>
    </el-form>
  </el-card>
</template>

<style scoped>
.auth-card {
  width: 440px;
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
