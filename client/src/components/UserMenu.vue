<!-- 右上角用户下拉：个人中心只在闸内出现，安全退出同在此处（AC-F-10）。 -->
<script setup>
import { computed, ref } from 'vue'

import { personalCenterFor } from '../session/navigation.js'

const props = defineProps({
  role: { type: String, required: true },
})
const emit = defineEmits(['navigate', 'logout'])

const personal = computed(() => personalCenterFor(props.role))
const open = ref(false)

function goPersonal() {
  open.value = false
  if (personal.value) emit('navigate', personal.value.to)
}

function logout() {
  open.value = false
  emit('logout')
}
</script>

<template>
  <div class="user-menu">
    <button type="button" data-user-menu @click="open = !open">用户</button>
    <ul v-if="open" class="user-menu__dropdown">
      <li>
        <a data-personal-center href="#" @click.prevent="goPersonal">{{
          personal?.label
        }}</a>
      </li>
      <li><a data-logout href="#" @click.prevent="logout">安全退出</a></li>
    </ul>
  </div>
</template>
