<!--
  管理端患者管理（TICKET-020，FUNCTIONAL_SPEC 2.5 / SPEC.md 5.4）。
  TICKET-030 改用 element-plus：el-form/el-input/el-select 录入，el-table 列患者，
  el-tag 状态，el-button 操作，el-pagination 翻页。

  分页查看患者、新建、编辑、启停与删除。删除患者由后端按 5.11 的顺序级联清理
  会话与消息、工单与回复、预约、档案。表单校验在提交时命令式判断（FUNCTIONAL_SPEC
  5.19），后端 422 才是最终依据。状态展示走 `accountStatusLabel`，按钮文案取反
  （AC-F-11）。所有后端调用都经 F-1 的 `client`。
-->
<script setup>
import { onMounted, ref } from 'vue'

import {
  accountStatusAction,
  accountStatusColor,
  accountStatusLabel,
  accountStatusToggleValue,
} from '../account/status.js'

const props = defineProps({
  client: { type: Object, required: true },
})
const emit = defineEmits(['error'])

const PAGE_SIZE = 10
const items = ref([])
const total = ref(0)
const page = ref(1)
const keyword = ref('')
const loadError = ref(null)
const formError = ref(null)
const editingId = ref(null)
const loading = ref(false)

const emptyForm = () => ({
  username: '',
  password: '',
  confirm_password: '',
  real_name: '',
  gender: 1,
  age: '',
  phone: '',
  allergy_history: '',
})
const form = ref(emptyForm())

async function load() {
  loading.value = true
  try {
    const data = await props.client.adminUsers({
      page: page.value,
      page_size: PAGE_SIZE,
      keyword: keyword.value.trim() || undefined,
    })
    items.value = data.items ?? []
    total.value = data.total ?? 0
    loadError.value = null
  } catch (failure) {
    items.value = []
    total.value = 0
    loadError.value = '患者列表加载失败'
    emit('error', failure)
  } finally {
    loading.value = false
  }
}

function search() {
  page.value = 1
  load()
}

function goTo(target) {
  if (target < 1 || target === page.value) return
  if ((page.value - 1) * PAGE_SIZE >= total.value && target > page.value) return
  page.value = target
  load()
}

function resetForm() {
  form.value = emptyForm()
  editingId.value = null
  formError.value = null
}

function startEdit(item) {
  editingId.value = item.id
  formError.value = null
  form.value = {
    username: item.username,
    password: '',
    confirm_password: '',
    real_name: item.real_name ?? '',
    gender: item.gender ?? 1,
    age: item.age ?? '',
    phone: item.phone ?? '',
    allergy_history: item.allergy_history ?? '',
  }
}

function validate() {
  const username = form.value.username.trim()
  if (editingId.value === null && username.length < 3) {
    return '用户名必填且至少 3 个字符'
  }
  if (editingId.value === null && form.value.password.length < 6) {
    return '口令必填且至少 6 个字符'
  }
  if (form.value.password && form.value.password.length < 6) {
    return '口令至少 6 个字符'
  }
  if (form.value.password !== form.value.confirm_password) {
    return '两次口令输入不一致'
  }
  return null
}

function payload() {
  const base = { real_name: form.value.real_name.trim() || undefined }
  if (form.value.gender !== '') base.gender = Number(form.value.gender)
  if (form.value.age !== '') base.age = Number(form.value.age)
  if (form.value.phone.trim()) base.phone = form.value.phone.trim()
  if (form.value.allergy_history.trim()) {
    base.allergy_history = form.value.allergy_history.trim()
  }
  if (editingId.value === null) {
    return {
      username: form.value.username.trim(),
      password: form.value.password,
      confirm_password: form.value.confirm_password,
      ...base,
    }
  }
  if (form.value.password) {
    base.password = form.value.password
    base.confirm_password = form.value.confirm_password
  }
  return base
}

async function submit() {
  const problem = validate()
  if (problem) {
    formError.value = problem
    return
  }
  try {
    if (editingId.value === null) await props.client.createUser(payload())
    else await props.client.updateUser(editingId.value, payload())
    ElMessage.success(editingId.value === null ? '患者已创建' : '患者已更新')
    resetForm()
    await load()
  } catch (failure) {
    emit('error', failure)
  }
}

async function remove(userId) {
  try {
    await props.client.deleteUser(userId)
    if (items.value.length === 1 && page.value > 1) page.value -= 1
    ElMessage.success('患者已删除')
    await load()
  } catch (failure) {
    emit('error', failure)
  }
}

async function toggleStatus(item) {
  try {
    await props.client.updateUserStatus(item.id, accountStatusToggleValue(item.status))
    ElMessage.success('状态已更新')
    await load()
  } catch (failure) {
    emit('error', failure)
  }
}

