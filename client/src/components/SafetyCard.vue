<!-- 安全门拦截时的唯一展示（AC-F-06）：文案来自 `safety` 帧，字段与 008 对齐。
     TICKET-029 用 el-card + el-tag + el-alert 重做外观，data-* 锚点保留。 -->
<script setup>
defineProps({
  safety: { type: Object, required: true },
})
</script>

<template>
  <section data-safety-card class="safety-card">
    <el-card shadow="never" class="safety-card__inner">
      <template #header>
        <div class="safety-card__head">
          <el-tag data-safety-level type="danger" effect="dark">
            {{ safety.level === 'emergency' ? '紧急' : '尽快就医' }}
          </el-tag>
          <span class="safety-card__title">安全提示</span>
        </div>
      </template>
      <el-alert data-safety-message type="error" :closable="false" show-icon>
        <template #title>{{ safety.message }}</template>
      </el-alert>
      <p data-safety-action class="safety-card__action">{{ safety.suggested_action }}</p>
      <ul data-safety-flags class="safety-card__flags">
        <li v-for="flag in safety.red_flags" :key="flag.id" data-red-flag>
          <el-tag size="small" type="danger" effect="plain">{{ flag.label }}</el-tag>
          <span class="safety-card__surface">{{ flag.matched_surface }}</span>
        </li>
      </ul>
    </el-card>
  </section>
</template>

<style scoped>
.safety-card__head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.safety-card__title {
  font-weight: 600;
}

.safety-card__action {
  margin: 12px 0;
}

.safety-card__flags {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.safety-card__flags li {
  display: flex;
  align-items: center;
  gap: 8px;
}

.safety-card__surface {
  color: var(--el-text-color-secondary);
}
</style>
