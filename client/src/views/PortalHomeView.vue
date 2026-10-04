<!--
  患者门户首页：个人概览（TICKET-022）与已发布的系统公告（TICKET-021）。
  视觉重做（第二阶段，图5）：渐变 hero 横幅 + 统计卡片行 + 快捷服务卡片 + 最新公告列表。

  个人概览展示本人的人工问诊、预约、健康档案、AI 会话四项计数（FUNCTIONAL_SPEC 2.9）。
  公告公开列表**不分页**，一次返回全部已发布公告；点标题看详情，公告详情加载失败
  或记录不存在时回到首页（FUNCTIONAL_SPEC 5.21）。列表加载失败呈现空态而非错误页。
  快捷服务卡片只 emit navigate（路由/守卫语义不变）；后端调用都经 F-1 的 `client`。
-->
<script setup>
import { onMounted, ref } from 'vue'

import StatGrid from '../components/StatGrid.vue'
import { navIcon } from '../layouts/navIcons.js'

const props = defineProps({
  client: { type: Object, required: true },
})
const emit = defineEmits(['error', 'navigate'])

const OVERVIEW_FIELDS = [
  { key: 'consult_count', label: '我的咨询', accent: '#6366f1' },
  { key: 'appointment_count', label: '我的预约', accent: '#14b8a6' },
  { key: 'record_count', label: '健康档案', accent: '#8b5cf6' },
  { key: 'session_count', label: 'AI对话', accent: '#e05a8a' },
]

const QUICK_SERVICES = [
  { label: 'AI 智能问诊', to: '/portal/chat', color: '#6366f1' },
  { label: '症状推理', to: '/portal/symptom', color: '#14b8a6' },
  { label: '在线咨询', to: '/portal/consult', color: '#ef4444' },
  { label: '预约挂号', to: '/portal/appointment', color: '#8b5cf6' },
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
    <div data-hero class="portal-home__hero">
      <h1 class="portal-home__hero-title">您好，用户 👋</h1>
      <p class="portal-home__hero-subtitle">
        AI 智能医疗问诊平台，为您提供专业、便捷的健康服务
      </p>
    </div>

    <StatGrid data-user-overview :fields="OVERVIEW_FIELDS" :overview="overview" />

    <section class="portal-home__section">
      <h2 class="portal-home__section-title">快捷服务</h2>
      <div class="portal-home__quick">
        <button
          v-for="service in QUICK_SERVICES"
          :key="service.to"
          type="button"
          class="portal-home__quick-card"
          data-quick-service
          @click="emit('navigate', service.to)"
        >
          <span class="portal-home__quick-icon" :style="{ background: service.color }">
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="1.8"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <path v-for="(d, index) in navIcon(service.to)" :key="index" :d="d" />
            </svg>
          </span>
          <span class="portal-home__quick-label">{{ service.label }}</span>
        </button>
      </div>
    </section>

    <section class="portal-home__section">
      <h2 class="portal-home__section-title">最新公告</h2>

      <el-card v-if="detail" data-notice-detail class="portal-home__card" shadow="never">
        <template #header>
          <div class="portal-home__detail-head">
            <span data-detail-title class="portal-home__detail-title">{{ detail.title }}</span>
            <el-button data-back @click="back">返回列表</el-button>
          </div>
        </template>
        <p data-detail-content class="portal-home__detail-content">{{ detail.content }}</p>
      </el-card>

      <el-card v-else class="portal-home__card" shadow="never">
        <p
          v-if="loadError"
          data-error
          class="portal-home__message portal-home__message--error"
        >
          {{ loadError }}
        </p>
        <p v-else-if="items.length === 0" data-empty class="portal-home__message">暂无公告</p>

        <ul v-else class="portal-home__notices">
          <li v-for="item in items" :key="item.id" data-notice-row class="portal-home__notice">
            <button
              type="button"
              class="portal-home__notice-button"
              :data-open="item.id"
              @click="open(item.id)"
            >
              <span class="portal-home__notice-icon">
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="1.8"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                >
                  <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
                  <path d="M13.73 21a2 2 0 0 1-3.46 0" />
                </svg>
              </span>
              <span data-cell-title class="portal-home__notice-title">{{ item.title }}</span>
              <time class="portal-home__notice-time">{{ item.create_time ?? '-' }}</time>
            </button>
          </li>
        </ul>
      </el-card>
    </section>
  </section>
</template>

<style scoped>
.portal-home {
  display: flex;
  flex-direction: column;
  gap: var(--ms-space-6);
}

.portal-home__hero {
  padding: var(--ms-space-8) var(--ms-space-6);
  border-radius: var(--ms-radius-lg);
  background: var(--ms-gradient);
  color: var(--ms-text-inverse);
  box-shadow: 0 12px 32px rgba(99, 102, 241, 0.28);
}

.portal-home__hero-title {
  margin: 0;
  font-size: var(--ms-font-xl);
  font-weight: 700;
}

.portal-home__hero-subtitle {
  margin: 8px 0 0;
  color: rgba(255, 255, 255, 0.82);
  font-size: var(--ms-font-base);
}

.portal-home__section {
  display: flex;
  flex-direction: column;
  gap: var(--ms-space-3);
}

.portal-home__section-title {
  margin: 0;
  font-size: var(--ms-font-md);
  font-weight: 600;
}

.portal-home__quick {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--ms-space-4);
}

