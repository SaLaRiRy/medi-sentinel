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
    <button type="button" data-user-menu class="user-menu__trigger">
      <span class="user-menu__avatar">用</span>
      <span class="user-menu__name">用户</span>
    </button>
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

<style scoped>
/* el-dropdown sets its own text color; re-inherit so the trigger follows the
   surrounding bar (light console header vs. the portal's purple gradient). */
.user-menu {
  color: inherit;
}

/* 触发器颜色继承所在顶栏（深色侧边栏旁的白底顶栏 / 门户的紫色渐变顶栏都适用）。 */
.user-menu__trigger {
  display: inline-flex;
  align-items: center;
  gap: var(--ms-space-2);
  padding: 4px 12px 4px 4px;
  border: 1px solid rgba(127, 127, 160, 0.22);
  border-radius: var(--ms-radius-full);
  background: rgba(127, 127, 160, 0.08);
  color: inherit;
  font-size: var(--ms-font-sm);
  cursor: pointer;
  transition: background 0.18s ease;
}

.user-menu__trigger:hover {
  background: rgba(127, 127, 160, 0.16);
}

.user-menu__avatar {
  display: grid;
  place-items: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--ms-gradient);
  color: #fff;
  font-size: var(--ms-font-xs);
  font-weight: 600;
}

.user-menu__name {
  white-space: nowrap;
}
</style>
