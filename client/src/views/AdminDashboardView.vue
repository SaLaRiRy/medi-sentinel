<!--
  管理员运营概览（TICKET-022，FUNCTIONAL_SPEC 2.9 / SPEC.md 5.4）。
  视觉重做（第二阶段，图2）：顶部统计卡片 + 两列图表卡片网格
  （咨询趋势折线 / 预约科室分布环形 / 用户增长柱状 / 知识库类型环形）。

  六项总数 + 问诊趋势 / 用户增长（按天数查询）+ 预约科室分布 / 知识库类型分布。
  加载失败呈现空状态而非错误页；未知的知识库类型回退到既定默认展示（AC-F-11）。
  所有后端调用都经 F-1 的 `client`。`data-*` 锚点原样保留（图表附无障碍数据表）。
-->
<script setup>
import { computed, onMounted, ref, watch } from 'vue'

import BarChart from '../components/charts/BarChart.vue'
import DonutChart from '../components/charts/DonutChart.vue'
import LineChart from '../components/charts/LineChart.vue'
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
  { key: 'user_count', label: '患者', accent: '#6366f1' },
  { key: 'doctor_count', label: '医生', accent: '#14b8a6' },
  { key: 'session_count', label: 'AI 会话', accent: '#8b5cf6' },
  { key: 'appointment_count', label: '预约', accent: '#3b82f6' },
  { key: 'knowledge_count', label: '知识文件', accent: '#f59e0b' },
  { key: 'article_count', label: '文章', accent: '#e05a8a' },
]

const DEPARTMENT_PALETTE = ['#6366f1', '#22a06b', '#f4b740', '#e05a8a', '#3b82f6', '#8b5cf6']
const KNOWLEDGE_PALETTE = ['#6366f1', '#22a06b', '#f4b740', '#e05a8a', '#3b82f6', '#14b8a6']

const trendPoints = computed(() =>
  consultTrend.value.map((point) => ({ label: point.date, value: point.count }))
)
const growthPoints = computed(() =>
  userGrowth.value.map((point) => ({ label: point.date, value: point.count }))
)

