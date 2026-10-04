<!--
  患者侧预约挂号（TICKET-017，FUNCTIONAL_SPEC 2.7 / 5.19 / 5.20）。TICKET-029 改用
  element-plus：el-form + el-select + el-date-picker 提交，el-table 列本人预约。

  提交预约（医生、科室、就诊日期、时段、备注）并查看本人预约。四项必填在提交时
  命令式判断（FUNCTIONAL_SPEC 5.19），后端 422 才是最终依据。状态展示走
  `appointmentStatusLabel`，未知值回退「待确认」（AC-F-11）。所有后端调用都经
  F-1 的 `client`，本组件不认识传输层。
-->
<script setup>
import { onMounted, ref } from 'vue'

import { appointmentStatusLabel } from '../appointment/status.js'

const props = defineProps({
  client: { type: Object, required: true },
})
const emit = defineEmits(['error'])

const TIME_SLOTS = ['上午', '下午', '晚上']

const items = ref([])
const doctors = ref([])
const departments = ref([])
const loading = ref(false)
const loadError = ref(null)
const formError = ref(null)
const submitting = ref(false)
const emptyForm = () => ({
  doctor_id: '',
  department_id: '',
  visit_date: '',
  time_slot: TIME_SLOTS[0],
  remark: '',
})
const form = ref(emptyForm())

async function loadOptions() {
  try {
    const page = await props.client.doctors({ page: 1, page_size: 100 })
    doctors.value = page.items ?? []
    departments.value = await props.client.departments()
  } catch (failure) {
    doctors.value = []
    departments.value = []
    emit('error', failure)
  }
}

async function load() {
  loading.value = true
  try {
    items.value = await props.client.myAppointments()
    loadError.value = null
  } catch (failure) {
    items.value = []
    loadError.value = '预约列表加载失败'
    emit('error', failure)
  } finally {
    loading.value = false
  }
}

async function submit() {
  const { doctor_id, department_id, visit_date, time_slot, remark } = form.value
  if (
    !String(doctor_id).trim() ||
    !String(department_id).trim() ||
    !visit_date ||
    !time_slot
  ) {
    formError.value = '医生、科室、就诊日期、时段均为必填'
    return
  }
  submitting.value = true
  formError.value = null
  try {
    await props.client.createAppointment({
      doctor_id: Number(doctor_id),
      department_id: Number(department_id),
      visit_date,
      time_slot,
      remark: remark.trim() || undefined,
    })
    ElMessage.success('预约已提交')
    form.value = emptyForm()
    await load()
  } catch (failure) {
    emit('error', failure)
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  loadOptions()
  load()
})
</script>

<template>
  <section class="appointment">
    <el-card class="appointment__card" shadow="never">
      <template #header>
        <span class="card-title">预约挂号</span>
      </template>

      <el-form
        data-appointment-form
        :model="form"
        label-width="88px"
        class="appointment__form"
        @submit.prevent="submit"
      >
        <el-form-item label="医生">
          <el-select v-model="form.doctor_id" data-doctor-id placeholder="请选择医生" :teleported="false">
            <el-option
              v-for="doctor in doctors"
              :key="doctor.id"
              data-doctor-option
              :value="doctor.id"
              :label="doctor.real_name"
            >
              {{ doctor.real_name }}{{ doctor.department_name ? `（${doctor.department_name}）` : '' }}
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="科室">
          <el-select v-model="form.department_id" data-department-id placeholder="请选择科室" :teleported="false">
            <el-option
              v-for="department in departments"
              :key="department.id"
              data-department-option
              :value="department.id"
              :label="department.name"
            >
              {{ department.name }}
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="就诊日期">
          <span data-visit-date class="appointment__date">
            <el-date-picker
              v-model="form.visit_date"
              type="date"
              value-format="YYYY-MM-DD"
              placeholder="选择日期"
            />
          </span>
        </el-form-item>
        <el-form-item label="时段">
          <el-select v-model="form.time_slot" data-time-slot :teleported="false">
            <el-option v-for="slot in TIME_SLOTS" :key="slot" :value="slot" :label="slot" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" data-remark placeholder="备注（可选）" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" data-submit native-type="submit" :loading="submitting">
            提交预约
          </el-button>
        </el-form-item>
      </el-form>

      <p v-if="formError" data-form-error class="appointment__message appointment__message--error">
        {{ formError }}
      </p>
      <p v-if="loadError" data-error class="appointment__message appointment__message--error">
        {{ loadError }}
      </p>
      <el-table v-else v-loading="loading" :data="items" stripe class="appointment__table">
        <template #empty>
          <span data-empty>暂无预约</span>
        </template>
        <el-table-column prop="doctor_name" label="医生" min-width="110">
          <template #default="{ row }">
            <span data-cell-doctor>{{ row.doctor_name ?? '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="department_id" label="科室" min-width="90">
          <template #default="{ row }">
            <span data-cell-department>{{ row.department_id }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="visit_date" label="就诊日期" min-width="120">
          <template #default="{ row }">
            <span data-cell-date>{{ row.visit_date }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="time_slot" label="时段" min-width="90">
          <template #default="{ row }">
            <span data-cell-slot>{{ row.time_slot }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" min-width="100">
          <template #default="{ row }">
            <el-tag data-cell-status type="info" effect="plain">
              {{ appointmentStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="remark" label="备注" min-width="140">
          <template #default="{ row }">
            <span data-cell-remark>{{ row.remark ?? '-' }}</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </section>
</template>

<style scoped>
.appointment {
  padding: 0;
}

/*
  el-select uses :teleported="false" so its option anchors stay inside the
  component tree for the DOM tests; el-card's default overflow:hidden /
  .el-card__body overflow:auto would clip the dropdown, so this card opts out.
*/
.appointment__card,
.appointment__card :deep(.el-card__body) {
  overflow: visible;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
}

.appointment__form {
  max-width: 560px;
}

.appointment__message {
  margin: 8px 0;
  color: var(--el-text-color-secondary);
}

.appointment__message--error {
  color: var(--el-color-danger);
}
</style>
