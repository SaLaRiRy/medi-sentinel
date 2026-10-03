<!--
  医生工作台：本人排期（TICKET-017，FUNCTIONAL_SPEC 2.7 / 5.20）。

  只读本人排期并按就诊日期升序展示；医生可把状态更新为已确认 / 已完成 / 已取消。
  状态着色只在医生端出现（warning / success / info / danger），未知值回退
  「待确认」（AC-F-11）。所有后端调用都经 F-1 的 `client`。
-->
<script setup>
import { onMounted, ref } from 'vue'

import {
  appointmentStatusColor,
  appointmentStatusLabel,
} from '../appointment/status.js'

const props = defineProps({
  client: { type: Object, required: true },
})
const emit = defineEmits(['error'])

const STATUS_ACTIONS = [
  { value: 1, label: '确认' },
  { value: 2, label: '完成' },
  { value: 3, label: '取消' },
]

const items = ref([])
const loadError = ref(null)

async function load() {
  try {
    items.value = await props.client.doctorAppointments()
    loadError.value = null
  } catch (failure) {
    items.value = []
    loadError.value = '排期加载失败'
    emit('error', failure)
  }
}

async function update(appointmentId, status) {
  try {
    await props.client.updateAppointmentStatus(appointmentId, status)
    await load()
  } catch (failure) {
    emit('error', failure)
  }
}

onMounted(load)
</script>

<template>
  <section class="doctor-appointments">
    <p v-if="loadError" data-error class="doctor-appointments__error">
      {{ loadError }}
    </p>
    <p v-else-if="items.length === 0" data-empty class="doctor-appointments__empty">
      暂无预约
    </p>

    <table v-else class="doctor-appointments__table">
      <thead>
        <tr>
          <th>患者</th>
          <th>就诊日期</th>
          <th>时段</th>
          <th>状态</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in items" :key="item.id" data-appointment-row>
          <td data-patient-name>{{ item.user_name ?? '-' }}</td>
          <td data-visit-date>{{ item.visit_date }}</td>
          <td data-time-slot>{{ item.time_slot }}</td>
          <td
            data-status
            :data-status-color="appointmentStatusColor(item.status)"
          >
            {{ appointmentStatusLabel(item.status) }}
          </td>
          <td class="doctor-appointments__actions">
            <button
              v-for="action in STATUS_ACTIONS"
              :key="action.value"
              type="button"
              :data-set-status="action.value"
              @click="update(item.id, action.value)"
            >
              {{ action.label }}
            </button>
          </td>
        </tr>
      </tbody>
    </table>
  </section>
</template>