async function load() {
  loading.value = true
  const window = Number(days.value) || TREND_DAYS[0]
  try {
    const [summary, consult, growth, byDepartment, byKnowledgeType] = await Promise.all([
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
      <header class="admin-dashboard__head">
        <h1 class="admin-dashboard__title">数据概览</h1>
        <el-select v-model="days" data-days class="admin-dashboard__days" :teleported="false">
          <el-option
            v-for="option in TREND_DAYS"
            :key="option"
            :value="option"
            :label="`最近 ${option} 天`"
          />
        </el-select>
      </header>

      <StatGrid v-if="overview" :fields="OVERVIEW_FIELDS" :overview="overview" />

      <div class="admin-dashboard__grid">
        <el-card data-consult-trend-panel class="admin-dashboard__panel" shadow="never">
          <template #header>
            <span class="card-title">咨询趋势</span>
          </template>
          <p v-if="consultTrend.length === 0" data-empty class="admin-dashboard__empty">暂无数据</p>
          <template v-else>
            <LineChart :data="trendPoints" color="#6366f1" />
            <ul class="admin-dashboard__sr">
              <li v-for="point in consultTrend" :key="point.date" data-consult-trend-row>
                <span data-cell-date>{{ point.date }}</span>
                <span data-cell-value>{{ point.count }}</span>
              </li>
            </ul>
          </template>
        </el-card>

        <el-card data-department-panel class="admin-dashboard__panel" shadow="never">
          <template #header>
            <span class="card-title">预约科室分布</span>
          </template>
          <p v-if="departments.length === 0" data-empty class="admin-dashboard__empty">暂无数据</p>
          <template v-else>
            <DonutChart :data="departments" :palette="DEPARTMENT_PALETTE" />
            <ul class="admin-dashboard__legend">
              <li v-for="(item, index) in departments" :key="item.name" data-department-row>
                <span
                  class="admin-dashboard__dot"
                  :style="{ background: DEPARTMENT_PALETTE[index % DEPARTMENT_PALETTE.length] }"
                />
                <span data-cell-name class="admin-dashboard__legend-name">{{ item.name }}</span>
                <span data-cell-value class="admin-dashboard__legend-value">{{ item.value }}</span>
              </li>
            </ul>
          </template>
        </el-card>

        <el-card data-user-growth-panel class="admin-dashboard__panel" shadow="never">
          <template #header>
            <span class="card-title">用户增长</span>
          </template>
          <p v-if="userGrowth.length === 0" data-empty class="admin-dashboard__empty">暂无数据</p>
          <template v-else>
            <BarChart :data="growthPoints" color="#8b5cf6" />
            <ul class="admin-dashboard__sr">
              <li v-for="point in userGrowth" :key="point.date" data-user-growth-row>
                <span data-cell-date>{{ point.date }}</span>
                <span data-cell-value>{{ point.count }}</span>
              </li>
            </ul>
          </template>
        </el-card>

        <el-card data-knowledge-panel class="admin-dashboard__panel" shadow="never">
          <template #header>
            <span class="card-title">知识库类型</span>
          </template>
          <p v-if="knowledgeTypes.length === 0" data-empty class="admin-dashboard__empty">
            暂无数据
          </p>
          <template v-else>
            <DonutChart :data="knowledgeTypes" :palette="KNOWLEDGE_PALETTE" />
            <ul class="admin-dashboard__legend">
              <li v-for="(item, index) in knowledgeTypes" :key="item.name" data-knowledge-row>
                <span
                  class="admin-dashboard__dot"
                  :style="{ background: KNOWLEDGE_PALETTE[index % KNOWLEDGE_PALETTE.length] }"
                />
                <span data-cell-name class="admin-dashboard__legend-name">
                  {{ knowledgeTypeLabel(item.name) }}
                </span>
                <span data-cell-value class="admin-dashboard__legend-value">{{ item.value }}</span>
              </li>
            </ul>
          </template>
        </el-card>
      </div>
    </template>
  </section>
</template>

<style scoped>
.admin-dashboard {
  display: flex;
  flex-direction: column;
  gap: var(--ms-space-5);
}

.admin-dashboard__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ms-space-4);
}

.admin-dashboard__title {
  font-size: var(--ms-font-lg);
  font-weight: 700;
}

.admin-dashboard__days {
  width: 150px;
}

.admin-dashboard__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  /* 两行等高：图表卡片不论内容多少都撑满各自的网格行。 */
  grid-auto-rows: 1fr;
  gap: var(--ms-space-5);
}

@media (max-width: 1100px) {
  .admin-dashboard__grid {
    grid-template-columns: 1fr;
  }
}

.admin-dashboard__panel {
  border: 1px solid var(--ms-border);
  border-radius: var(--ms-radius-lg);
  box-shadow: var(--ms-shadow);
}

.card-title {
  font-size: var(--ms-font-md);
  font-weight: 600;
}

.admin-dashboard__legend {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: var(--ms-space-3);
}

.admin-dashboard__legend li {
  display: flex;
  align-items: center;
  gap: var(--ms-space-2);
  font-size: var(--ms-font-sm);
}

.admin-dashboard__dot {
  width: 10px;
  height: 10px;
  flex: 0 0 10px;
  border-radius: 3px;
}

.admin-dashboard__legend-name {
  color: var(--ms-text-secondary);
}

.admin-dashboard__legend-value {
  margin-left: auto;
  color: var(--ms-text);
  font-weight: 600;
}

.admin-dashboard__empty {
  color: var(--ms-text-muted);
  font-size: var(--ms-font-sm);
}

.admin-dashboard__message {
  margin: 8px 0;
  color: var(--ms-text-secondary);
}

.admin-dashboard__message--error {
  color: var(--el-color-danger);
}

/* 图表的无障碍数据表：保留 data-* 锚点，视觉上不重复展示。 */
.admin-dashboard__sr {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
</style>
