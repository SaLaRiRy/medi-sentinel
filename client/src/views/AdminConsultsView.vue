<!--
  管理端人工问诊（TICKET-019，SPEC.md 5.4「人工问诊」）。
  TICKET-030 改用 element-plus：el-select 状态过滤，el-table 列工单，el-tag 状态，
  el-button 删除，el-pagination 翻页。

  分页查看全部工单，可按状态过滤，并可删除工单及其全部回复。删除最后一页的最后
  一条时页码回退（AC-F-12）。主诉按第一个全角冒号拆回标题与正文（AC-F-15）。
  所有后端调用都经 F-1 的 `client`；列表加载失败呈现空态并上报。
-->
<script setup>
import { computed, onMounted, ref, watch } from 'vue'

import { decodeChiefComplaint } from '../consult/complaint.js'
import { consultStatusColor, consultStatusLabel } from '../consult/status.js'

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
const loading = ref(false)

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))

function parts(item) {
  return decodeChiefComplaint(item.chief_complaint)
}

function query() {
  const params = { page: page.value, page_size: PAGE_SIZE }
  if (status.value !== '') params.status = Number(status.value)
  return params
}

async function load() {
  loading.value = true
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
  } finally {
    loading.value = false
  }
}

// el-select emits model updates, not a native change; a watcher keeps the
// "changing the status filter returns to page 1 and reloads" behaviour.
watch(status, () => {
  page.value = 1
  load()
})

function goTo(target) {
  const next = Math.min(Math.max(1, target), totalPages.value)
  if (next === page.value) return
  page.value = next
  load()
}

async function remove(consultId) {
  try {
    await props.client.deleteConsult(consultId)
    if (items.value.length === 1 && page.value > 1) page.value -= 1
    ElMessage.success('工单已删除')
    await load()
  } catch (failure) {
    emit('error', failure)
  }
}

onMounted(load)
</script>

<template>
  <section class="admin-consults">
    <el-card class="admin-consults__card" shadow="never">
      <template #header>
        <div class="card-head">
          <span class="card-title">人工问诊工单</span>
          <el-tag size="small" type="info" effect="plain">{{ total }} 条</el-tag>
        </div>
      </template>

      <el-select
        v-model="status"
        data-status-filter
        placeholder="全部状态"
        class="admin-consults__filter"
        :teleported="false"
      >
        <el-option value="" label="全部状态" />
        <el-option value="0" label="待回复" />
        <el-option value="1" label="已回复" />
      </el-select>

      <p v-if="loadError" data-error class="admin-consults__message admin-consults__message--error">
        {{ loadError }}
      </p>
      <el-table v-else v-loading="loading" :data="items" stripe class="admin-consults__table">
        <template #empty>
          <span data-empty>暂无问诊工单</span>
        </template>
        <el-table-column prop="user_name" label="患者" min-width="100">
          <template #default="{ row }">
            <span data-cell-patient>{{ row.user_name ?? '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="主诉" min-width="220">
          <template #default="{ row }">
            <span data-cell-complaint>{{ parts(row).title }}：{{ parts(row).body }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="doctor_name" label="医生" min-width="110">
          <template #default="{ row }">
            <span data-cell-doctor>{{ row.doctor_name ?? '待分配' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" min-width="100">
          <template #default="{ row }">
            <el-tag data-cell-status :type="consultStatusColor(row.status)" effect="light">
              {{ consultStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="110">
          <template #default="{ row }">
            <el-button size="small" type="danger" plain :data-delete="row.id" @click="remove(row.id)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="admin-consults__pager">
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
.admin-consults {
  padding: 16px;
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

.admin-consults__filter {
  width: 180px;
  margin-bottom: 12px;
}

.admin-consults__message {
  margin: 8px 0;
  color: var(--el-text-color-secondary);
}

.admin-consults__message--error {
  color: var(--el-color-danger);
}

.admin-consults__pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}
</style>
