<!--
  患者门户首页：个人概览（TICKET-022）与已发布的系统公告（TICKET-021）。
  TICKET-029 改用 element-plus：el-card 承载概览与公告，公告列表用 el-table。

  个人概览展示本人的人工问诊、预约、健康档案、AI 会话四项计数（FUNCTIONAL_SPEC 2.9）。
  公告公开列表**不分页**，一次返回全部已发布公告；点标题看详情，公告详情加载失败
  或记录不存在时回到首页（FUNCTIONAL_SPEC 5.21）。列表加载失败呈现空态而非错误页。
  后端调用都经 F-1 的 `client`。
-->
<script setup>
import { onMounted, ref } from 'vue'

import StatGrid from '../components/StatGrid.vue'

const props = defineProps({
  client: { type: Object, required: true },
})
const emit = defineEmits(['error'])

const OVERVIEW_FIELDS = [
  { key: 'consult_count', label: '人工问诊' },
  { key: 'appointment_count', label: '预约挂号' },
  { key: 'record_count', label: '健康档案' },
  { key: 'session_count', label: 'AI 会话' },
]

const overview = ref(null)
const items = ref([])
const loadError = ref(null)
const detail = ref(null)

async function loadOverview() {
  try {
    overview.value = await props.client.userOverview()
  } catch (failure) {
    overview.value = null
    emit('error', failure)
  }
}

async function load() {
  try {
    items.value = await props.client.notices()
    loadError.value = null
  } catch (failure) {
    items.value = []
    loadError.value = '公告加载失败'
    emit('error', failure)
  }
}

async function open(noticeId) {
  try {
    detail.value = await props.client.notice(noticeId)
  } catch (failure) {
    detail.value = null
    emit('error', failure)
  }
}

function back() {
  detail.value = null
}

onMounted(() => {
  load()
  loadOverview()
})
</script>

<template>
  <section class="portal-home">
    <el-card data-user-overview class="portal-home__card" shadow="never">
      <template #header>
        <span class="card-title">个人概览</span>
      </template>
      <StatGrid :fields="OVERVIEW_FIELDS" :overview="overview" />
    </el-card>

    <el-card v-if="detail" data-notice-detail class="portal-home__card" shadow="never">
      <template #header>
        <span class="card-title" data-detail-title>{{ detail.title }}</span>
      </template>
      <p data-detail-content class="portal-home__detail">{{ detail.content }}</p>
      <el-button data-back @click="back">返回首页</el-button>
    </el-card>

    <el-card v-else class="portal-home__card" shadow="never">
      <template #header>
        <span class="card-title">系统公告</span>
      </template>

      <p v-if="loadError" data-error class="portal-home__message portal-home__message--error">
        {{ loadError }}
      </p>
      <el-table v-else :data="items" class="portal-home__notices">
        <template #empty>
          <span data-empty>暂无公告</span>
        </template>
        <el-table-column label="标题" min-width="220">
          <template #default="{ row }">
            <span data-cell-title>{{ row.title }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button size="small" :data-open="row.id" @click="open(row.id)">查看</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </section>
</template>

<style scoped>
.portal-home {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
}

.portal-home__detail {
  white-space: pre-wrap;
  line-height: 1.7;
}

.portal-home__message {
  margin: 8px 0;
  color: var(--el-text-color-secondary);
}

.portal-home__message--error {
  color: var(--el-color-danger);
}
</style>
