<!-- TICKET-028: the unauthenticated shell. It keeps TICKET-001's health footer
     visible on login/register and gives App.vue one layout component per route
     layout instead of a per-screen dispatch chain. -->
<script setup>
import HealthView from '../views/HealthView.vue'

defineProps({
  client: { type: Object, required: true },
})
</script>

<template>
  <div class="public">
    <slot />
    <HealthView :client="client" />
  </div>
</template>
