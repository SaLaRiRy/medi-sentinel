<!--
  管理端预约管理（TICKET-017，FUNCTIONAL_SPEC 2.7 / 5.20）。

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

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))

function optionalNumber(value) {
  return value === '' || value === null ? undefined : Number(value)
}

async function load() {
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
    await load()
  } catch (failure) {
    emit('error', failure)
  }
}

onMounted(load)
</script>

<template>
  <section class="admin-appointments">
    <form data-filter-form class="admin-appointments__filters" @submit.prevent="search">
      <input v-model="filters.keyword" data-filter-keyword placeholder="按患者或医生搜索" />
      <input
        v-model="filters.department_id"
        data-filter-department-id
        placeholder="科室编号"
      />
      <input v-model="filters.visit_date" data-filter-visit-date type="date" />
      <select v-model="filters.status" data-filter-status>
        <option value="">全部状态</option>
        <option value="0">待确认</option>
        <option value="1">已确认</option>
        <option value="2">已完成</option>
        <option value="3">已取消</option>
      </select>
      <button type="submit">筛选</button>
    </form>

    <p v-if="loadError" data-error class="admin-appointments__error">
      {{ loadError }}
    </p>
    <p v-else-if="items.length === 0" data-empty class="admin-appointments__empty">
      暂无预约
    </p>

    <table v-else class="admin-appointments__table">
      <thead>
        <tr>
          <th>患者</th>
          <th>医生</th>
          <th>科室编号</th>
          <th>就诊日期</th>
          <th>时段</th>
          <th>状态</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in items" :key="item.id" data-appointment-row>
          <td data-patient-name>{{ item.user_name ?? '-' }}</td>
          <td data-doctor-name>{{ item.doctor_name ?? '-' }}</td>
          <td>{{ item.department_id }}</td>
          <td data-visit-date>{{ item.visit_date }}</td>
          <td>{{ item.time_slot }}</td>
          <td data-status>{{ appointmentStatusLabel(item.status) }}</td>
          <td class="admin-appointments__actions">
            <button
              v-for="action in APPOINTMENT_STATUS_ACTIONS"
              :key="action.value"
              type="button"
              :data-set-status="action.value"
              @click="update(item.id, action.value)"
            >
              {{ action.label }}
            </button>
            <button type="button" data-delete @click="remove(item.id)">删除</button>
          </td>
        </tr>
      </tbody>
    </table>

    <footer class="admin-appointments__pager">
      <button type="button" data-prev :disabled="page <= 1" @click="goTo(page - 1)">
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
