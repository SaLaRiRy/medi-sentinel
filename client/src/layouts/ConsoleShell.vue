<!-- F-3: 管理台 / 医生工作台共用外壳（FUNCTIONAL_SPEC 2.12）。侧边菜单按角色
     生成，个人中心只在右上角下拉里出现（AC-F-10）。 -->
<script setup>
import { computed } from 'vue'

import UserMenu from '../components/UserMenu.vue'
import { menuFor } from '../session/navigation.js'

const props = defineProps({
  role: { type: String, required: true },
  title: { type: String, default: '' },
})
const emit = defineEmits(['navigate', 'logout'])

const menu = computed(() => menuFor(props.role))
</script>

<template>
  <div class="console">
    <aside class="console__aside">
      <nav class="console__menu">
        <a
          v-for="item in menu"
          :key="item.to"
          :data-menu-item="item.label"
          :href="item.to"
          @click.prevent="emit('navigate', item.to)"
          >{{ item.label }}</a
        >
      </nav>
    </aside>
    <div class="console__body">
      <header class="console__header">
        <span class="console__title">{{ title }}</span>
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