onMounted(load)
</script>

<template>
  <section class="admin-users">
    <el-card class="admin-users__card admin-users__card--form" shadow="never">
      <template #header>
        <span class="card-title">{{ editingId === null ? '新建患者' : '编辑患者' }}</span>
      </template>

      <el-form
        data-user-form
        :model="form"
        label-width="88px"
        class="admin-users__form"
        @submit.prevent="submit"
      >
        <el-form-item label="用户名">
          <el-input
            v-model="form.username"
            data-username
            placeholder="用户名"
            :disabled="editingId !== null"
          />
        </el-form-item>
        <el-form-item label="口令">
          <el-input v-model="form.password" data-password type="password" placeholder="口令" />
        </el-form-item>
        <el-form-item label="确认口令">
          <el-input
            v-model="form.confirm_password"
            data-confirm-password
            type="password"
            placeholder="确认口令"
          />
        </el-form-item>
        <el-form-item label="姓名">
          <el-input v-model="form.real_name" data-real-name placeholder="姓名" />
        </el-form-item>
        <el-form-item label="性别">
          <el-select v-model="form.gender" data-gender :teleported="false">
            <el-option :value="1" label="男" />
            <el-option :value="2" label="女" />
          </el-select>
        </el-form-item>
        <el-form-item label="年龄">
          <el-input v-model="form.age" data-age type="number" placeholder="年龄" />
        </el-form-item>
        <el-form-item label="手机号">
          <el-input v-model="form.phone" data-phone placeholder="手机号" />
        </el-form-item>
        <el-form-item label="过敏史">
          <el-input v-model="form.allergy_history" data-allergy-history placeholder="过敏史" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" data-submit native-type="submit">保存</el-button>
          <el-button v-if="editingId !== null" data-cancel @click="resetForm">取消</el-button>
        </el-form-item>
      </el-form>

      <p v-if="formError" data-form-error class="admin-users__message admin-users__message--error">
        {{ formError }}
      </p>
    </el-card>

    <el-card class="admin-users__card" shadow="never">
      <template #header>
        <div class="card-head">
          <span class="card-title">患者列表</span>
          <el-tag size="small" type="info" effect="plain">{{ total }} 人</el-tag>
        </div>
      </template>

      <el-form data-search class="admin-users__search" @submit.prevent="search">
        <el-input v-model="keyword" data-keyword placeholder="按用户名或姓名搜索" clearable />
        <el-button native-type="submit">搜索</el-button>
      </el-form>

      <p v-if="loadError" data-error class="admin-users__message admin-users__message--error">
        {{ loadError }}
      </p>
      <el-table v-else v-loading="loading" :data="items" stripe class="admin-users__table">
        <template #empty>
          <span data-empty>暂无患者</span>
        </template>
        <el-table-column prop="username" label="用户名" min-width="120">
          <template #default="{ row }">
            <span data-cell-username>{{ row.username }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="real_name" label="姓名" min-width="100">
          <template #default="{ row }">
            <span data-cell-name>{{ row.real_name ?? '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="性别" min-width="80">
          <template #default="{ row }">
            <span data-cell-gender>{{ row.gender === 2 ? '女' : '男' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="age" label="年龄" min-width="80">
          <template #default="{ row }">
            <span data-cell-age>{{ row.age ?? '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" min-width="90">
          <template #default="{ row }">
            <el-tag data-cell-status :type="accountStatusColor(row.status)" effect="light">
              {{ accountStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="220">
          <template #default="{ row }">
            <el-button size="small" :data-edit="row.id" @click="startEdit(row)">编辑</el-button>
            <el-button size="small" :data-status-toggle="row.id" @click="toggleStatus(row)">
              {{ accountStatusAction(row.status) }}
            </el-button>
            <el-button size="small" type="danger" plain :data-delete="row.id" @click="remove(row.id)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="admin-users__pager">
        <el-pagination
          data-pagination
          background
          layout="prev, pager, next"
          :current-page="page"
          :page-size="PAGE_SIZE"
          :total="total"
          @current-change="goTo"
        />
      </div>
    </el-card>
  </section>
</template>

<style scoped>
.admin-users {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 0;
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

.admin-users__form {
  max-width: 560px;
}

/* Keep the non-teleported el-select dropdown from being clipped by el-card. */
.admin-users__card--form,
.admin-users__card--form :deep(.el-card__body) {
  overflow: visible;
}

.admin-users__search {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
}

.admin-users__search :deep(.el-input) {
  max-width: 320px;
}

.admin-users__message {
  margin: 8px 0;
  color: var(--el-text-color-secondary);
}

.admin-users__message--error {
  color: var(--el-color-danger);
}

.admin-users__pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}
</style>