.portal-home__quick-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--ms-space-3);
  padding: var(--ms-space-6) var(--ms-space-4);
  background: var(--ms-bg-elevated);
  border: 1px solid var(--ms-border);
  border-radius: var(--ms-radius-lg);
  box-shadow: var(--ms-shadow);
  cursor: pointer;
  transition: transform 0.18s ease, box-shadow 0.18s ease;
}

.portal-home__quick-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--ms-shadow-lg);
}

.portal-home__quick-icon {
  display: grid;
  place-items: center;
  width: 52px;
  height: 52px;
  border-radius: var(--ms-radius);
  color: #fff;
}

.portal-home__quick-icon svg {
  width: 26px;
  height: 26px;
}

.portal-home__quick-label {
  font-size: var(--ms-font-base);
  font-weight: 600;
  color: var(--ms-text);
}

.portal-home__card {
  border: 1px solid var(--ms-border);
  border-radius: var(--ms-radius-lg);
  box-shadow: var(--ms-shadow);
}

.portal-home__notices {
  display: flex;
  flex-direction: column;
}

.portal-home__notice + .portal-home__notice {
  border-top: 1px solid var(--ms-border);
}

.portal-home__notice-button {
  display: flex;
  align-items: center;
  gap: var(--ms-space-3);
  width: 100%;
  padding: 14px 4px;
  border: 0;
  background: transparent;
  text-align: left;
  cursor: pointer;
}

.portal-home__notice-button:hover .portal-home__notice-title {
  color: var(--ms-primary);
}

.portal-home__notice-icon {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  flex: 0 0 32px;
  border-radius: 9px;
  background: rgba(99, 102, 241, 0.12);
  color: var(--ms-primary);
}

.portal-home__notice-icon svg {
  width: 17px;
  height: 17px;
}

.portal-home__notice-title {
  flex: 1;
  min-width: 0;
  color: var(--ms-text);
  font-size: var(--ms-font-base);
  transition: color 0.18s ease;
}

.portal-home__notice-time {
  color: var(--ms-text-muted);
  font-size: var(--ms-font-sm);
}

.portal-home__message {
  margin: 8px 0;
  color: var(--ms-text-secondary);
}

.portal-home__message--error {
  color: var(--el-color-danger);
}

.portal-home__detail-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ms-space-4);
}

.portal-home__detail-title {
  font-size: var(--ms-font-md);
  font-weight: 600;
}

.portal-home__detail-content {
  white-space: pre-wrap;
  line-height: 1.7;
  color: var(--ms-text-secondary);
}
</style>
