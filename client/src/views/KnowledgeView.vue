<!--
  管理端知识库管理（TICKET-015，FUNCTIONAL_SPEC 2.12 / 5.6）。

  上传 → 「已上传 → 处理中 → 已向量化 / 失败」的状态流转、按文件名与类型检索、
  重新向量化、删除。列表只要还有状态 0 或 1 的行就按 `POLL_INTERVAL_MS` 静默
  轮询，全部完成即停，组件卸载时清除定时器（AC-F-13）。所有后端调用都走 F-1 的
  `client`，本组件不认识传输层。
-->
<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'

import { POLL_INTERVAL_MS, needsPolling } from '../knowledge/polling.js'
import { vectorStatusLabel } from '../knowledge/status.js'

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

let timer = null

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))

async function load() {
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

async function upload(event) {
  const file = event.target.files?.[0]
  if (!file) return
  try {
    await props.client.uploadKnowledge(file)
    await load()
  } catch (failure) {
    emit('error', failure)
  } finally {
    event.target.value = ''
  }
}

async function revectorize(fileId) {
  try {
    await props.client.revectorizeKnowledge(fileId)
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
    <header class="knowledge__toolbar">
      <form data-search class="knowledge__search" @submit.prevent="search">
        <input v-model="keyword" data-keyword placeholder="按文件名或类型搜索" />
        <select v-model="fileType" data-file-type>
          <option value="">全部类型</option>
          <option value="txt">txt</option>
          <option value="md">md</option>
          <option value="markdown">markdown</option>
          <option value="pdf">pdf</option>
          <option value="doc">doc</option>
          <option value="docx">docx</option>
        </select>
        <button type="submit">搜索</button>
      </form>
      <label class="knowledge__upload">
        上传文档
        <input
          data-upload
          type="file"
          :accept="ACCEPTED_TYPES"
          @change="upload"
        />
      </label>
    </header>

    <p v-if="loadError" data-error class="knowledge__error">{{ loadError }}</p>
    <p v-else-if="items.length === 0" data-empty class="knowledge__empty">
      暂无知识库文档
    </p>

    <table v-else class="knowledge__table">
      <thead>
        <tr>
          <th>文件名</th>
          <th>类型</th>
          <th>大小</th>
          <th>分块数</th>
          <th>状态</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in items" :key="item.id" data-knowledge-row>
          <td data-file-name>{{ item.file_name }}</td>
          <td>{{ item.file_type }}</td>
          <td>{{ item.file_size }}</td>
          <td data-chunk-count>{{ item.chunk_count }}</td>
          <td data-status>{{ vectorStatusLabel(item.vector_status) }}</td>
          <td class="knowledge__actions">
            <button type="button" data-revectorize @click="revectorize(item.id)">
              重新向量化
            </button>
            <button type="button" data-delete @click="remove(item.id)">删除</button>
          </td>
        </tr>
      </tbody>
    </table>

    <footer class="knowledge__pager">
      <button
        type="button"
        data-prev
        :disabled="page <= 1"
        @click="goTo(page - 1)"
      >
        上一页
      </button>
      <span data-page>{{ page }} / {{ totalPages }}</span>
      <button
        type="button"
        data-next
        :disabled="page >= totalPages"
        @click="goTo(page + 1)"
      >
        下一页
      </button>
    </footer>
  </section>
</template>
