<!--
  F-3: 患者门户外壳（FUNCTIONAL_SPEC 2.12）。顶部固定 7 项导航，个人中心与安全退出
  放在下拉菜单里（AC-F-10）。视觉重做（第一阶段）：紫色渐变通栏顶栏，白字图标 +
  圆角选中高亮；导航数据仍来自 navigation.js，`[data-nav-item]` 锚点不变。
-->
<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import UserMenu from '../components/UserMenu.vue'
import { portalNav } from '../session/navigation.js'
import { navIcon } from './navIcons.js'

const emit = defineEmits(['navigate', 'logout'])

const route = useRoute()
const nav = computed(() => portalNav())
</script>

<template>
  <div class="portal">
    <header class="portal__header">
      <div class="portal__brand">
        <span class="portal__logo">
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2.2"
            stroke-linecap="round"
          >
            <path d="M12 5v14" />
            <path d="M5 12h14" />
          </svg>
        </span>
        <span class="portal__brand-text">AI 智能医疗问诊平台</span>
      </div>

      <nav class="portal__nav">
        <button
          v-for="item in nav"
          :key="item.to"
          type="button"
          class="portal__item"
          :class="{ 'is-active': route.path === item.to }"
          data-nav-item
          @click="emit('navigate', item.to)"
        >
          <svg
            class="portal__icon"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.8"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <path v-for="(d, index) in navIcon(item.to)" :key="index" :d="d" />
          </svg>
          <span>{{ item.label }}</span>
        </button>
      </nav>

      <div class="portal__user-area">
        <UserMenu role="user" @navigate="emit('navigate', $event)" @logout="emit('logout')" />
      </div>
    </header>

    <main class="portal__content"><slot /></main>
  </div>
</template>

<style scoped>
.portal {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background: var(--ms-bg);
}

.portal__header {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  gap: var(--ms-space-6);
  height: var(--ms-header-height);
  padding: 0 var(--ms-content-padding);
  background: var(--ms-gradient);
  color: var(--ms-text-inverse);
  box-shadow: 0 4px 16px rgba(99, 102, 241, 0.28);
}

.portal__brand {
  display: flex;
  align-items: center;
  gap: var(--ms-space-2);
  font-size: var(--ms-font-md);
  font-weight: 700;
  white-space: nowrap;
}

.portal__logo {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.18);
}

.portal__logo svg {
  width: 17px;
  height: 17px;
}

.portal__nav {
  display: flex;
  align-items: center;
  gap: var(--ms-space-1);
  flex: 1;
  min-width: 0;
  overflow-x: auto;
}

.portal__item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 14px;
  border: 0;
  border-radius: var(--ms-radius-full);
  background: transparent;
  color: rgba(255, 255, 255, 0.82);
  font-size: var(--ms-font-base);
  white-space: nowrap;
  cursor: pointer;
  transition: background 0.18s ease, color 0.18s ease;
}

.portal__item:hover {
  background: rgba(255, 255, 255, 0.16);
  color: #fff;
}

.portal__item.is-active {
  background: rgba(255, 255, 255, 0.24);
  color: #fff;
  font-weight: 600;
}

.portal__icon {
  width: 16px;
  height: 16px;
}

.portal__user-area {
  margin-left: auto;
}

.portal__content {
  flex: 1;
  padding: var(--ms-content-padding);
}
</style>
