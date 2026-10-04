<!--
  医生工作台：患者列表 / 健康档案（TICKET-018，FUNCTIONAL_SPEC 2.7 / 5.19）。
  TICKET-029 改用 element-plus：el-form/el-select/el-date-picker/el-input 录入，
  el-table 列档案，el-button 编辑/删除。

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
const loading = ref(false)
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
  loading.value = true
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
  } finally {
    loading.value = false
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
      ElMessage.success('档案已更新')
    } else {
      await props.client.createRecord({ user_id: Number(user_id), ...fields })
      ElMessage.success('档案已建立')
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
    ElMessage.success('档案已删除')
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
    <el-card class="doctor-patients__card doctor-patients__card--form" shadow="never">
      <template #header>
        <span class="card-title">{{ editingId ? '修改健康档案' : '建立健康档案' }}</span>
      </template>

      <el-form
        data-record-form
        :model="form"
        label-width="88px"
        class="doctor-patients__form"
        @submit.prevent="submit"
      >
        <el-form-item label="患者">
          <el-select
            v-model="form.user_id"
            data-patient-select
            placeholder="请选择患者"
            :disabled="Boolean(editingId)"
            :teleported="false"
          >
            <el-option
              v-for="option in options"
              :key="option.id"
              data-patient-option
              :value="option.id"
              :label="option.name"
            >
              {{ option.name }}
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="档案类型">
          <el-select v-model="form.record_type" data-record-type :teleported="false">
            <el-option v-for="type in RECORD_TYPES" :key="type" :value="type" :label="type" />
          </el-select>
        </el-form-item>
        <el-form-item label="诊断">
          <el-input v-model="form.diagnosis" data-diagnosis placeholder="诊断（可选）" />
        </el-form-item>
        <el-form-item label="治疗方案">
          <el-input v-model="form.treatment" data-treatment placeholder="治疗方案（可选）" />
        </el-form-item>
        <el-form-item label="处方">
          <el-input v-model="form.prescription" data-prescription placeholder="处方（可选）" />
        </el-form-item>
        <el-form-item label="就诊日期">
          <span data-visit-date class="doctor-patients__date">
            <el-date-picker
              v-model="form.visit_date"
              type="date"
              value-format="YYYY-MM-DD"
              placeholder="选择日期"
            />
          </span>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" data-submit native-type="submit" :loading="submitting">
            {{ editingId ? '保存修改' : '建档' }}
          </el-button>
          <el-button v-if="editingId" data-cancel @click="resetForm">取消</el-button>
        </el-form-item>
      </el-form>

      <p v-if="formError" data-form-error class="doctor-patients__message doctor-patients__message--error">
        {{ formError }}
      </p>
    </el-card>

    <el-card class="doctor-patients__card" shadow="never">
      <template #header>
        <div class="card-head">
          <span class="card-title">本人名下档案</span>
          <el-tag size="small" type="info" effect="plain">{{ items.length }} 条</el-tag>
        </div>
      </template>

      <p v-if="loadError" data-error class="doctor-patients__message doctor-patients__message--error">
        {{ loadError }}
      </p>
      <el-table v-else v-loading="loading" :data="items" stripe class="doctor-patients__table">
        <template #empty>
          <span data-empty>暂无健康档案</span>
        </template>
        <el-table-column prop="user_name" label="患者" min-width="110">
          <template #default="{ row }">
            <span data-cell-patient>{{ row.user_name ?? '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="record_type" label="档案类型" min-width="110">
          <template #default="{ row }">
            <span data-cell-type>{{ row.record_type ?? '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="diagnosis" label="诊断" min-width="140">
          <template #default="{ row }">
            <span data-cell-diagnosis>{{ row.diagnosis ?? '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="visit_date" label="就诊日期" min-width="120">
          <template #default="{ row }">
            <span data-cell-date>{{ row.visit_date ?? '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="160">
          <template #default="{ row }">
            <el-button size="small" :data-edit="row.id" @click="startEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" plain :data-delete="row.id" @click="remove(row.id)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </section>
</template>

<style scoped>
.doctor-patients {
  display: flex;
  flex-direction: column;
  gap: 16px;
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

.doctor-patients__form {
  max-width: 560px;
}

/* Keep the non-teleported el-select dropdown from being clipped by el-card. */
.doctor-patients__card--form,
.doctor-patients__card--form :deep(.el-card__body) {
  overflow: visible;
}

.doctor-patients__message {
  margin: 8px 0;
  color: var(--el-text-color-secondary);
}

.doctor-patients__message--error {
  color: var(--el-color-danger);
}
</style>
