<!-- 安全门拦截时的唯一展示（AC-F-06）：文案来自 `safety` 帧，字段与 008 对齐。 -->
<script setup>
defineProps({
  safety: { type: Object, required: true },
})
</script>

<template>
  <section data-safety-card class="safety-card">
    <h2 data-safety-level class="safety-card__level">
      {{ safety.level === 'emergency' ? '紧急' : '尽快就医' }}
    </h2>
    <p data-safety-message class="safety-card__message">{{ safety.message }}</p>
    <p data-safety-action class="safety-card__action">{{ safety.suggested_action }}</p>
    <ul data-safety-flags class="safety-card__flags">
      <li v-for="flag in safety.red_flags" :key="flag.id" data-red-flag>
        {{ flag.label }}（{{ flag.matched_surface }}）
      </li>
    </ul>
  </section>
</template>
