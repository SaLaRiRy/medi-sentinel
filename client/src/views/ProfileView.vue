<!-- TICKET-028: routes the shared ProfilePanel (012) without growing App.vue's
     dispatch chain. The panel itself is untouched; 029/030 restyle the views. -->
<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'

import ProfilePanel from '../components/ProfilePanel.vue'
import { homeFor } from '../session/navigation.js'
import { useAuthStore } from '../stores/auth.js'

defineProps({
  client: { type: Object, required: true },
})
const emit = defineEmits(['error'])

const auth = useAuthStore()
const router = useRouter()
const role = computed(() => auth.role)

function back() {
  router.push(homeFor(role.value) ?? '/login')
}
</script>

<template>
  <ProfilePanel :client="client" :role="role" @error="emit('error', $event)" @back="back" />
</template>
