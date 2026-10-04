<!--
  统计数据网格（TICKET-022）：一行「标签 + 数值」。管理员运营概览、医生工作台概览
  与患者个人概览三处共用，字段由调用方按角色给出（`fields: [{key, label}]`）。
-->
<script setup>
defineProps({
  fields: { type: Array, required: true },
  overview: { type: Object, default: null },
})
</script>

<template>
  <div data-overview class="stat-grid">
    <div
      v-for="field in fields"
      :key="field.key"
      data-overview-stat
      class="stat-grid__item"
    >
      <span data-stat-label>{{ field.label }}</span>
      <strong data-stat-value>{{ overview?.[field.key] ?? 0 }}</strong>
    </div>
  </div>
</template>
