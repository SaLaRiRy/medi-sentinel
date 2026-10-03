<script setup>
import { onMounted, reactive, ref } from 'vue'

const props = defineProps({
  client: { type: Object, required: true },
  role: { type: String, required: true },
})
const emit = defineEmits(['error', 'back'])

// 每个角色可编辑的字段不同（FUNCTIONAL_SPEC 4.3.1-4.3.3）。
const EDITABLE = {
  user: ['real_name', 'phone', 'allergy_history'],
  doctor: ['real_name', 'title', 'specialty', 'introduction', 'phone'],
  admin: ['nickname', 'phone', 'email'],
}
const LABELS = {
  real_name: '姓名',
  nickname: '昵称',
  phone: '手机号',
  email: '邮箱',
  allergy_history: '过敏史',
  title: '职称',
  specialty: '擅长领域',
  introduction: '个人简介',
}

const fields = EDITABLE[props.role] ?? []
const profile = ref({})
const form = reactive({})
const oldPassword = ref('')
const newPassword = ref('')
const message = ref(null)

function fill(row) {
  profile.value = row
  for (const name of fields) form[name] = row?.[name] ?? ''
}

onMounted(async () => {
  try {
    fill(await props.client.profileInfo())
  } catch (failure) {
    emit('error', failure)
  }
})

async function save() {
  const changes = {}
  for (const name of fields) {
    if (String(form[name] ?? '') !== String(profile.value?.[name] ?? '')) {
      changes[name] = form[name]
    }
  }
  if (Object.keys(changes).length === 0) return
  try {
    await props.client.profileUpdate(changes)
    fill(await props.client.profileInfo())
    message.value = '资料已保存'
  } catch (failure) {
    emit('error', failure)
  }
}

async function changePassword() {
  try {
    await props.client.changePassword({
      old_password: oldPassword.value,
      new_password: newPassword.value,
    })
    oldPassword.value = ''
    newPassword.value = ''
    message.value = '口令已修改'
  } catch (failure) {
    emit('error', failure)
  }
}
</script>

<template>
  <section class="profile">
    <h2 data-display-name>{{ profile.display_name }}</h2>
    <button type="button" data-back @click="emit('back')">返回</button>
    <form class="profile__form" @submit.prevent="save">
      <label v-for="name in fields" :key="name">
        {{ LABELS[name] }}
        <input v-model="form[name]" :data-field="name" />
      </label>
      <button type="button" data-save @click="save">保存资料</button>
    </form>
    <form class="profile__password" @submit.prevent="changePassword">
      <label>原口令 <input v-model="oldPassword" data-old-password type="password" /></label>
      <label>新口令 <input v-model="newPassword" data-new-password type="password" /></label>
      <button type="button" data-change-password @click="changePassword">修改口令</button>
    </form>
    <p v-if="message" data-message>{{ message }}</p>
  </section>
</template>
