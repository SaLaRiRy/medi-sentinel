<!--
  F-3: 管理台 / 医生工作台共用外壳（FUNCTIONAL_SPEC 2.12）。侧边菜单按角色生成，
  个人中心只在右上角下拉里出现（AC-F-10）。视觉重做（第一阶段）：深色侧边栏
  （220px，图标 + 文字，选中高亮）+ 56px 顶栏（面包屑 + 用户菜单）+ 24px 内容留白。
  菜单数据仍来自 navigation.js，`[data-menu-item]` 锚点不变。
-->
<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import UserMenu from '../components/UserMenu.vue'
import { menuFor } from '../session/navigation.js'
import { navIcon } from './navIcons.js'

const props = defineProps({
  role: { type: String, required: true },
  title: { type: String, default: '' },
})
const emit = defineEmits(['navigate', 'logout'])

const route = useRoute()
const menu = computed(() => menuFor(props.role))

const ROLE_LABEL = { admin: '管理后台', doctor: '医生工作台' }
const crumbs = computed(() => {
  const base = ROLE_LABEL[props.role] ?? '控制台'
  const current = menu.value.find((item) => item.to === route.path)
  return current && current.label !== base ? [base, current.label] : [base]
})
</script>

<template>
  <div class="console">
    <aside class="console__aside">
      <div class="console__brand">
        <span class="console__logo">
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
        <span class="console__brand-text">AI 智能问诊</span>
      </div>

      <nav class="console__menu">
        <button
          v-for="item in menu"
          :key="item.to"
          type="button"
          class="console__item"
          :class="{ 'is-active': route.path === item.to }"
          :data-menu-item="item.label"
          @click="emit('navigate', item.to)"
        >
          <svg
            class="console__icon"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.8"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <path v-for="(d, index) in navIcon(item.to)" :key="index" :d="d" />
          </svg>
          <span class="console__label">{{ item.label }}</span>
        </button>
      </nav>
    </aside>

    <div class="console__body">
      <header class="console__header">
        <nav class="console__crumbs">
          <template v-for="(crumb, index) in crumbs" :key="crumb">
            <span v-if="index > 0" class="console__crumb-sep">/</span>
            <span
              class="console__crumb"
              :class="{ 'is-current': index === crumbs.length - 1 }"
            >
              {{ crumb }}
            </span>
          </template>
        </nav>
        <div class="console__user-area">
          <UserMenu
            :role="role"
            @navigate="emit('navigate', $event)"
            @logout="emit('logout')"
          />
        </div>
      </header>
      <main class="console__content"><slot /></main>
    </div>
  </div>
</template>

<style scoped>
.console {
  display: flex;
  min-height: 100vh;
  background: var(--ms-bg);
}

.console__aside {
  flex: 0 0 var(--ms-sidebar-width);
  width: var(--ms-sidebar-width);
  display: flex;
  flex-direction: column;
  background: var(--ms-sidebar);
  color: var(--ms-text-inverse);
}

.console__brand {
  display: flex;
  align-items: center;
  gap: var(--ms-space-3);
  height: var(--ms-header-height);
  padding: 0 var(--ms-space-5);
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.console__logo {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  border-radius: 9px;
  background: var(--ms-gradient);
  color: #fff;
}

.console__logo svg {
  width: 18px;
  height: 18px;
}

.console__brand-text {
  font-size: var(--ms-font-md);
  font-weight: 600;
  letter-spacing: 0.02em;
}

.console__menu {
  display: flex;
  flex-direction: column;
  gap: var(--ms-space-1);
  padding: var(--ms-space-3) 10px;
}

.console__item {
  display: flex;
  align-items: center;
  gap: var(--ms-space-3);
  width: 100%;
  padding: 10px 12px;
  border: 0;
  border-radius: 10px;
  background: transparent;
  color: rgba(255, 255, 255, 0.72);
  font-size: var(--ms-font-base);
  text-align: left;
  cursor: pointer;
  transition: background 0.18s ease, color 0.18s ease;
}

.console__item:hover {
  background: var(--ms-sidebar-hover);
  color: #fff;
}

.console__item.is-active {
  background: var(--ms-sidebar-active);
  color: #fff;
  box-shadow: inset 3px 0 0 0 var(--ms-accent);
}

.console__icon {
  flex: 0 0 18px;
  width: 18px;
  height: 18px;
}

.console__body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.console__header {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: var(--ms-header-height);
  padding: 0 var(--ms-content-padding);
  background: var(--ms-bg-elevated);
  border-bottom: 1px solid var(--ms-border);
}

.console__crumbs {
  display: flex;
  align-items: center;
  gap: var(--ms-space-2);
  font-size: var(--ms-font-sm);
  color: var(--ms-text-muted);
}

.console__crumb.is-current {
  color: var(--ms-text);
  font-weight: 600;
}

.console__crumb-sep {
  color: var(--ms-border-strong);
}

.console__content {
  flex: 1;
  padding: var(--ms-content-padding);
  overflow: auto;
}
</style>
