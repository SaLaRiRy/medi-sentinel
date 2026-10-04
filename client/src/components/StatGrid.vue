<!--
  统计数据网格（TICKET-022）：管理员运营概览、医生工作台概览与患者个人概览三处共用，
  字段由调用方按角色给出（`fields: [{key, label, accent?}]`）。
  视觉重做（第二阶段）：每项是一张圆角卡片 —— 顶部彩色横条 + 大号紫色数字 + 小号标签。
  `data-overview` / `data-overview-stat` / `data-stat-label` / `data-stat-value` 锚点不变。
-->
<script setup>
const props = defineProps({
  fields: { type: Array, required: true },
  overview: { type: Object, default: null },
})

// 每张卡片顶部横条的颜色；字段可用 `accent` 覆盖，否则按顺序轮转。
const ACCENTS = ['#6366f1', '#14b8a6', '#e05a8a', '#8b5cf6', '#3b82f6', '#f59e0b']

function accentFor(field, index) {
  return field?.accent ?? ACCENTS[index % ACCENTS.length]
}
</script>

<template>
  <div data-overview class="stat-grid">
    <div
      v-for="(field, index) in props.fields"
      :key="field.key"
      data-overview-stat
      class="stat-grid__item"
    >
      <span
        class="stat-grid__accent"
        :style="{ background: accentFor(field, index) }"
        aria-hidden="true"
      />
      <strong data-stat-value class="stat-grid__value">
        {{ props.overview?.[field.key] ?? 0 }}
      </strong>
      <span data-stat-label class="stat-grid__label">{{ field.label }}</span>
    </div>
  </div>
</template>

<style scoped>
.stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: var(--ms-space-4);
}

.stat-grid__item {
  position: relative;
  overflow: hidden;
  padding: var(--ms-space-5);
  background: var(--ms-bg-elevated);
  border: 1px solid var(--ms-border);
  border-radius: var(--ms-radius-lg);
  box-shadow: var(--ms-shadow);
}

.stat-grid__accent {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 4px;
}

.stat-grid__value {
  display: block;
  font-size: var(--ms-font-2xl);
  font-weight: 800;
  line-height: 1.1;
  color: var(--ms-primary);
}

.stat-grid__label {
  display: block;
  margin-top: 6px;
  color: var(--ms-text-muted);
  font-size: var(--ms-font-sm);
}
</style>
