<!--
  TICKET-028 的未登录外壳：登录/注册页共享全屏渐变背景 + 居中舞台。
  仍保留 TICKET-001 的健康探针（HealthView 常驻挂载、启动即发 GET /api/v1/health），
  只在视觉上收成底部浅色状态行，不改变其行为。
-->
<script setup>
import HealthView from '../views/HealthView.vue'

defineProps({
  client: { type: Object, required: true },
})
</script>

<template>
  <div class="public">
    <span class="public__glow public__glow--a" aria-hidden="true" />
    <span class="public__glow public__glow--b" aria-hidden="true" />

    <main class="public__stage"><slot /></main>

    <footer class="public__health">
      <HealthView :client="client" />
    </footer>
  </div>
</template>

<style scoped>
.public {
  position: relative;
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  overflow: hidden;
  background: var(--ms-gradient);
}

.public__glow {
  position: absolute;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.12);
  pointer-events: none;
  filter: blur(2px);
}

.public__glow--a {
  top: -120px;
  right: -80px;
  width: 360px;
  height: 360px;
}

.public__glow--b {
  bottom: -160px;
  left: -100px;
  width: 420px;
  height: 420px;
}

.public__stage {
  position: relative;
  z-index: 1;
  display: flex;
  flex: 1;
  align-items: center;
  justify-content: center;
  padding: var(--ms-space-8) var(--ms-space-4);
}

.public__health {
  position: relative;
  z-index: 1;
  padding: 0 var(--ms-space-4) var(--ms-space-4);
}

/* HealthView 收成底部状态行：保留 DOM 与请求，只收窄排版。 */
.public__health :deep(.health) {
  color: rgba(255, 255, 255, 0.68);
  font-size: var(--ms-font-xs);
  text-align: center;
}

.public__health :deep(.health h1) {
  margin: 0;
  font-size: var(--ms-font-xs);
  font-weight: 600;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}

.public__health :deep(.health dl) {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: var(--ms-space-4);
  margin: 4px 0 0;
}

.public__health :deep(.health dt) {
  display: none;
}

.public__health :deep(.health dd) {
  margin: 0;
}

.public__health :deep(.health__error) {
  margin: 4px 0 0;
}
</style>
