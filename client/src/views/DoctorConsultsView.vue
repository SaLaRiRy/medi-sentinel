<!--
  医生工作台：人工问诊抢单与回复（TICKET-019，SPEC.md 5.4「人工问诊」）。

  列出「指派给我或尚未指派且状态为 0」的工单，先到先得：首位提交回复的医生被
  写入为负责医生，状态无条件置 1。已被其他医生认领时后端返回 409，本组件只呈现
  结果并上报（SPEC.md 3.3：前端不复制业务规则作为唯一依据）。主诉按第一个全角
  冒号拆回标题与正文（AC-F-15）。所有后端调用都经 F-1 的 `client`。
-->
<script setup>
import { onMounted, ref } from 'vue'

import { decodeChiefComplaint } from '../consult/complaint.js'

const props = defineProps({
  client: { type: Object, required: true },
})
const emit = defineEmits(['error'])

const items = ref([])
const loadError = ref(null)
const drafts = ref({})

function parts(item) {
  return decodeChiefComplaint(item.chief_complaint)
}

async function load() {
  try {
    items.value = await props.client.pendingConsults()
    loadError.value = null
  } catch (failure) {
    items.value = []
    loadError.value = '待分配工单加载失败'
    emit('error', failure)
  }
}

async function reply(item) {
  const content = (drafts.value[item.id] ?? '').trim()
  if (!content) return
  try {
    await props.client.replyConsult(item.id, { consult_id: item.id, content })
    drafts.value[item.id] = ''
    await load()
  } catch (failure) {
    emit('error', failure)
  }
}

onMounted(load)
</script>

<template>
  <section class="doctor-consults">
    <p v-if="loadError" data-error class="doctor-consults__error">{{ loadError }}</p>
    <p v-else-if="items.length === 0" data-empty class="doctor-consults__empty">
      暂无待处理工单
    </p>

    <ul v-else class="doctor-consults__list">
      <li v-for="item in items" :key="item.id" data-consult-row>
        <h3 data-cell-title>{{ parts(item).title }}</h3>
        <p data-cell-body>{{ parts(item).body }}</p>
        <p data-cell-patient>{{ item.user_name ?? '-' }}</p>
        <input
          v-model="drafts[item.id]"
          data-reply-input
          placeholder="回复患者"
        />
        <button type="button" data-reply-submit @click="reply(item)">回复并认领</button>
      </li>
    </ul>
  </section>
</template>
