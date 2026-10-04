<!--
  轻量 SVG 折线图（视觉重做 第二阶段）。无第三方图表依赖，数据为
  `[{ label, value }]`；配色随 `color` 传入。仅负责绘制，数据锚点由调用方保留。
-->
<script setup>
import { computed } from 'vue'

let seq = 0

const props = defineProps({
  data: { type: Array, default: () => [] },
  color: { type: String, default: '#6366f1' },
  height: { type: Number, default: 220 },
})

const uid = `ms-line-${(seq += 1)}`
const WIDTH = 640
const PAD_X = 16
const PAD_TOP = 16
const PAD_BOTTOM = 24

const innerW = computed(() => WIDTH - PAD_X * 2)
const innerH = computed(() => props.height - PAD_TOP - PAD_BOTTOM)
const max = computed(() => Math.max(1, ...props.data.map((p) => Number(p.value) || 0)))

const points = computed(() =>
  props.data.map((p, index) => {
    const x =
      props.data.length > 1
        ? PAD_X + (innerW.value * index) / (props.data.length - 1)
        : WIDTH / 2
    const y = PAD_TOP + innerH.value - ((Number(p.value) || 0) / max.value) * innerH.value
    return { x, y, label: p.label }
  })
)

// 最多 5 个 x 轴标签，避免密集数据互相重叠。
const labelPoints = computed(() => {
  const pts = points.value
  if (pts.length === 0) return []
  const stride = Math.max(1, Math.ceil(pts.length / 5))
  return pts
    .map((point, index) => ({ ...point, index }))
    .filter((item) => item.index % stride === 0 || item.index === pts.length - 1)
    .map((item) => ({
      x: item.x,
      label: item.label,
      index: item.index,
      // 首尾标签贴边对齐，避免被 viewBox 裁切。
      anchor: item.index === 0 ? 'start' : item.index === pts.length - 1 ? 'end' : 'middle',
    }))
})

const linePath = computed(() =>
  points.value.map((p, index) => `${index === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ')
)

const areaPath = computed(() => {
  const pts = points.value
  if (pts.length === 0) return ''
  const base = PAD_TOP + innerH.value
  return `M ${pts[0].x} ${base} ${pts.map((p) => `L ${p.x} ${p.y}`).join(' ')} L ${
    pts[pts.length - 1].x
  } ${base} Z`
})

const grid = computed(() => [0, 0.25, 0.5, 0.75, 1].map((r) => PAD_TOP + innerH.value * r))
</script>

<template>
  <svg class="line-chart" :viewBox="`0 0 ${WIDTH} ${props.height}`" role="img">
    <defs>
      <linearGradient :id="`${uid}-fill`" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" :stop-color="props.color" stop-opacity="0.3" />
        <stop offset="100%" :stop-color="props.color" stop-opacity="0" />
      </linearGradient>
    </defs>
    <line
      v-for="(y, index) in grid"
      :key="index"
      class="line-chart__grid"
      x1="0"
      :x2="WIDTH"
      :y1="y"
      :y2="y"
    />
    <path :d="areaPath" :fill="`url(#${uid}-fill)`" />
    <path
      :d="linePath"
      fill="none"
      :stroke="props.color"
      stroke-width="2.5"
      stroke-linecap="round"
      stroke-linejoin="round"
    />
    <circle v-for="(p, index) in points" :key="index" :cx="p.x" :cy="p.y" r="3" :fill="props.color" />
    <text
      v-for="(p, index) in labelPoints"
      :key="`label-${index}`"
      class="line-chart__label"
      :x="p.x"
      :y="props.height - 6"
      :text-anchor="p.anchor"
    >
      {{ p.label }}
    </text>
  </svg>
</template>

<style scoped>
.line-chart {
  display: block;
  width: 100%;
  height: auto;
}

.line-chart__grid {
  stroke: var(--ms-border);
  stroke-width: 1;
  stroke-dasharray: 4 6;
}

.line-chart__label {
  fill: var(--ms-text-muted);
  font-size: 11px;
}
</style>
