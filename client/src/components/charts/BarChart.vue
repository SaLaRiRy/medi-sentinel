<!--
  轻量 SVG 柱状图（视觉重做 第二阶段）。数据为 `[{ label, value }]`，
  渐变柱身；仅负责绘制，数据锚点由调用方保留。
-->
<script setup>
import { computed } from 'vue'

let seq = 0

const props = defineProps({
  data: { type: Array, default: () => [] },
  color: { type: String, default: '#6366f1' },
  height: { type: Number, default: 220 },
})

const uid = `ms-bar-${(seq += 1)}`
const WIDTH = 640
const PAD_X = 16
const PAD_TOP = 16
const PAD_BOTTOM = 24

const innerW = computed(() => WIDTH - PAD_X * 2)
const innerH = computed(() => props.height - PAD_TOP - PAD_BOTTOM)
const max = computed(() => Math.max(1, ...props.data.map((p) => Number(p.value) || 0)))

const bars = computed(() => {
  const count = props.data.length || 1
  const slot = innerW.value / count
  const width = Math.max(6, slot * 0.55)
  return props.data.map((p, index) => {
    const value = Number(p.value) || 0
    const h = (value / max.value) * innerH.value
    return {
      x: PAD_X + slot * index + (slot - width) / 2,
      y: PAD_TOP + innerH.value - h,
      width,
      height: Math.max(value > 0 ? 3 : 0, h),
    }
  })
})

// 最多 5 个 x 轴标签，避免密集数据互相重叠。
const labelPoints = computed(() => {
  const count = props.data.length
  if (count === 0) return []
  const stride = Math.max(1, Math.ceil(count / 5))
  const slot = innerW.value / (count || 1)
  return props.data
    .map((p, index) => ({ x: PAD_X + slot * index + slot / 2, label: p.label, index }))
    .filter((item) => item.index % stride === 0)
})

const grid = computed(() => [0, 0.25, 0.5, 0.75, 1].map((r) => PAD_TOP + innerH.value * r))
</script>

<template>
  <svg class="bar-chart" :viewBox="`0 0 ${WIDTH} ${props.height}`" role="img">
    <defs>
      <linearGradient :id="`${uid}-fill`" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" :stop-color="props.color" stop-opacity="0.95" />
        <stop offset="100%" :stop-color="props.color" stop-opacity="0.45" />
      </linearGradient>
    </defs>
    <line
      v-for="(y, index) in grid"
      :key="index"
      class="bar-chart__grid"
      x1="0"
      :x2="WIDTH"
      :y1="y"
      :y2="y"
    />
    <rect
      v-for="(bar, index) in bars"
      :key="index"
      :x="bar.x"
      :y="bar.y"
      :width="bar.width"
      :height="bar.height"
      rx="6"
      :fill="`url(#${uid}-fill)`"
    />
    <text
      v-for="item in labelPoints"
      :key="`label-${item.index}`"
      class="bar-chart__label"
      :x="item.x"
      :y="props.height - 6"
      text-anchor="middle"
    >
      {{ item.label }}
    </text>
  </svg>
</template>

<style scoped>
.bar-chart {
  display: block;
  width: 100%;
  height: auto;
}

.bar-chart__grid {
  stroke: var(--ms-border);
  stroke-width: 1;
  stroke-dasharray: 4 6;
}

.bar-chart__label {
  fill: var(--ms-text-muted);
  font-size: 11px;
}
</style>
