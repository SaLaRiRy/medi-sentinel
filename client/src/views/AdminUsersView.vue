<!--
  管理端患者管理（TICKET-020，FUNCTIONAL_SPEC 2.5 / SPEC.md 5.4）。

  分页查看患者、新建、编辑、启停与删除。删除患者由后端按 5.11 的顺序级联清理
  会话与消息、工单与回复、预约、档案。表单校验在提交时命令式判断（FUNCTIONAL_SPEC
  5.19），后端 422 才是最终依据。状态展示走 `accountStatusLabel`，按钮文案取反
  （AC-F-11）。所有后端调用都经 F-1 的 `client`。
-->
<script setup>
import { onMounted, ref } from 'vue'

import { accountStatusAction, accountStatusLabel, accountStatusToggleValue } from '../account/status.js'

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
    await load()
  } catch (failure) {
    emit('error', failure)
  }
}

async function toggleStatus(item) {
  try {
    await props.client.updateUserStatus(item.id, accountStatusToggleValue(item.status))
    await load()
  } catch (failure) {
    emit('error', failure)
  }
}

onMounted(load)
</script>

<template>
  <section class="admin-users">
    <form data-user-form class="admin-users__form" @submit.prevent="submit">
      <input v-model="form.username" data-username placeholder="用户名" :disabled="editingId !== null" />
      <input v-model="form.password" data-password type="password" placeholder="口令" />
      <input
        v-model="form.confirm_password"
        data-confirm-password
        type="password"
        placeholder="确认口令"
      />
      <input v-model="form.real_name" data-real-name placeholder="姓名" />
      <select v-model="form.gender" data-gender>
        <option :value="1">男</option>
        <option :value="2">女</option>
      </select>
      <input v-model="form.age" data-age type="number" placeholder="年龄" />
      <input v-model="form.phone" data-phone placeholder="手机号" />
      <input v-model="form.allergy_history" data-allergy-history placeholder="过敏史" />
      <button type="submit" data-submit>保存</button>
      <button v-if="editingId !== null" type="button" data-cancel @click="resetForm">
        取消
      </button>
    </form>

    <form data-search class="admin-users__search" @submit.prevent="search">
      <input v-model="keyword" data-keyword placeholder="按用户名或姓名搜索" />
      <button type="submit">搜索</button>
    </form>

    <p v-if="formError" data-form-error class="admin-users__error">{{ formError }}</p>
    <p v-if="loadError" data-error class="admin-users__error">{{ loadError }}</p>
    <p v-else-if="items.length === 0" data-empty class="admin-users__empty">暂无患者</p>

    <table v-else class="admin-users__table">
      <thead>
        <tr>
          <th>用户名</th>
          <th>姓名</th>
          <th>性别</th>
          <th>年龄</th>
          <th>状态</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in items" :key="item.id" data-user-row>
          <td data-cell-username>{{ item.username }}</td>
          <td data-cell-name>{{ item.real_name ?? '-' }}</td>
          <td data-cell-gender>{{ item.gender === 2 ? '女' : '男' }}</td>
          <td data-cell-age>{{ item.age ?? '-' }}</td>
          <td data-cell-status>{{ accountStatusLabel(item.status) }}</td>
          <td class="admin-users__actions">
            <button type="button" :data-edit="item.id" @click="startEdit(item)">编辑</button>
            <button type="button" :data-status-toggle="item.id" @click="toggleStatus(item)">
              {{ accountStatusAction(item.status) }}
            </button>
            <button type="button" :data-delete="item.id" @click="remove(item.id)">删除</button>
          </td>
        </tr>
      </tbody>
    </table>

    <footer class="admin-users__pager">
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
