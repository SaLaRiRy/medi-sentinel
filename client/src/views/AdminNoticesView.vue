<!--
  管理端公告管理（TICKET-021，FUNCTIONAL_SPEC 2.8 / SPEC.md 5.4）。

  分页查看全部状态的公告，新建、编辑（含发布/下架状态流转）与删除。标题必填由前端
  提示（FUNCTIONAL_SPEC 5.19），其余校验与 404 由后端承担。列表加载失败呈现空态；
  删除当前页最后一条时页码回退（本票验收）。所有后端调用都经 F-1 的 `client`。
-->
<script setup>
import { onMounted, ref } from 'vue'

import { contentStatusLabel } from '../content/status.js'

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

const emptyForm = () => ({ title: '', content: '', status: 1 })
const form = ref(emptyForm())

async function load() {
  try {
    const data = await props.client.adminNotices({
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
    loadError.value = '公告列表加载失败'
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
    title: item.title,
    content: item.content ?? '',
    status: item.status ?? 1,
  }
}

function payload() {
  return {
    title: form.value.title.trim(),
    content: form.value.content,
    status: Number(form.value.status),
  }
}

async function submit() {
  if (!form.value.title.trim()) {
    formError.value = '公告标题必填'
    return
  }
  try {
    if (editingId.value === null) await props.client.createNotice(payload())
    else await props.client.updateNotice(editingId.value, payload())
    resetForm()
    await load()
  } catch (failure) {
    emit('error', failure)
  }
}

async function remove(noticeId) {
  try {
    await props.client.deleteNotice(noticeId)
    if (items.value.length === 1 && page.value > 1) page.value -= 1
    await load()
  } catch (failure) {
    emit('error', failure)
  }
}

onMounted(load)
</script>

<template>
  <section class="admin-notices">
    <form data-notice-form class="admin-notices__form" @submit.prevent="submit">
      <input v-model="form.title" data-title placeholder="公告标题" />
      <textarea v-model="form.content" data-content placeholder="公告正文"></textarea>
      <select v-model.number="form.status" data-status>
        <option :value="1">已发布</option>
        <option :value="0">已下架</option>
      </select>
      <button type="submit" data-submit>保存</button>
      <button v-if="editingId !== null" type="button" data-cancel @click="resetForm">
        取消
      </button>
    </form>

    <form data-search class="admin-notices__search" @submit.prevent="search">
      <input v-model="keyword" data-keyword placeholder="按标题搜索" />
      <button type="submit">搜索</button>
    </form>

    <p v-if="formError" data-form-error class="admin-notices__error">{{ formError }}</p>
    <p v-if="loadError" data-error class="admin-notices__error">{{ loadError }}</p>
    <p v-else-if="items.length === 0" data-empty class="admin-notices__empty">
      暂无公告
    </p>

    <table v-else class="admin-notices__table">
      <thead>
        <tr>
          <th>标题</th>
          <th>正文</th>
          <th>状态</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in items" :key="item.id" data-notice-row>
          <td data-cell-title>{{ item.title }}</td>
          <td data-cell-content>{{ item.content }}</td>
          <td data-cell-status>{{ contentStatusLabel(item.status) }}</td>
          <td class="admin-notices__actions">
            <button type="button" :data-edit="item.id" @click="startEdit(item)">编辑</button>
            <button type="button" :data-delete="item.id" @click="remove(item.id)">删除</button>
          </td>
        </tr>
      </tbody>
    </table>

    <footer class="admin-notices__pager">
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
