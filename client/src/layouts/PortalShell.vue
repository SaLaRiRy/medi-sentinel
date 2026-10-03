<!-- F-3: 患者门户外壳（FUNCTIONAL_SPEC 2.12）。顶部固定 7 项导航，个人中心与
     安全退出放在下拉菜单里（AC-F-10）。 -->
<script setup>
import { computed } from 'vue'

import UserMenu from '../components/UserMenu.vue'
import { portalNav } from '../session/navigation.js'

const emit = defineEmits(['navigate', 'logout'])

const nav = computed(() => portalNav())
</script>

<template>
  <div class="portal">
    <header class="portal__header">
      <nav class="portal__nav">
        <a
          v-for="item in nav"
          :key="item.to"
          data-nav-item
          :href="item.to"
          @click.prevent="emit('navigate', item.to)"
          >{{ item.label }}</a
        >
      </nav>
      <div class="portal__user-area">
        <UserMenu role="user" @navigate="emit('navigate', $event)" @logout="emit('logout')" />
      </div>
    </header>
    <main class="portal__content"><slot /></main>
  </div>
</template>
