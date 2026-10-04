<!--
  医生工作台：人工问诊抢单与回复（TICKET-019，SPEC.md 5.4「人工问诊」）。
  TICKET-029 改用 element-plus：el-table 列出可抢工单，行内 el-input + el-button
  回复并认领。

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
const loading = ref(false)
const loadError = ref(null)
const drafts = ref({})

function parts(item) {
  return decodeChiefComplaint(item.chief_complaint)
}

async function load() {
  loading.value = true
  try {
    items.value = await props.client.pendingConsults()
    loadError.value = null
  } catch (failure) {
    items.value = []
    loadError.value = '待分配工单加载失败'
    emit('error', failure)
  } finally {
    loading.value = false
  }
}

async function reply(item) {
  const content = (drafts.value[item.id] ?? '').trim()
  if (!content) return
  try {
    await props.client.replyConsult(item.id, { consult_id: item.id, content })
    ElMessage.success('已回复并认领')
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
    <el-card class="doctor-consults__card" shadow="never">
      <template #header>
        <div class="card-head">
          <span class="card-title">待处理工单</span>
          <el-tag size="small" type="info" effect="plain">{{ items.length }} 条</el-tag>
        </div>
      </template>

      <p v-if="loadError" data-error class="doctor-consults__message doctor-consults__message--error">
        {{ loadError }}
      </p>
      <el-table v-else v-loading="loading" :data="items" stripe class="doctor-consults__table">
        <template #empty>
          <span data-empty>暂无待处理工单</span>
        </template>
        <el-table-column label="患者" min-width="100">
          <template #default="{ row }">
            <span data-cell-patient>{{ row.user_name ?? '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="主诉标题" min-width="140">
          <template #default="{ row }">
            <span data-cell-title>{{ parts(row).title }}</span>
          </template>
        </el-table-column>
        <el-table-column label="详细描述" min-width="180">
          <template #default="{ row }">
            <span data-cell-body>{{ parts(row).body }}</span>
          </template>
        </el-table-column>
        <el-table-column label="回复" min-width="220">
          <template #default="{ row }">
            <el-input
              v-model="drafts[row.id]"
              data-reply-input
              placeholder="回复患者"
            />
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="130">
          <template #default="{ row }">
            <el-button type="primary" data-reply-submit size="small" @click="reply(row)">
              回复并认领
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </section>
</template>

<style scoped>
.doctor-consults {
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

.doctor-consults__message {
  margin: 8px 0;
  color: var(--el-text-color-secondary);
}

.doctor-consults__message--error {
  color: var(--el-color-danger);
}
</style>
