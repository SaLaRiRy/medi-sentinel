<!--
  患者侧人工问诊（TICKET-019，SPEC.md 5.4「人工问诊」/ FUNCTIONAL_SPEC 2.6）。
  TICKET-029 改用 element-plus：el-form/el-input 提交，el-table 列本人工单。

  提交工单时把「标题 + 正文」编码成一个主诉字段（全角冒号，AC-F-15），可指定
  医生，也可留空成为「待分配」；下方按时间倒序列出本人全部工单及医生回复。所有
  后端调用都经 F-1 的 `client`。列表加载失败呈现空态并上报（AC-F-12）。
-->
<script setup>
import { onMounted, ref } from 'vue'

import { decodeChiefComplaint, encodeChiefComplaint } from '../consult/complaint.js'
import { consultStatusLabel } from '../consult/status.js'

const props = defineProps({
  client: { type: Object, required: true },
})
const emit = defineEmits(['error'])

const items = ref([])
const loading = ref(false)
const loadError = ref(null)
const formError = ref(null)
const submitting = ref(false)
const emptyForm = () => ({ title: '', body: '', doctor_id: '' })
const form = ref(emptyForm())

function parts(item) {
  return decodeChiefComplaint(item.chief_complaint)
}

async function load() {
  loading.value = true
  try {
    items.value = await props.client.myConsults()
    loadError.value = null
  } catch (failure) {
    items.value = []
    loadError.value = '问诊工单加载失败'
    emit('error', failure)
  } finally {
    loading.value = false
  }
}

async function submit() {
  const title = form.value.title.trim()
  if (!title) {
    formError.value = '主诉标题为必填'
    return
  }
  submitting.value = true
  formError.value = null
  try {
    const payload = {
      chief_complaint: encodeChiefComplaint(title, form.value.body.trim()),
    }
    if (form.value.doctor_id !== '') payload.doctor_id = Number(form.value.doctor_id)
    await props.client.createConsult(payload)
    ElMessage.success('问诊已提交')
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
  <section class="consult">
    <el-card class="consult__card" shadow="never">
      <template #header>
        <span class="card-title">发起人工问诊</span>
      </template>

      <el-form
        data-consult-form
        :model="form"
        label-width="88px"
        class="consult__form"
        @submit.prevent="submit"
      >
        <el-form-item label="主诉标题">
          <el-input v-model="form.title" data-complaint-title placeholder="主诉标题" />
        </el-form-item>
        <el-form-item label="详细描述">
          <el-input
            v-model="form.body"
            data-complaint-body
            type="textarea"
            :rows="3"
            placeholder="详细描述（可选）"
          />
        </el-form-item>
        <el-form-item label="指定医生">
          <el-input
            v-model="form.doctor_id"
            data-doctor-id
            placeholder="指定医生编号（留空则待分配）"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" data-submit native-type="submit" :loading="submitting">
            提交问诊
          </el-button>
        </el-form-item>
      </el-form>

      <p v-if="formError" data-form-error class="consult__message consult__message--error">
        {{ formError }}
      </p>
    </el-card>

    <el-card class="consult__card" shadow="never">
      <template #header>
        <div class="card-head">
          <span class="card-title">我的工单</span>
          <el-tag size="small" type="info" effect="plain">{{ items.length }} 条</el-tag>
        </div>
      </template>

      <p v-if="loadError" data-error class="consult__message consult__message--error">
        {{ loadError }}
      </p>
      <el-table v-else v-loading="loading" :data="items" stripe class="consult__table">
        <template #empty>
          <span data-empty>暂无问诊工单</span>
        </template>
        <el-table-column label="主诉标题" min-width="140">
          <template #default="{ row }">
            <span data-cell-title>{{ parts(row).title }}</span>
          </template>
        </el-table-column>
        <el-table-column label="详细描述" min-width="200">
          <template #default="{ row }">
            <span data-cell-body>{{ parts(row).body }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" min-width="100">
          <template #default="{ row }">
            <el-tag data-cell-status type="info" effect="plain">
              {{ consultStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="医生" min-width="110">
          <template #default="{ row }">
            <span data-cell-doctor>{{ row.doctor_name ?? '待分配' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="回复" min-width="200">
          <template #default="{ row }">
            <span v-for="reply in row.replies" :key="reply.id" data-reply class="consult__reply">
              {{ reply.doctor_name ?? '医生' }}：{{ reply.content }}
            </span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </section>
</template>

<style scoped>
.consult {
  display: flex;
  flex-direction: column;
  gap: 16px;
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

.consult__form {
  max-width: 640px;
}

.consult__message {
  margin: 8px 0;
  color: var(--el-text-color-secondary);
}

.consult__message--error {
  color: var(--el-color-danger);
}

.consult__reply {
  display: block;
}
</style>
