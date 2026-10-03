<script setup>
import { onMounted, ref } from 'vue'

const props = defineProps({
  client: { type: Object, required: true },
})

const health = ref(null)
const error = ref(null)

onMounted(async () => {
  try {
    health.value = await props.client.health()
  } catch {
    error.value = '后端不可用'
  }
})
</script>

<template>
  <section class="health">
    <h1>MediSentinel</h1>
    <p v-if="error" class="health__error">{{ error }}</p>
    <dl v-else-if="health">
      <dt>服务状态</dt>
      <dd>{{ health.status }}</dd>
      <dt>数据库</dt>
      <dd>{{ health.database }}</dd>
      <dt>版本</dt>
      <dd>{{ health.version }}</dd>
    </dl>
    <p v-else>加载中…</p>
  </section>
</template>
