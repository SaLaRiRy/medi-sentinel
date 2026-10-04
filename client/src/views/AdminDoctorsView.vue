<!--
  管理端医生管理（TICKET-020，FUNCTIONAL_SPEC 2.5 / SPEC.md 5.4）。

  分页查看医生、新建、编辑、启停与删除；科室下拉来自本票的科室主数据。删除医生
  由后端按 5.11 的顺序级联清理其工单与回复、预约、档案（未指派的工单保持不动）。
  状态展示走 `accountStatusLabel`，按钮文案取反（AC-F-11）。所有后端调用都经
  F-1 的 `client`。
-->
<script setup>
import { onMounted, ref } from 'vue'

import {
  accountStatusAction,
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
  if (form.value.department_id !== '') {
    base.department_id = Number(form.value.department_id)
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
    await load()
  } catch (failure) {
    emit('error', failure)
  }
}

async function toggleStatus(item) {
  try {
    await props.client.updateDoctorStatus(item.id, accountStatusToggleValue(item.status))
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
    <form data-doctor-form class="admin-doctors__form" @submit.prevent="submit">
      <input v-model="form.username" data-username placeholder="用户名" :disabled="editingId !== null" />
      <input v-model="form.password" data-password type="password" placeholder="口令" />
      <input
        v-model="form.confirm_password"
        data-confirm-password
        type="password"
        placeholder="确认口令"
      />
      <input v-model="form.real_name" data-real-name placeholder="姓名" />
      <select v-model="form.department_id" data-department>
        <option value="">未分配科室</option>
        <option
          v-for="department in departments"
          :key="department.id"
          data-department-option
          :value="department.id"
        >
          {{ department.name }}
        </option>
      </select>
      <input v-model="form.title" data-title placeholder="职称" />
      <input v-model="form.specialty" data-specialty placeholder="擅长领域" />
      <input v-model="form.introduction" data-introduction placeholder="个人简介" />
      <input v-model="form.phone" data-phone placeholder="手机号" />
      <button type="submit" data-submit>保存</button>
      <button v-if="editingId !== null" type="button" data-cancel @click="resetForm">
        取消
      </button>
    </form>

    <form data-search class="admin-doctors__search" @submit.prevent="search">
      <input v-model="keyword" data-keyword placeholder="按用户名或姓名搜索" />
      <button type="submit">搜索</button>
    </form>

    <p v-if="formError" data-form-error class="admin-doctors__error">{{ formError }}</p>
    <p v-if="loadError" data-error class="admin-doctors__error">{{ loadError }}</p>
    <p v-else-if="items.length === 0" data-empty class="admin-doctors__empty">暂无医生</p>

    <table v-else class="admin-doctors__table">
      <thead>
        <tr>
          <th>用户名</th>
          <th>姓名</th>
          <th>科室</th>
          <th>职称</th>
          <th>状态</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in items" :key="item.id" data-doctor-row>
          <td data-cell-username>{{ item.username }}</td>
          <td data-cell-name>{{ item.real_name }}</td>
          <td data-cell-department>{{ item.department_name ?? '-' }}</td>
          <td data-cell-title>{{ item.title ?? '-' }}</td>
          <td data-cell-status>{{ accountStatusLabel(item.status) }}</td>
          <td class="admin-doctors__actions">
            <button type="button" :data-edit="item.id" @click="startEdit(item)">编辑</button>
            <button type="button" :data-status-toggle="item.id" @click="toggleStatus(item)">
              {{ accountStatusAction(item.status) }}
            </button>
            <button type="button" :data-delete="item.id" @click="remove(item.id)">删除</button>
          </td>
        </tr>
      </tbody>
    </table>

    <footer class="admin-doctors__pager">
      <button type="button" data-prev :disabled="page <= 1" @click="goTo(page - 1)">
        上一页
      </button>
      <button
        type="button"
        data-next
        :disabled="page * PAGE_SIZE >= total"
        @click="goTo(page + 1)"
      >
        下一页
      </button>
    </footer>
  </section>
</template>
