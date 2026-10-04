<!-- TICKET-029: 登录表单改用 element-plus（el-form/el-select/el-input/el-button），
     对外仍只 emit authenticated / error / register，业务逻辑不变。 -->
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
  <el-card class="auth-card" shadow="always">
    <h1 class="auth-card__title">登录</h1>
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
      <el-button type="primary" native-type="submit" :loading="submitting">登录</el-button>
      <el-button data-register @click="emit('register')">患者注册</el-button>
    </el-form>
  </el-card>
</template>

<style scoped>
.auth-card {
  width: 360px;
  margin: 48px auto;
}

.auth-card__title {
  margin: 0 0 16px;
  text-align: center;
  font-size: 22px;
}

.auth-form__error {
  margin: 0 0 12px;
  color: var(--el-color-danger);
}
</style>
