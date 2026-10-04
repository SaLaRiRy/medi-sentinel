<!--
  管理端文章管理（TICKET-021，FUNCTIONAL_SPEC 2.8 / SPEC.md 5.4）。
  TICKET-030 改用 element-plus：el-form/el-input/el-select 录入，el-table 列文章，
  el-tag 状态，el-button 操作，el-pagination 翻页。

  分页查看全部状态的文章，新建、编辑（含发布/下架状态流转）与删除。标题必填由前端
  提示（FUNCTIONAL_SPEC 5.19），其余校验与 404 由后端承担。列表加载失败呈现空态；
  删除当前页最后一条时页码回退（本票验收）。所有后端调用都经 F-1 的 `client`。
-->
<script setup>
import { onMounted, ref } from 'vue'

import {
  ARTICLE_CATEGORIES,
  contentStatusColor,
  contentStatusLabel,
} from '../content/status.js'

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
const formVisible = ref(false)
const loading = ref(false)

const emptyForm = () => ({
  title: '',
  category: '',
  summary: '',
  content: '',
  status: 1,
})
const form = ref(emptyForm())

async function load() {
  loading.value = true
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
  formVisible.value = false
}

function openCreate() {
  resetForm()
  formVisible.value = true
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
  formVisible.value = true
}

function payload() {
  const body = { title: form.value.title.trim(), status: Number(form.value.status) }
  // el-select may clear to '' or undefined.
  const category = form.value.category ?? ''
  if (category.trim()) body.category = category.trim()
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
    ElMessage.success(editingId.value === null ? '文章已创建' : '文章已更新')
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
    ElMessage.success('文章已删除')
    await load()
  } catch (failure) {
    emit('error', failure)
  }
}

onMounted(load)
</script>

<template>
  <section class="admin-articles">
    <header class="page-head">
      <h1 class="page-head__title">文章管理</h1>
      <el-button type="primary" data-create @click="openCreate">新建文章</el-button>
    </header>

    <el-dialog
      v-model="formVisible"
      :title="editingId === null ? '新建文章' : '编辑文章'"
      width="600px"
      :teleported="false"
      class="admin-articles__dialog"
    >
      <el-form
        data-article-form
        :model="form"
        label-width="88px"
        class="admin-articles__form"
        @submit.prevent="submit"
      >
        <el-form-item label="文章标题">
          <el-input v-model="form.title" data-title placeholder="文章标题" />
        </el-form-item>
        <el-form-item label="分类">
          <el-select
            v-model="form.category"
            data-category
            placeholder="不选分类"
            clearable
            value-on-clear=""
            :teleported="false"
          >
            <el-option v-for="name in ARTICLE_CATEGORIES" :key="name" :value="name" :label="name" />
          </el-select>
        </el-form-item>
        <el-form-item label="摘要">
          <el-input v-model="form.summary" data-summary placeholder="摘要" />
        </el-form-item>
        <el-form-item label="正文">
          <el-input v-model="form.content" data-content type="textarea" :rows="3" placeholder="正文" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="form.status" data-status :teleported="false">
            <el-option :value="1" label="已发布" />
            <el-option :value="0" label="已下架" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" data-submit native-type="submit">保存</el-button>
          <el-button data-cancel @click="resetForm">取消</el-button>
        </el-form-item>
      </el-form>

      <p v-if="formError" data-form-error class="admin-articles__message admin-articles__message--error">
        {{ formError }}
      </p>
    </el-dialog>

    <el-card class="admin-articles__card" shadow="never">
      <template #header>
        <div class="card-head">
          <span class="card-title">文章列表</span>
          <el-tag size="small" type="info" effect="plain">{{ total }} 篇</el-tag>
        </div>
      </template>

      <el-form data-search class="admin-articles__search" @submit.prevent="search">
        <el-input v-model="keyword" data-keyword placeholder="按标题搜索" clearable />
        <el-button native-type="submit">搜索</el-button>
      </el-form>

      <p v-if="loadError" data-error class="admin-articles__message admin-articles__message--error">
        {{ loadError }}
      </p>
      <el-table v-else v-loading="loading" :data="items" stripe class="admin-articles__table">
        <template #empty>
          <span data-empty>暂无文章</span>
        </template>
        <el-table-column prop="title" label="标题" min-width="200">
          <template #default="{ row }">
            <span data-cell-title>{{ row.title }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="category" label="分类" min-width="120">
          <template #default="{ row }">
            <span data-cell-category>{{ row.category ?? '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" min-width="100">
          <template #default="{ row }">
            <el-tag data-cell-status :type="contentStatusColor(row.status)" effect="light">
              {{ contentStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="view_count" label="浏览量" min-width="90">
          <template #default="{ row }">
            <span data-cell-views>{{ row.view_count }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="160">
          <template #default="{ row }">
            <el-button size="small" :data-edit="row.id" @click="startEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" plain :data-delete="row.id" @click="remove(row.id)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="admin-articles__pager">
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
.admin-articles {
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

.admin-articles__form {
  max-width: 640px;
}

/* Keep the non-teleported el-select dropdown from being clipped by el-card. */
.admin-articles__card--form,
.admin-articles__card--form :deep(.el-card__body) {
  overflow: visible;
}

.admin-articles__search {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
}

.admin-articles__search :deep(.el-input) {
  max-width: 320px;
}

.admin-articles__message {
  margin: 8px 0;
  color: var(--el-text-color-secondary);
}

.admin-articles__message--error {
  color: var(--el-color-danger);
}

.admin-articles__pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}
</style>
