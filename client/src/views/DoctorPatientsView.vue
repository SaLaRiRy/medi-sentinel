<!--
  医生工作台：患者列表 / 健康档案（TICKET-018，FUNCTIONAL_SPEC 2.7 / 5.19）。

  从「可选患者」（本人预约人 ∪ 已建档人）里挑患者建档，并可修改、删除本人名下的
  档案 —— 归属校验在后端硬执行，这里只呈现结果（SPEC.md 3.3：前端不复制业务规则
  作为唯一依据）。新建立档必须选择患者与档案类型，是提交时的命令式判断
  （FUNCTIONAL_SPEC 5.19），后端 422 才是最终依据。所有后端调用都经 F-1 `client`。
-->
<script setup>
import { onMounted, ref } from 'vue'

import { DEFAULT_RECORD_TYPE, RECORD_TYPES } from '../records/types.js'

const props = defineProps({
  client: { type: Object, required: true },
})
const emit = defineEmits(['error'])

const items = ref([])
const options = ref([])
const loadError = ref(null)
const formError = ref(null)
const submitting = ref(false)
const editingId = ref(null)
const emptyForm = () => ({
  user_id: '',
  record_type: DEFAULT_RECORD_TYPE,
  diagnosis: '',
  treatment: '',
  prescription: '',
  visit_date: '',
})
const form = ref(emptyForm())

function optional(value) {
  return value === '' || value === undefined || value === null ? undefined : value
}

async function load() {
  try {
    const [records, patientOptions] = await Promise.all([
      props.client.doctorRecords(),
      props.client.recordPatientOptions(),
    ])
    items.value = records
    options.value = patientOptions
    loadError.value = null
  } catch (failure) {
    items.value = []
    options.value = []
    loadError.value = '健康档案加载失败'
    emit('error', failure)
  }
}

function startEdit(item) {
  editingId.value = item.id
  formError.value = null
  form.value = {
    user_id: String(item.user_id),
    record_type: item.record_type ?? DEFAULT_RECORD_TYPE,
    diagnosis: item.diagnosis ?? '',
    treatment: item.treatment ?? '',
    prescription: item.prescription ?? '',
    visit_date: item.visit_date ?? '',
  }
}

function resetForm() {
  editingId.value = null
  form.value = emptyForm()
}

async function submit() {
  const { user_id, record_type } = form.value
  if (!editingId.value && !String(user_id).trim()) {
    formError.value = '患者与档案类型均为必填'
    return
  }
  if (!record_type) {
    formError.value = '患者与档案类型均为必填'
    return
  }
  const fields = {
    record_type,
    diagnosis: optional(form.value.diagnosis.trim()),
    treatment: optional(form.value.treatment.trim()),
    prescription: optional(form.value.prescription.trim()),
    visit_date: optional(form.value.visit_date),
  }
  submitting.value = true
  formError.value = null
  try {
    if (editingId.value) {
      await props.client.updateRecord(editingId.value, fields)
    } else {
      await props.client.createRecord({ user_id: Number(user_id), ...fields })
    }
    resetForm()
    await load()
  } catch (failure) {
    emit('error', failure)
  } finally {
    submitting.value = false
  }
}

async function remove(recordId) {
  try {
    await props.client.deleteRecord(recordId)
    if (editingId.value === recordId) resetForm()
    await load()
  } catch (failure) {
    emit('error', failure)
  }
}

onMounted(load)
</script>

<template>
  <section class="doctor-patients">
    <form data-record-form class="doctor-patients__form" @submit.prevent="submit">
      <select v-model="form.user_id" data-patient-select :disabled="Boolean(editingId)">
        <option value="">请选择患者</option>
        <option
          v-for="option in options"
          :key="option.id"
          :value="option.id"
          data-patient-option
        >
          {{ option.name }}
        </option>
      </select>
      <select v-model="form.record_type" data-record-type>
        <option v-for="type in RECORD_TYPES" :key="type" :value="type">{{ type }}</option>
      </select>
      <input v-model="form.diagnosis" data-diagnosis placeholder="诊断（可选）" />
      <input v-model="form.treatment" data-treatment placeholder="治疗方案（可选）" />
      <input v-model="form.prescription" data-prescription placeholder="处方（可选）" />
      <input v-model="form.visit_date" data-visit-date type="date" />
      <button type="submit" data-submit :disabled="submitting">
        {{ editingId ? '保存修改' : '建档' }}
      </button>
      <button v-if="editingId" type="button" data-cancel @click="resetForm">取消</button>
    </form>

    <p v-if="formError" data-form-error class="doctor-patients__error">{{ formError }}</p>
    <p v-if="loadError" data-error class="doctor-patients__error">{{ loadError }}</p>
    <p v-else-if="items.length === 0" data-empty class="doctor-patients__empty">
      暂无健康档案
    </p>

    <table v-else class="doctor-patients__table">
      <thead>
        <tr>
          <th>患者</th>
          <th>档案类型</th>
          <th>诊断</th>
          <th>就诊日期</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in items" :key="item.id" data-record-row>
          <td data-cell-patient>{{ item.user_name ?? '-' }}</td>
          <td data-cell-type>{{ item.record_type ?? '-' }}</td>
          <td data-cell-diagnosis>{{ item.diagnosis ?? '-' }}</td>
          <td data-cell-date>{{ item.visit_date ?? '-' }}</td>
          <td class="doctor-patients__actions">
            <button type="button" :data-edit="item.id" @click="startEdit(item)">
              编辑
            </button>
            <button type="button" :data-delete="item.id" @click="remove(item.id)">
              删除
            </button>
          </td>
        </tr>
      </tbody>
    </table>
  </section>
</template>
