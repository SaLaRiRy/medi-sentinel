<!--
  患者侧预约挂号（TICKET-017，FUNCTIONAL_SPEC 2.7 / 5.19 / 5.20）。

  提交预约（医生、科室、就诊日期、时段、备注）并查看本人预约。四项必填在提交时
  命令式判断（FUNCTIONAL_SPEC 5.19），后端 422 才是最终依据。状态展示走
  `appointmentStatusLabel`，未知值回退「待确认」（AC-F-11）。所有后端调用都经
  F-1 的 `client`，本组件不认识传输层。

  科室主数据（下拉选项）由 TICKET-020 提供，本票先以编号录入。
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

async function load() {
  try {
    items.value = await props.client.myAppointments()
    loadError.value = null
  } catch (failure) {
    items.value = []
    loadError.value = '预约列表加载失败'
    emit('error', failure)
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
    form.value = emptyForm()
    await load()
  } catch (failure) {
    emit('error', failure)
  } finally {
    submitting.value = false
  }
}

onMounted(load)
</script>

<template>
  <section class="appointment">
    <form data-appointment-form class="appointment__form" @submit.prevent="submit">
      <input v-model="form.doctor_id" data-doctor-id placeholder="医生编号" />
      <input v-model="form.department_id" data-department-id placeholder="科室编号" />
      <input v-model="form.visit_date" data-visit-date type="date" />
      <select v-model="form.time_slot" data-time-slot>
        <option v-for="slot in TIME_SLOTS" :key="slot" :value="slot">{{ slot }}</option>
      </select>
      <input v-model="form.remark" data-remark placeholder="备注（可选）" />
      <button type="submit" data-submit :disabled="submitting">提交预约</button>
    </form>

    <p v-if="formError" data-form-error class="appointment__error">{{ formError }}</p>
    <p v-if="loadError" data-error class="appointment__error">{{ loadError }}</p>
    <p v-else-if="items.length === 0" data-empty class="appointment__empty">
      暂无预约
    </p>

    <table v-else class="appointment__table">
      <thead>
        <tr>
          <th>医生</th>
          <th>科室编号</th>
          <th>就诊日期</th>
          <th>时段</th>
          <th>状态</th>
          <th>备注</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in items" :key="item.id" data-appointment-row>
          <td data-cell-doctor>{{ item.doctor_name ?? '-' }}</td>
          <td data-cell-department>{{ item.department_id }}</td>
          <td data-cell-date>{{ item.visit_date }}</td>
          <td data-cell-slot>{{ item.time_slot }}</td>
          <td data-cell-status>{{ appointmentStatusLabel(item.status) }}</td>
          <td data-cell-remark>{{ item.remark ?? '-' }}</td>
        </tr>
      </tbody>
    </table>
  </section>
</template>
