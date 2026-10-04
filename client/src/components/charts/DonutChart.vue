<!--
  轻量 SVG 环形图（视觉重做 第二阶段）。数据为 `[{ label, value }]`，
  按 `palette` 轮转配色，中心显示合计；图例由调用方渲染以保留数据锚点。
-->
<script setup>
import { computed } from 'vue'

const props = defineProps({
  data: { type: Array, default: () => [] },
  palette: {
    type: Array,
    default: () => ['#6366f1', '#22a06b', '#f4b740', '#e05a8a', '#3b82f6', '#8b5cf6', '#14b8a6'],
  },
  size: { type: Number, default: 180 },
})

const RADIUS = 54
const CIRCUMFERENCE = 2 * Math.PI * RADIUS

const total = computed(() => props.data.reduce((sum, item) => sum + (Number(item.value) || 0), 0))

const segments = computed(() => {
  let offset = 0
  return props.data.map((item, index) => {
    const value = Number(item.value) || 0
    const length = total.value > 0 ? (value / total.value) * CIRCUMFERENCE : 0
    const segment = {
      color: props.palette[index % props.palette.length],
      dasharray: `${length} ${CIRCUMFERENCE - length}`,
      dashoffset: -offset,
    }
    offset += length
    return segment
  })
})
</script>

<template>
  <svg class="donut-chart" viewBox="0 0 140 140" :style="{ width: `${props.size}px` }" role="img">
    <circle class="donut-chart__track" cx="70" cy="70" :r="RADIUS" />
    <circle
      v-for="(segment, index) in segments"
      :key="index"
      class="donut-chart__segment"
      cx="70"
      cy="70"
      :r="RADIUS"
      :stroke="segment.color"
      :stroke-dasharray="segment.dasharray"
      :stroke-dashoffset="segment.dashoffset"
    />
    <text class="donut-chart__total" x="70" y="66">{{ total }}</text>
    <text class="donut-chart__caption" x="70" y="86">合计</text>
  </svg>
</template>

<style scoped>
.donut-chart {
  display: block;
  margin: 0 auto;
}

.donut-chart__track,
.donut-chart__segment {
  fill: none;
  stroke-width: 18;
}

.donut-chart__track {
  stroke: var(--ms-border);
}

.donut-chart__segment {
  transform: rotate(-90deg);
  transform-origin: 70px 70px;
  transition: stroke-dasharray 0.3s ease;
}

.donut-chart__total {
  fill: var(--ms-text);
  font-size: 22px;
  font-weight: 700;
  text-anchor: middle;
}

.donut-chart__caption {
  fill: var(--ms-text-muted);
  font-size: 11px;
  text-anchor: middle;
}
</style>
