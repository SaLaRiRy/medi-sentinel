<!-- F-3: 患者门户外壳（FUNCTIONAL_SPEC 2.12）。顶部固定 7 项导航，个人中心与
     安全退出放在下拉菜单里（AC-F-10）。TICKET-028 换成 element-plus 的
     el-container / el-header / el-menu；导航数据仍来自 navigation.js。 -->
<script setup>
import { computed } from 'vue'

import UserMenu from '../components/UserMenu.vue'
import { portalNav } from '../session/navigation.js'

const emit = defineEmits(['navigate', 'logout'])

const nav = computed(() => portalNav())
</script>

<template>
  <el-container class="portal">
    <el-header class="portal__header">
      <el-menu class="portal__nav" mode="horizontal" :default-active="nav[0]?.to">
        <el-menu-item
          v-for="item in nav"
          :key="item.to"
          :index="item.to"
          data-nav-item
          @click="emit('navigate', item.to)"
        >
          {{ item.label }}
        </el-menu-item>
      </el-menu>
      <div class="portal__user-area">
        <UserMenu role="user" @navigate="emit('navigate', $event)" @logout="emit('logout')" />
      </div>
    </el-header>
    <el-main class="portal__content"><slot /></el-main>
  </el-container>
</template>
