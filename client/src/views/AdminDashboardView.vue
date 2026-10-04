<!--
  管理员运营概览（TICKET-022，FUNCTIONAL_SPEC 2.9 / SPEC.md 5.4）。

  六项总数 + 问诊趋势 / 用户增长（按天数查询）+ 预约科室分布 / 知识库类型分布。
  加载失败呈现空状态而非错误页；未知的知识库类型回退到既定默认展示（AC-F-11）。
  所有后端调用都经 F-1 的 `client`。
-->
<script setup>
import { onMounted, ref } from 'vue'

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

const OVERVIEW_FIELDS = [
  { key: 'user_count', label: '患者' },
  { key: 'doctor_count', label: '医生' },
  { key: 'session_count', label: 'AI 会话' },
  { key: 'appointment_count', label: '预约' },
  { key: 'knowledge_count', label: '知识文件' },
  { key: 'article_count', label: '文章' },
]

async function load() {
  try {
    const [summary, consult, growth, byDepartment, byKnowledgeType] =
      await Promise.all([
        props.client.statOverview(),
        props.client.consultTrend(days.value),
        props.client.userGrowth(days.value),
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
  }
}

onMounted(load)
</script>

<template>
  <section class="admin-dashboard">
    <p v-if="loadError" data-error class="admin-dashboard__error">{{ loadError }}</p>

    <template v-else>
      <h2>运营概览</h2>
      <StatGrid v-if="overview" :fields="OVERVIEW_FIELDS" :overview="overview" />

      <label class="admin-dashboard__days">
        统计天数
        <select v-model.number="days" data-days @change="load">
          <option v-for="option in TREND_DAYS" :key="option" :value="option">
            最近 {{ option }} 天
          </option>
        </select>
      </label>

      <div class="admin-dashboard__panels">
        <section data-consult-trend-panel>
          <h3>问诊趋势</h3>
          <p v-if="consultTrend.length === 0" data-empty>暂无数据</p>
          <ul v-else>
            <li v-for="point in consultTrend" :key="point.date" data-consult-trend-row>
              <span data-cell-date>{{ point.date }}</span>
              <span data-cell-value>{{ point.count }}</span>
            </li>
          </ul>
        </section>

        <section data-user-growth-panel>
          <h3>用户增长</h3>
          <p v-if="userGrowth.length === 0" data-empty>暂无数据</p>
          <ul v-else>
            <li v-for="point in userGrowth" :key="point.date" data-user-growth-row>
              <span data-cell-date>{{ point.date }}</span>
              <span data-cell-value>{{ point.count }}</span>
            </li>
          </ul>
        </section>

        <section data-department-panel>
          <h3>预约科室分布</h3>
          <p v-if="departments.length === 0" data-empty>暂无数据</p>
          <ul v-else>
            <li v-for="item in departments" :key="item.name" data-department-row>
              <span data-cell-name>{{ item.name }}</span>
              <span data-cell-value>{{ item.value }}</span>
            </li>
          </ul>
        </section>

        <section data-knowledge-panel>
          <h3>知识库类型分布</h3>
          <p v-if="knowledgeTypes.length === 0" data-empty>暂无数据</p>
          <ul v-else>
            <li v-for="item in knowledgeTypes" :key="item.name" data-knowledge-row>
              <span data-cell-name>{{ knowledgeTypeLabel(item.name) }}</span>
              <span data-cell-value>{{ item.value }}</span>
            </li>
          </ul>
        </section>
      </div>
    </template>
  </section>
</template>
