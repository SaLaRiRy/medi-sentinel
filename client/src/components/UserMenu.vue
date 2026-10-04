<!-- 右上角用户下拉：个人中心只在闸内出现，安全退出同在此处（AC-F-10）。
     TICKET-028 用 element-plus 的 el-dropdown 重做；对外仍是 navigate / logout
     两个事件，视图与外壳的契约不变。 -->
<script setup>
import { computed } from 'vue'

import { personalCenterFor } from '../session/navigation.js'

const props = defineProps({
  role: { type: String, required: true },
})
const emit = defineEmits(['navigate', 'logout'])

const personal = computed(() => personalCenterFor(props.role))

function goPersonal() {
  if (personal.value) emit('navigate', personal.value.to)
}

function logout() {
  emit('logout')
}
</script>

<template>
  <el-dropdown
    class="user-menu"
    trigger="click"
    :teleported="false"
    :persistent="false"
  >
    <button type="button" data-user-menu>用户</button>
    <template #dropdown>
      <el-dropdown-menu>
        <el-dropdown-item data-personal-center @click="goPersonal">
          {{ personal?.label }}
        </el-dropdown-item>
        <el-dropdown-item data-logout @click="logout">安全退出</el-dropdown-item>
      </el-dropdown-menu>
    </template>
  </el-dropdown>
</template>
