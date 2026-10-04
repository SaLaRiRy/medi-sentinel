<!-- F-3: 管理台 / 医生工作台共用外壳（FUNCTIONAL_SPEC 2.12）。侧边菜单按角色
     生成，个人中心只在右上角下拉里出现（AC-F-10）。TICKET-028 换成 element-plus
     的 el-container / el-aside / el-menu / el-header；菜单数据仍来自 navigation.js。 -->
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
  <el-container class="console">
    <el-aside class="console__aside" width="200px">
      <el-menu class="console__menu" :default-active="menu[0]?.to">
        <el-menu-item
          v-for="item in menu"
          :key="item.to"
          :index="item.to"
          :data-menu-item="item.label"
          @click="emit('navigate', item.to)"
        >
          {{ item.label }}
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container class="console__body">
      <el-header class="console__header">
        <span class="console__title">{{ title }}</span>
        <div class="console__user-area">
          <UserMenu
            :role="role"
            @navigate="emit('navigate', $event)"
            @logout="emit('logout')"
          />
        </div>
      </el-header>
      <el-main class="console__content"><slot /></el-main>
    </el-container>
  </el-container>
</template>
