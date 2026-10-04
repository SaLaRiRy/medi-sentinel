<!--
  医生工作台概览（TICKET-022，FUNCTIONAL_SPEC 2.9 / SPEC.md 5.4）。
  TICKET-030 改用 element-plus：el-card 承载工作台统计，加载用 v-loading。

  四项工作台指标：待处理工单、今日预约、已回复工单、患者总数。加载失败呈现空状态
  而非错误页。所有后端调用都经 F-1 的 `client`。
-->
<script setup>
import { onMounted, ref } from 'vue'

import StatGrid from '../components/StatGrid.vue'

const props = defineProps({
  client: { type: Object, required: true },
})
const emit = defineEmits(['error'])

const OVERVIEW_FIELDS = [
  { key: 'pending_consults', label: '待处理工单' },
  { key: 'today_appointments', label: '今日预约' },
  { key: 'replied_consults', label: '已回复工单' },
  { key: 'total_patients', label: '患者总数' },
]

const overview = ref(null)
const loadError = ref(null)
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    overview.value = await props.client.statOverview()
    loadError.value = null
  } catch (failure) {
    overview.value = null
    loadError.value = '工作台数据加载失败'
    emit('error', failure)
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <section class="doctor-dashboard">
    <p v-if="loadError" data-error class="doctor-dashboard__error">{{ loadError }}</p>
    <el-card v-else v-loading="loading" class="doctor-dashboard__card" shadow="never">
      <template #header>
        <span class="card-title">工作台</span>
      </template>
      <StatGrid v-if="overview" :fields="OVERVIEW_FIELDS" :overview="overview" />
    </el-card>
  </section>
</template>

<style scoped>
.doctor-dashboard {
  padding: 0;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
}

.doctor-dashboard__error {
  margin: 8px 0;
  color: var(--el-color-danger);
}
</style>
