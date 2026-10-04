<!--
  管理端知识库管理（TICKET-015，FUNCTIONAL_SPEC 2.12 / 5.6）。
  TICKET-030 改用 element-plus：el-form/el-input/el-select 检索 + el-upload 上传，
  el-table 列文档，el-tag 状态，el-button 操作，el-pagination 翻页。

  上传 → 「已上传 → 处理中 → 已向量化 / 失败」的状态流转、按文件名与类型检索、
  重新向量化、删除。列表只要还有状态 0 或 1 的行就按 `POLL_INTERVAL_MS` 静默
  轮询，全部完成即停，组件卸载时清除定时器（AC-F-13）。所有后端调用都走 F-1 的
  `client`，本组件不认识传输层。
-->
<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'

import { POLL_INTERVAL_MS, needsPolling } from '../knowledge/polling.js'
import { vectorStatusColor, vectorStatusLabel } from '../knowledge/status.js'

const props = defineProps({
  client: { type: Object, required: true },
})
const emit = defineEmits(['error'])

// FUNCTIONAL_SPEC 5.18: the knowledge base accepts these extensions.
const ACCEPTED_TYPES = '.txt,.pdf,.doc,.docx,.md'
const PAGE_SIZE = 10

const items = ref([])
const total = ref(0)
const page = ref(1)
const keyword = ref('')
const fileType = ref('')
const loadError = ref(null)
const loading = ref(false)

let timer = null

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))

async function load() {
  loading.value = true
  try {
    const data = await props.client.knowledgeFiles({
      page: page.value,
      page_size: PAGE_SIZE,
      keyword: keyword.value.trim() || undefined,
      file_type: fileType.value || undefined,
    })
    items.value = data.items ?? []
    total.value = data.total ?? 0
    loadError.value = null
  } catch (failure) {
    items.value = []
    total.value = 0
    loadError.value = '知识库列表加载失败'
    emit('error', failure)
  } finally {
    loading.value = false
    syncPolling()
  }
}

function syncPolling() {
  if (needsPolling(items.value)) startPolling()
  else stopPolling()
}

function startPolling() {
  if (timer === null) timer = setInterval(load, POLL_INTERVAL_MS)
}

function stopPolling() {
  if (timer !== null) {
    clearInterval(timer)
    timer = null
  }
}

function search() {
  page.value = 1
  load()
}

function goTo(target) {
  const next = Math.min(Math.max(1, target), totalPages.value)
  if (next === page.value) return
  page.value = next
  load()
}

async function upload(uploadFile) {
  const file = uploadFile?.raw
  if (!file) return
  try {
    await props.client.uploadKnowledge(file)
    ElMessage.success('文档已上传')
    await load()
  } catch (failure) {
    emit('error', failure)
  }
}

async function revectorize(fileId) {
  try {
    await props.client.revectorizeKnowledge(fileId)
    ElMessage.success('已重新触发向量化')
    await load()
  } catch (failure) {
    emit('error', failure)
  }
}

async function remove(fileId) {
  try {
    await props.client.deleteKnowledge(fileId)
    // Deleting the last row of a page falls back one page (AC-F-12).
    if (items.value.length === 1 && page.value > 1) page.value -= 1
    ElMessage.success('文档已删除')
    await load()
  } catch (failure) {
    emit('error', failure)
  }
}

onMounted(load)
onUnmounted(stopPolling)
</script>

<template>
  <section class="knowledge">
    <header class="page-head">
      <h1 class="page-head__title">知识库管理</h1>
      <el-upload
        data-upload
        class="knowledge__upload"
        :auto-upload="false"
        :show-file-list="false"
        :accept="ACCEPTED_TYPES"
        :on-change="upload"
      >
        <el-button type="primary">上传文件</el-button>
      </el-upload>
    </header>

    <el-card class="knowledge__card" shadow="never">
      <template #header>
        <div class="card-head">
          <span class="card-title">知识库文档</span>
          <el-tag size="small" type="info" effect="plain">{{ total }} 个</el-tag>
        </div>
      </template>

      <header class="knowledge__toolbar">
        <el-form data-search class="knowledge__search" @submit.prevent="search">
          <el-input v-model="keyword" data-keyword placeholder="按文件名或类型搜索" clearable />
          <el-select
            v-model="fileType"
            data-file-type
            placeholder="全部类型"
            :teleported="false"
          >
            <el-option value="" label="全部类型" />
            <el-option value="txt" label="txt" />
            <el-option value="md" label="md" />
            <el-option value="markdown" label="markdown" />
            <el-option value="pdf" label="pdf" />
            <el-option value="doc" label="doc" />
            <el-option value="docx" label="docx" />
          </el-select>
          <el-button native-type="submit">搜索</el-button>
        </el-form>
      </header>

      <p v-if="loadError" data-error class="knowledge__message knowledge__message--error">
        {{ loadError }}
      </p>
      <el-table v-else v-loading="loading" :data="items" stripe class="knowledge__table">
        <template #empty>
          <span data-empty>暂无知识库文档</span>
        </template>
        <el-table-column prop="file_name" label="文件名" min-width="180">
          <template #default="{ row }">
            <span data-file-name>{{ row.file_name }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="file_type" label="类型" min-width="90">
          <template #default="{ row }">
            <span data-file-type>{{ row.file_type }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="file_size" label="大小" min-width="90">
          <template #default="{ row }">
            <span data-file-size>{{ row.file_size }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="chunk_count" label="分块数" min-width="90">
          <template #default="{ row }">
            <span data-chunk-count>{{ row.chunk_count }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" min-width="110">
          <template #default="{ row }">
            <el-tag data-status :type="vectorStatusColor(row.vector_status)" effect="light">
              {{ vectorStatusLabel(row.vector_status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="200">
          <template #default="{ row }">
            <el-button size="small" data-revectorize @click="revectorize(row.id)">
              重新向量化
            </el-button>
            <el-button size="small" type="danger" plain data-delete @click="remove(row.id)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="knowledge__pager">
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
.knowledge {
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

.knowledge__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.knowledge__search {
  display: flex;
  gap: 12px;
}

.knowledge__search :deep(.el-input) {
  width: 240px;
}

.knowledge__search :deep(.el-select) {
  width: 140px;
}

.knowledge__message {
  margin: 8px 0;
  color: var(--el-text-color-secondary);
}

.knowledge__message--error {
  color: var(--el-color-danger);
}

.knowledge__pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}
</style>
