<!--
  管理端医生管理（TICKET-020，FUNCTIONAL_SPEC 2.5 / SPEC.md 5.4）。
  TICKET-030 改用 element-plus：el-form/el-input/el-select 录入，el-table 列医生，
  el-tag 状态，el-button 操作，el-pagination 翻页。

  分页查看医生、新建、编辑、启停与删除；科室下拉来自本票的科室主数据。删除医生
  由后端按 5.11 的顺序级联清理其工单与回复、预约、档案（未指派的工单保持不动）。
  状态展示走 `accountStatusLabel`，按钮文案取反（AC-F-11）。所有后端调用都经
  F-1 的 `client`。
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
const departments = ref([])
const loadError = ref(null)
const formError = ref(null)
const editingId = ref(null)
const loading = ref(false)

const emptyForm = () => ({
  username: '',
  password: '',
  confirm_password: '',
  real_name: '',
  department_id: '',
  title: '',
  specialty: '',
  introduction: '',
  phone: '',
})
const form = ref(emptyForm())

async function load() {
  loading.value = true
  try {
    const data = await props.client.adminDoctors({
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
    loadError.value = '医生列表加载失败'
    emit('error', failure)
  } finally {
    loading.value = false
  }
}

async function loadDepartments() {
  try {
    const data = await props.client.adminDepartments({ page: 1, page_size: 100 })
    departments.value = data.items ?? []
  } catch (failure) {
    departments.value = []
    emit('error', failure)
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
    department_id: item.department_id ?? '',
    title: item.title ?? '',
    specialty: item.specialty ?? '',
    introduction: item.introduction ?? '',
    phone: item.phone ?? '',
  }
}

function validate() {
  if (editingId.value === null && form.value.username.trim().length < 3) {
    return '用户名必填且至少 3 个字符'
  }
  if (!form.value.real_name.trim()) return '姓名必填'
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
  const base = { real_name: form.value.real_name.trim() }
  // el-select may clear to '' or undefined; only a real id becomes a number
  // (otherwise Number(undefined) would send NaN).
  const departmentId = form.value.department_id
  if (departmentId !== '' && departmentId !== null && departmentId !== undefined) {
    base.department_id = Number(departmentId)
  }
  if (form.value.title.trim()) base.title = form.value.title.trim()
  if (form.value.specialty.trim()) base.specialty = form.value.specialty.trim()
  if (form.value.introduction.trim()) {
    base.introduction = form.value.introduction.trim()
  }
  if (form.value.phone.trim()) base.phone = form.value.phone.trim()
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
    if (editingId.value === null) await props.client.createDoctor(payload())
    else await props.client.updateDoctor(editingId.value, payload())
    ElMessage.success(editingId.value === null ? '医生已创建' : '医生已更新')
    resetForm()
    await load()
  } catch (failure) {
    emit('error', failure)
  }
}

async function remove(doctorId) {
  try {
    await props.client.deleteDoctor(doctorId)
    if (items.value.length === 1 && page.value > 1) page.value -= 1
    ElMessage.success('医生已删除')
    await load()
  } catch (failure) {
    emit('error', failure)
  }
}

async function toggleStatus(item) {
  try {
    await props.client.updateDoctorStatus(item.id, accountStatusToggleValue(item.status))
    ElMessage.success('状态已更新')
    await load()
  } catch (failure) {
    emit('error', failure)
  }
}

onMounted(() => {
  loadDepartments()
  load()
})
</script>

<template>
  <section class="admin-doctors">
    <header class="page-head">
      <h1 class="page-head__title">医生管理</h1>
    </header>

    <el-card class="admin-doctors__card admin-doctors__card--form" shadow="never">
      <template #header>
        <span class="card-title">{{ editingId === null ? '新建医生' : '编辑医生' }}</span>
      </template>

      <el-form
        data-doctor-form
        :model="form"
        label-width="88px"
        class="admin-doctors__form"
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
        <el-form-item label="科室">
          <el-select
            v-model="form.department_id"
            data-department
            placeholder="未分配科室"
            clearable
            value-on-clear=""
            :teleported="false"
          >
            <el-option
              v-for="department in departments"
              :key="department.id"
              data-department-option
              :value="department.id"
              :label="department.name"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="职称">
          <el-input v-model="form.title" data-title placeholder="职称" />
        </el-form-item>
        <el-form-item label="擅长领域">
          <el-input v-model="form.specialty" data-specialty placeholder="擅长领域" />
        </el-form-item>
        <el-form-item label="个人简介">
          <el-input v-model="form.introduction" data-introduction placeholder="个人简介" />
        </el-form-item>
        <el-form-item label="手机号">
          <el-input v-model="form.phone" data-phone placeholder="手机号" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" data-submit native-type="submit">保存</el-button>
          <el-button v-if="editingId !== null" data-cancel @click="resetForm">取消</el-button>
        </el-form-item>
      </el-form>

      <p v-if="formError" data-form-error class="admin-doctors__message admin-doctors__message--error">
        {{ formError }}
      </p>
    </el-card>

    <el-card class="admin-doctors__card" shadow="never">
      <template #header>
        <div class="card-head">
          <span class="card-title">医生列表</span>
          <el-tag size="small" type="info" effect="plain">{{ total }} 人</el-tag>
        </div>
      </template>

      <el-form data-search class="admin-doctors__search" @submit.prevent="search">
        <el-input v-model="keyword" data-keyword placeholder="按用户名或姓名搜索" clearable />
        <el-button native-type="submit">搜索</el-button>
      </el-form>

      <p v-if="loadError" data-error class="admin-doctors__message admin-doctors__message--error">
        {{ loadError }}
      </p>
      <el-table v-else v-loading="loading" :data="items" stripe class="admin-doctors__table">
        <template #empty>
          <span data-empty>暂无医生</span>
        </template>
        <el-table-column prop="username" label="用户名" min-width="120">
          <template #default="{ row }">
            <span data-cell-username>{{ row.username }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="real_name" label="姓名" min-width="100">
          <template #default="{ row }">
            <span data-cell-name>{{ row.real_name }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="department_name" label="科室" min-width="120">
          <template #default="{ row }">
            <span data-cell-department>{{ row.department_name ?? '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="title" label="职称" min-width="120">
          <template #default="{ row }">
            <span data-cell-title>{{ row.title ?? '-' }}</span>
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

      <div class="admin-doctors__pager">
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
.admin-doctors {
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

.admin-doctors__form {
  max-width: 560px;
}

/* Keep the non-teleported el-select dropdown from being clipped by el-card. */
.admin-doctors__card--form,
.admin-doctors__card--form :deep(.el-card__body) {
  overflow: visible;
}

.admin-doctors__search {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
}

.admin-doctors__search :deep(.el-input) {
  max-width: 320px;
}

.admin-doctors__message {
  margin: 8px 0;
  color: var(--el-text-color-secondary);
}

.admin-doctors__message--error {
  color: var(--el-color-danger);
}

.admin-doctors__pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}
</style>
