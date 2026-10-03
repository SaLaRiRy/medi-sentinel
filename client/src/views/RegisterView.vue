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

async function submit() {
  error.value = null
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
  }
}
</script>

<template>
  <form class="auth-form" @submit.prevent="submit">
    <h1>患者注册</h1>
    <label>用户名 <input v-model="username" data-username autocomplete="username" /></label>
    <label>口令 <input v-model="password" data-password type="password" autocomplete="new-password" /></label>
    <label>确认口令 <input v-model="confirm" data-confirm type="password" autocomplete="new-password" /></label>
    <label>真实姓名 <input v-model="realName" data-real-name /></label>
    <label>手机号 <input v-model="phone" data-phone /></label>
    <p v-if="error" data-error class="auth-form__error">{{ error }}</p>
    <button type="submit">注册</button>
    <button type="button" data-login @click="emit('login')">返回登录</button>
  </form>
</template>
