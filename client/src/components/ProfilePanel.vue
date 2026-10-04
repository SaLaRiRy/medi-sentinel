<!--
  个人中心面板（TICKET-012）。视觉重做（第二阶段，图8）：左侧头像卡片
  （头像 + 上传提示 + 资料修改 / 密码修改 侧边菜单）+ 右侧表单卡片。

  所有 data-* 锚点保留，保存/改密逻辑不变（表单用 v-show 切换，两个分区始终在
  DOM 中，测试可直接驱动字段）。每个角色可编辑字段不同（FUNCTIONAL_SPEC 4.3.x）。
-->
<script setup>
import { computed, onMounted, reactive, ref } from 'vue'

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
const tab = ref('profile')

const initial = computed(() => (profile.value?.display_name ?? '用').slice(0, 1))

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
    <header class="page-head">
      <h1 class="page-head__title">个人中心</h1>
    </header>

    <div class="profile__layout">
      <el-card class="profile__aside" shadow="never">
        <div class="profile__avatar-block">
          <span class="profile__avatar">{{ initial }}</span>
          <p class="profile__avatar-hint">点击头像上传</p>
          <p data-display-name class="profile__name">{{ profile.display_name }}</p>
        </div>

        <nav class="profile__menu">
          <button
            type="button"
            class="profile__menu-item"
            :class="{ 'is-active': tab === 'profile' }"
            data-tab="profile"
            @click="tab = 'profile'"
          >
            资料修改
          </button>
          <button
            type="button"
            class="profile__menu-item"
            :class="{ 'is-active': tab === 'password' }"
            data-tab="password"
            @click="tab = 'password'"
          >
            密码修改
          </button>
        </nav>
      </el-card>

      <el-card class="profile__main" shadow="never">
        <template #header>
          <div class="card-head">
            <span class="card-title">{{ tab === 'profile' ? '个人资料' : '修改密码' }}</span>
            <el-button data-back size="small" @click="emit('back')">返回</el-button>
          </div>
        </template>

        <el-form
          v-show="tab === 'profile'"
          class="profile__form"
          label-width="88px"
          @submit.prevent="save"
        >
          <el-form-item v-for="name in fields" :key="name" :label="LABELS[name]">
            <el-input v-model="form[name]" :data-field="name" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" data-save @click="save">保存资料</el-button>
          </el-form-item>
        </el-form>

        <el-form
          v-show="tab === 'password'"
          class="profile__password"
          label-width="88px"
          @submit.prevent="changePassword"
        >
          <el-form-item label="原口令">
            <el-input v-model="oldPassword" data-old-password type="password" show-password />
          </el-form-item>
          <el-form-item label="新口令">
            <el-input v-model="newPassword" data-new-password type="password" show-password />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" data-change-password @click="changePassword">
              修改口令
            </el-button>
          </el-form-item>
        </el-form>

        <p v-if="message" data-message class="profile__message">{{ message }}</p>
      </el-card>
    </div>
  </section>
</template>

<style scoped>
.profile {
  display: flex;
  flex-direction: column;
  gap: var(--ms-space-5);
  padding: 0;
}

.profile__layout {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  gap: var(--ms-space-5);
  align-items: start;
}

.profile__aside,
.profile__main {
  border: 1px solid var(--ms-border);
  border-radius: var(--ms-radius-lg);
  box-shadow: var(--ms-shadow);
}

.profile__avatar-block {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--ms-space-2);
  padding-bottom: var(--ms-space-4);
}

.profile__avatar {
  display: grid;
  place-items: center;
  width: 88px;
  height: 88px;
  border-radius: 50%;
  background: var(--ms-gradient);
  color: #fff;
  font-size: 34px;
  font-weight: 700;
}

.profile__avatar-hint {
  color: var(--ms-text-muted);
  font-size: var(--ms-font-xs);
}

.profile__name {
  font-size: var(--ms-font-md);
  font-weight: 600;
}

.profile__menu {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-top: var(--ms-space-2);
}

.profile__menu-item {
  padding: 11px 14px;
  border: 0;
  border-left: 3px solid transparent;
  border-radius: var(--ms-radius-sm);
  background: transparent;
  color: var(--ms-text-secondary);
  font-size: var(--ms-font-base);
  text-align: left;
  cursor: pointer;
  transition: background 0.16s ease, color 0.16s ease;
}

.profile__menu-item:hover {
  background: var(--ms-bg);
}

.profile__menu-item.is-active {
  border-left-color: var(--ms-primary);
  background: rgba(99, 102, 241, 0.1);
  color: var(--ms-primary);
  font-weight: 600;
}

.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.card-title {
  font-size: var(--ms-font-md);
  font-weight: 600;
}

.profile__form,
.profile__password {
  max-width: 560px;
}

.profile__message {
  color: var(--el-color-success);
}
</style>
