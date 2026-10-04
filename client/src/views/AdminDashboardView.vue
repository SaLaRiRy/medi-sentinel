<!--
  管理员运营概览（TICKET-022，FUNCTIONAL_SPEC 2.9 / SPEC.md 5.4）。
  TICKET-030 改用 element-plus：el-card 承载概览与四张分布面板，el-select 选择统计
  天数，数值用 el-tag 呈现，加载用 v-loading。

  六项总数 + 问诊趋势 / 用户增长（按天数查询）+ 预约科室分布 / 知识库类型分布。
  加载失败呈现空状态而非错误页；未知的知识库类型回退到既定默认展示（AC-F-11）。
  所有后端调用都经 F-1 的 `client`。
-->
<script setup>
import { onMounted, ref, watch } from 'vue'

import StatGrid from '../components/StatGrid.vue'
import { knowledgeTypeLabel } from '../stat/labels.js'

const props = defineProps({
  client: { type: Object, required: true },
})
const emit = defineEmits(['error'])

const TREND_DAYS = [7, 14, 30]

const days = ref(7)
const overview = ref(null)
const consultTrend = ref([])
const userGrowth = ref([])
const departments = ref([])
const knowledgeTypes = ref([])
const loadError = ref(null)
const loading = ref(false)

const OVERVIEW_FIELDS = [
  { key: 'user_count', label: '患者' },
  { key: 'doctor_count', label: '医生' },
  { key: 'session_count', label: 'AI 会话' },
  { key: 'appointment_count', label: '预约' },
  { key: 'knowledge_count', label: '知识文件' },
  { key: 'article_count', label: '文章' },
]

async function load() {
  loading.value = true
  const window = Number(days.value) || TREND_DAYS[0]
  try {
    const [summary, consult, growth, byDepartment, byKnowledgeType] =
      await Promise.all([
        props.client.statOverview(),
        props.client.consultTrend(window),
        props.client.userGrowth(window),
        props.client.appointmentsByDepartment(),
        props.client.knowledgeTypes(),
      ])
    overview.value = summary
    consultTrend.value = consult ?? []
    userGrowth.value = growth ?? []
    departments.value = byDepartment ?? []
    knowledgeTypes.value = byKnowledgeType ?? []
    loadError.value = null
  } catch (failure) {
    overview.value = null
    consultTrend.value = []
    userGrowth.value = []
    departments.value = []
    knowledgeTypes.value = []
    loadError.value = '数据概览加载失败'
    emit('error', failure)
  } finally {
    loading.value = false
  }
}

// el-select emits model updates, not a native change; a watcher keeps the
// "changing the day window reloads the trends" behaviour.
watch(days, () => load())

onMounted(load)
</script>

<template>
  <section v-loading="loading" class="admin-dashboard">
    <p v-if="loadError" data-error class="admin-dashboard__message admin-dashboard__message--error">
      {{ loadError }}
    </p>

    <template v-else>
      <el-card class="admin-dashboard__card" shadow="never">
        <template #header>
          <div class="card-head">
            <span class="card-title">运营概览</span>
            <el-select v-model="days" data-days class="admin-dashboard__days" :teleported="false">
              <el-option
                v-for="option in TREND_DAYS"
                :key="option"
                :value="option"
                :label="`最近 ${option} 天`"
              />
            </el-select>
          </div>
        </template>
        <StatGrid v-if="overview" :fields="OVERVIEW_FIELDS" :overview="overview" />
      </el-card>

      <div class="admin-dashboard__panels">
        <el-card data-consult-trend-panel shadow="never">
          <template #header><span class="card-title">问诊趋势</span></template>
          <p v-if="consultTrend.length === 0" data-empty>暂无数据</p>
          <ul v-else class="admin-dashboard__list">
            <li v-for="point in consultTrend" :key="point.date" data-consult-trend-row>
              <span data-cell-date>{{ point.date }}</span>
              <el-tag size="small" effect="plain" data-cell-value>{{ point.count }}</el-tag>
            </li>
          </ul>
        </el-card>

        <el-card data-user-growth-panel shadow="never">
          <template #header><span class="card-title">用户增长</span></template>
          <p v-if="userGrowth.length === 0" data-empty>暂无数据</p>
          <ul v-else class="admin-dashboard__list">
            <li v-for="point in userGrowth" :key="point.date" data-user-growth-row>
              <span data-cell-date>{{ point.date }}</span>
              <el-tag size="small" effect="plain" data-cell-value>{{ point.count }}</el-tag>
            </li>
          </ul>
        </el-card>

        <el-card data-department-panel shadow="never">
          <template #header><span class="card-title">预约科室分布</span></template>
          <p v-if="departments.length === 0" data-empty>暂无数据</p>
          <ul v-else class="admin-dashboard__list">
            <li v-for="item in departments" :key="item.name" data-department-row>
              <span data-cell-name>{{ item.name }}</span>
              <el-tag size="small" effect="plain" data-cell-value>{{ item.value }}</el-tag>
            </li>
          </ul>
        </el-card>

        <el-card data-knowledge-panel shadow="never">
          <template #header><span class="card-title">知识库类型分布</span></template>
          <p v-if="knowledgeTypes.length === 0" data-empty>暂无数据</p>
          <ul v-else class="admin-dashboard__list">
            <li v-for="item in knowledgeTypes" :key="item.name" data-knowledge-row>
              <span data-cell-name>{{ knowledgeTypeLabel(item.name) }}</span>
              <el-tag size="small" effect="plain" data-cell-value>{{ item.value }}</el-tag>
            </li>
          </ul>
        </el-card>
      </div>
    </template>
  </section>
</template>

<style scoped>
.admin-dashboard {
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

.admin-dashboard__days {
  width: 140px;
}

.admin-dashboard__panels {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}

.admin-dashboard__list {
  margin: 0;
  padding: 0;
  list-style: none;
}

.admin-dashboard__list li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 0;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.admin-dashboard__message {
  margin: 8px 0;
  color: var(--el-text-color-secondary);
}

.admin-dashboard__message--error {
  color: var(--el-color-danger);
}
</style>
