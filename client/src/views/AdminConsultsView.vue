<!--
  管理端人工问诊（TICKET-019，SPEC.md 5.4「人工问诊」）。

  分页查看全部工单，可按状态过滤，并可删除工单及其全部回复。删除最后一页的最后
  一条时页码回退（AC-F-12）。主诉按第一个全角冒号拆回标题与正文（AC-F-15）。
  所有后端调用都经 F-1 的 `client`；列表加载失败呈现空态并上报。
-->
<script setup>
import { onMounted, ref } from 'vue'

import { decodeChiefComplaint } from '../consult/complaint.js'
import { consultStatusLabel } from '../consult/status.js'

const props = defineProps({
  client: { type: Object, required: true },
})
const emit = defineEmits(['error'])

const PAGE_SIZE = 10
const items = ref([])
const total = ref(0)
const page = ref(1)
const status = ref('')
const loadError = ref(null)

function parts(item) {
  return decodeChiefComplaint(item.chief_complaint)
}

function query() {
  const params = { page: page.value, page_size: PAGE_SIZE }
  if (status.value !== '') params.status = Number(status.value)
  return params
}

async function load() {
  try {
    const data = await props.client.adminConsults(query())
    items.value = data.items
    total.value = data.total
    loadError.value = null
  } catch (failure) {
    items.value = []
    total.value = 0
    loadError.value = '问诊工单加载失败'
    emit('error', failure)
  }
}

async function filter() {
  page.value = 1
  await load()
}

async function next() {
  if (page.value * PAGE_SIZE >= total.value) return
  page.value += 1
  await load()
}

async function previous() {
  if (page.value <= 1) return
  page.value -= 1
  await load()
}

async function remove(consultId) {
  try {
    await props.client.deleteConsult(consultId)
    if (items.value.length === 1 && page.value > 1) page.value -= 1
    await load()
  } catch (failure) {
    emit('error', failure)
  }
}

onMounted(load)
</script>

<template>
  <section class="admin-consults">
    <select v-model="status" data-status-filter @change="filter">
      <option value="">全部状态</option>
      <option value="0">待回复</option>
      <option value="1">已回复</option>
    </select>

    <p v-if="loadError" data-error class="admin-consults__error">{{ loadError }}</p>
    <p v-else-if="items.length === 0" data-empty class="admin-consults__empty">
      暂无问诊工单
    </p>

    <table v-else class="admin-consults__table">
      <thead>
        <tr>
          <th>患者</th>
          <th>主诉</th>
          <th>医生</th>
          <th>状态</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in items" :key="item.id" data-consult-row>
          <td data-cell-patient>{{ item.user_name ?? '-' }}</td>
          <td data-cell-complaint>
            {{ parts(item).title }}：{{ parts(item).body }}
          </td>
          <td data-cell-doctor>{{ item.doctor_name ?? '待分配' }}</td>
          <td data-cell-status>{{ consultStatusLabel(item.status) }}</td>
          <td>
            <button type="button" :data-delete="item.id" @click="remove(item.id)">
              删除
            </button>
          </td>
        </tr>
      </tbody>
    </table>

    <div class="admin-consults__pager">
      <button type="button" data-prev-page @click="previous">上一页</button>
      <button type="button" data-next-page @click="next">下一页</button>
    </div>
  </section>
</template>
