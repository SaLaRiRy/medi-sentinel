<!--
  患者侧人工问诊（TICKET-019，SPEC.md 5.4「人工问诊」/ FUNCTIONAL_SPEC 2.6）。

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
const loadError = ref(null)
const formError = ref(null)
const submitting = ref(false)
const emptyForm = () => ({ title: '', body: '', doctor_id: '' })
const form = ref(emptyForm())

function parts(item) {
  return decodeChiefComplaint(item.chief_complaint)
}

async function load() {
  try {
    items.value = await props.client.myConsults()
    loadError.value = null
  } catch (failure) {
    items.value = []
    loadError.value = '问诊工单加载失败'
    emit('error', failure)
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
    <form data-consult-form class="consult__form" @submit.prevent="submit">
      <input v-model="form.title" data-complaint-title placeholder="主诉标题" />
      <textarea v-model="form.body" data-complaint-body placeholder="详细描述（可选）" />
      <input v-model="form.doctor_id" data-doctor-id placeholder="指定医生编号（留空则待分配）" />
      <button type="submit" data-submit :disabled="submitting">提交问诊</button>
    </form>

    <p v-if="formError" data-form-error class="consult__error">{{ formError }}</p>
    <p v-if="loadError" data-error class="consult__error">{{ loadError }}</p>
    <p v-else-if="items.length === 0" data-empty class="consult__empty">暂无问诊工单</p>

    <ul v-else class="consult__list">
      <li v-for="item in items" :key="item.id" data-consult-row>
        <h3 data-cell-title>{{ parts(item).title }}</h3>
        <p data-cell-body>{{ parts(item).body }}</p>
        <p data-cell-status>{{ consultStatusLabel(item.status) }}</p>
        <p data-cell-doctor>{{ item.doctor_name ?? '待分配' }}</p>
        <ul class="consult__replies">
          <li v-for="reply in item.replies" :key="reply.id" data-reply>
            {{ reply.doctor_name ?? '医生' }}：{{ reply.content }}
          </li>
        </ul>
      </li>
    </ul>
  </section>
</template>
