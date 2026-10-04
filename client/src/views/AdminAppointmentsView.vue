<!--
  管理端预约管理（TICKET-017，FUNCTIONAL_SPEC 2.7 / 5.20）。
  TICKET-030 改用 element-plus：el-form/el-input/el-select/el-date-picker 过滤，
  el-table 列预约，el-tag 状态，el-button 操作，el-pagination 翻页。

  分页查看全部预约，可按科室、就诊日期、状态与关键字过滤；可更新状态、删除记录。
  删除最后一条时页码回退（AC-F-12），列表加载失败置空并展示空状态。所有后端调用
  都经 F-1 的 `client`，本组件不认识传输层。
-->
<script setup>
import { computed, onMounted, ref } from 'vue'

import {
  APPOINTMENT_STATUS_ACTIONS,
  appointmentStatusLabel,
} from '../appointment/status.js'

const props = defineProps({
  client: { type: Object, required: true },
})
const emit = defineEmits(['error'])

const PAGE_SIZE = 10
const items = ref([])
const total = ref(0)
const page = ref(1)
const filters = ref({ keyword: '', department_id: '', visit_date: '', status: '' })
const loadError = ref(null)
const loading = ref(false)

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))

function optionalNumber(value) {
  return value === '' || value === null ? undefined : Number(value)
}

async function load() {
  loading.value = true
  try {
    const data = await props.client.adminAppointments({
      page: page.value,
      page_size: PAGE_SIZE,
      keyword: filters.value.keyword.trim() || undefined,
      department_id: optionalNumber(filters.value.department_id),
      visit_date: filters.value.visit_date || undefined,
      status: optionalNumber(filters.value.status),
    })
    items.value = data.items ?? []
    total.value = data.total ?? 0
    loadError.value = null
  } catch (failure) {
    items.value = []
    total.value = 0
    loadError.value = '预约列表加载失败'
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
  const next = Math.min(Math.max(1, target), totalPages.value)
  if (next === page.value) return
  page.value = next
  load()
}

async function update(appointmentId, status) {
  try {
    await props.client.updateAppointmentStatus(appointmentId, status)
    ElMessage.success('预约状态已更新')
    await load()
  } catch (failure) {
    emit('error', failure)
  }
}

async function remove(appointmentId) {
  try {
    await props.client.deleteAppointment(appointmentId)
    // Deleting the last row of a page falls back one page (AC-F-12).
    if (items.value.length === 1 && page.value > 1) page.value -= 1
    ElMessage.success('预约已删除')
    await load()
  } catch (failure) {
    emit('error', failure)
  }
}

onMounted(load)
</script>

<template>
  <section class="admin-appointments">
    <el-card class="admin-appointments__card" shadow="never">
      <template #header>
        <div class="card-head">
          <span class="card-title">预约管理</span>
          <el-tag size="small" type="info" effect="plain">{{ total }} 条</el-tag>
        </div>
      </template>

      <el-form
        data-filter-form
        class="admin-appointments__filters"
        :model="filters"
        @submit.prevent="search"
      >
        <el-input v-model="filters.keyword" data-filter-keyword placeholder="按患者或医生搜索" clearable />
        <el-input v-model="filters.department_id" data-filter-department-id placeholder="科室编号" />
        <span data-filter-visit-date>
          <el-date-picker
            v-model="filters.visit_date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="就诊日期"
          />
        </span>
        <el-select
          v-model="filters.status"
          data-filter-status
          placeholder="全部状态"
          :teleported="false"
        >
          <el-option value="" label="全部状态" />
          <el-option value="0" label="待确认" />
          <el-option value="1" label="已确认" />
          <el-option value="2" label="已完成" />
          <el-option value="3" label="已取消" />
        </el-select>
        <el-button type="primary" native-type="submit">筛选</el-button>
      </el-form>

      <p v-if="loadError" data-error class="admin-appointments__message admin-appointments__message--error">
        {{ loadError }}
      </p>
      <el-table v-else v-loading="loading" :data="items" stripe class="admin-appointments__table">
        <template #empty>
          <span data-empty>暂无预约</span>
        </template>
        <el-table-column prop="user_name" label="患者" min-width="100">
          <template #default="{ row }">
            <span data-patient-name>{{ row.user_name ?? '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="doctor_name" label="医生" min-width="100">
          <template #default="{ row }">
            <span data-doctor-name>{{ row.doctor_name ?? '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="department_id" label="科室编号" min-width="90">
          <template #default="{ row }">
            <span data-department-id>{{ row.department_id }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="visit_date" label="就诊日期" min-width="120">
          <template #default="{ row }">
            <span data-visit-date>{{ row.visit_date }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="time_slot" label="时段" min-width="90">
          <template #default="{ row }">
            <span data-time-slot>{{ row.time_slot }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" min-width="100">
          <template #default="{ row }">
            <el-tag data-status effect="plain">{{ appointmentStatusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="240">
          <template #default="{ row }">
            <el-button
              v-for="action in APPOINTMENT_STATUS_ACTIONS"
              :key="action.value"
              size="small"
              plain
              :data-set-status="action.value"
              @click="update(row.id, action.value)"
            >
              {{ action.label }}
            </el-button>
            <el-button size="small" type="danger" plain data-delete @click="remove(row.id)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="admin-appointments__pager">
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
.admin-appointments {
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

.admin-appointments__filters {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 12px;
}

.admin-appointments__filters :deep(.el-input) {
  width: 200px;
}

.admin-appointments__filters :deep(.el-select) {
  width: 160px;
}

/* el-date-picker does not forward attrs; its outer span carries the anchor and
   keeps the non-teleported select dropdown / date panel inside the card. */
.admin-appointments__filters [data-filter-visit-date] {
  display: inline-flex;
}

.admin-appointments__message {
  margin: 8px 0;
  color: var(--el-text-color-secondary);
}

.admin-appointments__message--error {
  color: var(--el-color-danger);
}

.admin-appointments__pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}
</style>
