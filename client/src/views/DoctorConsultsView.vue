<!--
  医生工作台：人工问诊抢单与回复（TICKET-019，SPEC.md 5.4「人工问诊」）。
  TICKET-029 改用 element-plus：el-table 列出可抢工单，行内 el-input + el-button
  回复并认领。

  列出「指派给我或尚未指派且状态为 0」的工单，先到先得：首位提交回复的医生被
  写入为负责医生，状态无条件置 1。已被其他医生认领时后端返回 409，本组件只呈现
  结果并上报（SPEC.md 3.3：前端不复制业务规则作为唯一依据）。主诉按第一个全角
  冒号拆回标题与正文（AC-F-15）。所有后端调用都经 F-1 的 `client`。

  TICKET-AC-05：每行可以打开「AI 上下文」——工单关联的 AI 会话的候选疾病、引用
  与原始主诉。归属校验在后端（未认领工单对全体医生可见，已被他人认领的不可见），
  这里只呈现结果。
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

const contextVisible = ref(false)
const contextLoading = ref(false)
const context = ref(null)
const contextError = ref(null)

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

async function openContext(item) {
  contextVisible.value = true
  contextLoading.value = true
  context.value = null
  contextError.value = null
  try {
    context.value = await props.client.consultAiContext(item.id)
  } catch (failure) {
    contextError.value = 'AI 上下文加载失败'
    emit('error', failure)
  } finally {
    contextLoading.value = false
  }
}

function hasContext(value) {
  return Boolean(value && (value.summary || value.graph.length || value.references.length))
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
            <div class="doctor-consults__actions">
              <el-button type="primary" data-reply-submit size="small" @click="reply(row)">
                回复并认领
              </el-button>
              <el-button data-ai-context size="small" plain @click="openContext(row)">
                AI 上下文
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="contextVisible" title="AI 问诊上下文" width="680px">
      <p v-if="contextError" data-context-error class="doctor-consults__message doctor-consults__message--error">
        {{ contextError }}
      </p>
      <div v-else-if="context" class="doctor-consults__context">
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="主诉">
            {{ context.chief_complaint }}
          </el-descriptions-item>
          <el-descriptions-item label="关联会话">
            {{ context.session_id ?? '未关联 AI 会话' }}
          </el-descriptions-item>
        </el-descriptions>

        <template v-if="context.summary">
          <p class="doctor-consults__label">AI 建议</p>
          <p data-context-summary class="doctor-consults__summary">{{ context.summary }}</p>
        </template>

        <template v-if="context.graph.length">
          <p class="doctor-consults__label">候选疾病</p>
          <el-table :data="context.graph" size="small" stripe>
            <el-table-column prop="disease" label="疾病" min-width="120" />
            <el-table-column label="覆盖率" min-width="90">
              <template #default="{ row }">
                {{ Number(row.coverage ?? 0).toFixed(2) }}
              </template>
            </el-table-column>
            <el-table-column label="科室" min-width="100">
              <template #default="{ row }">{{ row.department ?? '-' }}</template>
            </el-table-column>
            <el-table-column label="依据症状" min-width="160">
              <template #default="{ row }">
                {{ (row.matched_symptoms ?? []).join('、') }}
              </template>
            </el-table-column>
          </el-table>
        </template>

        <template v-if="context.references.length">
          <p class="doctor-consults__label">引用来源</p>
          <ul class="doctor-consults__references">
            <li v-for="reference in context.references" :key="reference.index" data-context-reference>
              [{{ reference.index }}] {{ reference.file_name }}
            </li>
          </ul>
        </template>

        <p v-if="!hasContext(context)" data-context-empty class="doctor-consults__message">
          这次工单没有关联 AI 问诊内容。
        </p>
      </div>
      <div v-else v-loading="contextLoading" class="doctor-consults__loading" />
    </el-dialog>
  </section>
</template>

<style scoped>
.doctor-consults {
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

.doctor-consults__message {
  margin: 8px 0;
  color: var(--el-text-color-secondary);
}

.doctor-consults__message--error {
  color: var(--el-color-danger);
}

.doctor-consults__actions {
  display: flex;
  gap: 8px;
}

.doctor-consults__context {
  display: flex;
  flex-direction: column;
}

.doctor-consults__label {
  margin: 16px 0 8px;
  font-weight: 600;
}

.doctor-consults__summary {
  margin: 0;
  padding: 12px;
  border-radius: 6px;
  background: var(--el-fill-color-light);
  white-space: pre-wrap;
}

.doctor-consults__references {
  margin: 0;
  padding-left: 20px;
  color: var(--el-text-color-regular);
}

.doctor-consults__loading {
  min-height: 96px;
}
</style>
