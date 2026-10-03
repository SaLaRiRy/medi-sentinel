<script setup>
import { createApiClient } from './api/client.js'
import HealthView from './views/HealthView.vue'

const client = createApiClient()
</script>

<template>
  <HealthView :client="client" />
</template>
