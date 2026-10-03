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

async function submit() {
  error.value = null
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
  }
}
</script>

<template>
  <form class="auth-form" @submit.prevent="submit">
    <h1>登录</h1>
    <label>
      角色
      <select v-model="role" data-role>
        <option v-for="option in ROLE_OPTIONS" :key="option.value" :value="option.value">
          {{ option.label }}
        </option>
      </select>
    </label>
    <label>用户名 <input v-model="username" data-username autocomplete="username" /></label>
    <label>口令 <input v-model="password" data-password type="password" autocomplete="current-password" /></label>
    <p v-if="error" data-error class="auth-form__error">{{ error }}</p>
    <button type="submit">登录</button>
    <button type="button" data-register @click="emit('register')">患者注册</button>
  </form>
</template>
