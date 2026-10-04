<!-- TICKET-029: 患者注册表单改用 element-plus，对外仍只 emit authenticated / error /
     login，业务逻辑不变。 -->
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
  <el-card class="auth-card" shadow="always">
    <h1 class="auth-card__title">患者注册</h1>
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
      <el-button type="primary" native-type="submit" :loading="submitting">注册</el-button>
      <el-button data-login @click="emit('login')">返回登录</el-button>
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
