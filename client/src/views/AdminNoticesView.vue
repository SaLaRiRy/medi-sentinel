<!--
  管理端公告管理（TICKET-021，FUNCTIONAL_SPEC 2.8 / SPEC.md 5.4）。
  TICKET-030 改用 element-plus：el-form/el-input/el-select 录入，el-table 列公告，
  el-tag 状态，el-button 操作，el-pagination 翻页。

  分页查看全部状态的公告，新建、编辑（含发布/下架状态流转）与删除。标题必填由前端
  提示（FUNCTIONAL_SPEC 5.19），其余校验与 404 由后端承担。列表加载失败呈现空态；
  删除当前页最后一条时页码回退（本票验收）。所有后端调用都经 F-1 的 `client`。
-->
<script setup>
import { onMounted, ref } from 'vue'

import { contentStatusColor, contentStatusLabel } from '../content/status.js'

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

const emptyForm = () => ({ title: '', content: '', status: 1 })
const form = ref(emptyForm())

async function load() {
  loading.value = true
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
    ElMessage.success(editingId.value === null ? '公告已创建' : '公告已更新')
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
    ElMessage.success('公告已删除')
    await load()
  } catch (failure) {
    emit('error', failure)
  }
}

onMounted(load)
</script>

<template>
  <section class="admin-notices">
    <el-card class="admin-notices__card admin-notices__card--form" shadow="never">
      <template #header>
        <span class="card-title">{{ editingId === null ? '新建公告' : '编辑公告' }}</span>
      </template>

      <el-form
        data-notice-form
        :model="form"
        label-width="88px"
        class="admin-notices__form"
        @submit.prevent="submit"
      >
        <el-form-item label="公告标题">
          <el-input v-model="form.title" data-title placeholder="公告标题" />
        </el-form-item>
        <el-form-item label="公告正文">
          <el-input v-model="form.content" data-content type="textarea" :rows="3" placeholder="公告正文" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="form.status" data-status :teleported="false">
            <el-option :value="1" label="已发布" />
            <el-option :value="0" label="已下架" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" data-submit native-type="submit">保存</el-button>
          <el-button v-if="editingId !== null" data-cancel @click="resetForm">取消</el-button>
        </el-form-item>
      </el-form>

      <p v-if="formError" data-form-error class="admin-notices__message admin-notices__message--error">
        {{ formError }}
      </p>
    </el-card>

    <el-card class="admin-notices__card" shadow="never">
      <template #header>
        <div class="card-head">
          <span class="card-title">公告列表</span>
          <el-tag size="small" type="info" effect="plain">{{ total }} 条</el-tag>
        </div>
      </template>

      <el-form data-search class="admin-notices__search" @submit.prevent="search">
        <el-input v-model="keyword" data-keyword placeholder="按标题搜索" clearable />
        <el-button native-type="submit">搜索</el-button>
      </el-form>

      <p v-if="loadError" data-error class="admin-notices__message admin-notices__message--error">
        {{ loadError }}
      </p>
      <el-table v-else v-loading="loading" :data="items" stripe class="admin-notices__table">
        <template #empty>
          <span data-empty>暂无公告</span>
        </template>
        <el-table-column prop="title" label="标题" min-width="200">
          <template #default="{ row }">
            <span data-cell-title>{{ row.title }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="content" label="正文" min-width="240">
          <template #default="{ row }">
            <span data-cell-content>{{ row.content }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" min-width="100">
          <template #default="{ row }">
            <el-tag data-cell-status :type="contentStatusColor(row.status)" effect="light">
              {{ contentStatusLabel(row.status) }}
            </el-tag>
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

      <div class="admin-notices__pager">
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
.admin-notices {
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

.admin-notices__form {
  max-width: 640px;
}

/* Keep the non-teleported el-select dropdown from being clipped by el-card. */
.admin-notices__card--form,
.admin-notices__card--form :deep(.el-card__body) {
  overflow: visible;
}

.admin-notices__search {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
}

.admin-notices__search :deep(.el-input) {
  max-width: 320px;
}

.admin-notices__message {
  margin: 8px 0;
  color: var(--el-text-color-secondary);
}

.admin-notices__message--error {
  color: var(--el-color-danger);
}

.admin-notices__pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}
</style>
