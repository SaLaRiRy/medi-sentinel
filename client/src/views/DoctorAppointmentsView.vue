<!--
  医生工作台：本人排期（TICKET-017，FUNCTIONAL_SPEC 2.7 / 5.20）。TICKET-029 改用
  element-plus：el-card + el-table + el-tag 状态 + el-button 操作。

  只读本人排期并按就诊日期升序展示；医生可把状态更新为已确认 / 已完成 / 已取消。
  状态着色只在医生端出现（warning / success / info / danger），未知值回退「待确认」
  （AC-F-11）。所有后端调用都经 F-1 的 `client`。
-->
<script setup>
import { onMounted, ref } from 'vue'

import {
  APPOINTMENT_STATUS_ACTIONS,
  appointmentStatusColor,
  appointmentStatusLabel,
} from '../appointment/status.js'

const props = defineProps({
  client: { type: Object, required: true },
})
const emit = defineEmits(['error'])

const items = ref([])
const loading = ref(false)
const loadError = ref(null)

async function load() {
  loading.value = true
  try {
    items.value = await props.client.doctorAppointments()
    loadError.value = null
  } catch (failure) {
    items.value = []
    loadError.value = '排期加载失败'
    emit('error', failure)
  } finally {
    loading.value = false
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
    <el-card class="doctor-appointments__card" shadow="never">
      <template #header>
        <div class="card-head">
          <span class="card-head__title">我的排期</span>
          <el-tag size="small" effect="plain" type="info">{{ items.length }} 条</el-tag>
        </div>
      </template>

      <p v-if="loadError" data-error class="doctor-appointments__message doctor-appointments__message--error">
        {{ loadError }}
      </p>
      <el-table
        v-else
        v-loading="loading"
        :data="items"
        stripe
        class="doctor-appointments__table"
      >
        <template #empty>
          <span data-empty>暂无预约</span>
        </template>
        <el-table-column prop="user_name" label="患者" min-width="110">
          <template #default="{ row }">
            <span data-patient-name>{{ row.user_name ?? '-' }}</span>
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
            <el-tag
              data-status
              :data-status-color="appointmentStatusColor(row.status)"
              :type="appointmentStatusColor(row.status)"
              effect="light"
            >
              {{ appointmentStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="200">
          <template #default="{ row }">
            <el-button
              v-for="action in APPOINTMENT_STATUS_ACTIONS"
              :key="action.value"
              :data-set-status="action.value"
              size="small"
              plain
              @click="update(row.id, action.value)"
            >
              {{ action.label }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </section>
</template>

<style scoped>
.doctor-appointments {
  padding: 16px;
}

.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.card-head__title {
  font-size: 16px;
  font-weight: 600;
}

.doctor-appointments__message {
  margin: 8px 0;
  color: var(--el-text-color-secondary);
}

.doctor-appointments__message--error {
  color: var(--el-color-danger);
}
</style>
