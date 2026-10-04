<!--
  管理端文章管理（TICKET-021，FUNCTIONAL_SPEC 2.8 / SPEC.md 5.4）。

  分页查看全部状态的文章，新建、编辑（含发布/下架状态流转）与删除。标题必填由前端
  提示（FUNCTIONAL_SPEC 5.19），其余校验与 404 由后端承担。列表加载失败呈现空态；
  删除当前页最后一条时页码回退（本票验收）。所有后端调用都经 F-1 的 `client`。
-->
<script setup>
import { onMounted, ref } from 'vue'

import { ARTICLE_CATEGORIES, contentStatusLabel } from '../content/status.js'

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
  title: '',
  category: '',
  summary: '',
  content: '',
  status: 1,
})
const form = ref(emptyForm())

async function load() {
  try {
    const data = await props.client.adminArticles({
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
    loadError.value = '文章列表加载失败'
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
    category: item.category ?? '',
    summary: item.summary ?? '',
    content: item.content ?? '',
    status: item.status ?? 1,
  }
}

function payload() {
  const body = { title: form.value.title.trim(), status: Number(form.value.status) }
  if (form.value.category.trim()) body.category = form.value.category.trim()
  if (form.value.summary.trim()) body.summary = form.value.summary.trim()
  if (form.value.content.trim()) body.content = form.value.content.trim()
  return body
}

async function submit() {
  if (!form.value.title.trim()) {
    formError.value = '文章标题必填'
    return
  }
  try {
    if (editingId.value === null) await props.client.createArticle(payload())
    else await props.client.updateArticle(editingId.value, payload())
    resetForm()
    await load()
  } catch (failure) {
    emit('error', failure)
  }
}

async function remove(articleId) {
  try {
    await props.client.deleteArticle(articleId)
    if (items.value.length === 1 && page.value > 1) page.value -= 1
    await load()
  } catch (failure) {
    emit('error', failure)
  }
}

onMounted(load)
</script>

<template>
  <section class="admin-articles">
    <form data-article-form class="admin-articles__form" @submit.prevent="submit">
      <input v-model="form.title" data-title placeholder="文章标题" />
      <select v-model="form.category" data-category>
        <option value="">不选分类</option>
        <option v-for="name in ARTICLE_CATEGORIES" :key="name" :value="name">
          {{ name }}
        </option>
      </select>
      <input v-model="form.summary" data-summary placeholder="摘要" />
      <textarea v-model="form.content" data-content placeholder="正文"></textarea>
      <select v-model.number="form.status" data-status>
        <option :value="1">已发布</option>
        <option :value="0">已下架</option>
      </select>
      <button type="submit" data-submit>保存</button>
      <button v-if="editingId !== null" type="button" data-cancel @click="resetForm">
        取消
      </button>
    </form>

    <form data-search class="admin-articles__search" @submit.prevent="search">
      <input v-model="keyword" data-keyword placeholder="按标题搜索" />
      <button type="submit">搜索</button>
    </form>

    <p v-if="formError" data-form-error class="admin-articles__error">{{ formError }}</p>
    <p v-if="loadError" data-error class="admin-articles__error">{{ loadError }}</p>
    <p v-else-if="items.length === 0" data-empty class="admin-articles__empty">
      暂无文章
    </p>

    <table v-else class="admin-articles__table">
      <thead>
        <tr>
          <th>标题</th>
          <th>分类</th>
          <th>状态</th>
          <th>浏览量</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in items" :key="item.id" data-article-row>
          <td data-cell-title>{{ item.title }}</td>
          <td data-cell-category>{{ item.category ?? '-' }}</td>
          <td data-cell-status>{{ contentStatusLabel(item.status) }}</td>
          <td data-cell-views>{{ item.view_count }}</td>
          <td class="admin-articles__actions">
            <button type="button" :data-edit="item.id" @click="startEdit(item)">编辑</button>
            <button type="button" :data-delete="item.id" @click="remove(item.id)">删除</button>
          </td>
        </tr>
      </tbody>
    </table>

    <footer class="admin-articles__pager">
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
