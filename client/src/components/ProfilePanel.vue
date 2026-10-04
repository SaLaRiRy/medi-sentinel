<!-- TICKET-029: 个人中心面板改用 element-plus（el-form/el-input/el-button），
     所有 data-* 锚点保留，保存/改密逻辑不变。 -->
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
    <el-card class="profile__card" shadow="never">
      <template #header>
        <div class="card-head">
          <span data-display-name class="card-title">{{ profile.display_name }}</span>
          <el-button data-back size="small" @click="emit('back')">返回</el-button>
        </div>
      </template>

      <el-form class="profile__form" label-width="88px" @submit.prevent="save">
        <el-form-item v-for="name in fields" :key="name" :label="LABELS[name]">
          <el-input v-model="form[name]" :data-field="name" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" data-save @click="save">保存资料</el-button>
        </el-form-item>
      </el-form>

      <el-divider />

      <el-form class="profile__password" label-width="88px" @submit.prevent="changePassword">
        <el-form-item label="原口令">
          <el-input v-model="oldPassword" data-old-password type="password" show-password />
        </el-form-item>
        <el-form-item label="新口令">
          <el-input v-model="newPassword" data-new-password type="password" show-password />
        </el-form-item>
        <el-form-item>
          <el-button data-change-password @click="changePassword">修改口令</el-button>
        </el-form-item>
      </el-form>

      <p v-if="message" data-message class="profile__message">{{ message }}</p>
    </el-card>
  </section>
</template>

<style scoped>
.profile {
  padding: 16px;
}

.profile__card {
  max-width: 640px;
}

.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
}

.profile__message {
  color: var(--el-color-success);
}
</style>
