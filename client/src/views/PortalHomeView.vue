<!--
  患者门户首页：已发布的系统公告（TICKET-021，FUNCTIONAL_SPEC 2.8）。

  公告公开列表**不分页**，一次返回全部已发布公告；点标题看详情，公告详情加载失败
  或记录不存在时回到首页（FUNCTIONAL_SPEC 5.21）。列表加载失败呈现空态而非错误页。
  后端调用都经 F-1 的 `client`。
-->
<script setup>
import { onMounted, ref } from 'vue'

const props = defineProps({
  client: { type: Object, required: true },
})
const emit = defineEmits(['error'])

const items = ref([])
const loadError = ref(null)
const detail = ref(null)

async function load() {
  try {
    items.value = await props.client.notices()
    loadError.value = null
  } catch (failure) {
    items.value = []
    loadError.value = '公告加载失败'
    emit('error', failure)
  }
}

async function open(noticeId) {
  try {
    detail.value = await props.client.notice(noticeId)
  } catch (failure) {
    detail.value = null
    emit('error', failure)
  }
}

function back() {
  detail.value = null
}

onMounted(load)
</script>

<template>
  <section class="portal-home">
    <article v-if="detail" data-notice-detail class="portal-home__detail">
      <h2 data-detail-title>{{ detail.title }}</h2>
      <p data-detail-content>{{ detail.content }}</p>
      <button type="button" data-back @click="back">返回首页</button>
    </article>

    <template v-else>
      <h2>系统公告</h2>
      <p v-if="loadError" data-error class="portal-home__error">{{ loadError }}</p>
      <p v-else-if="items.length === 0" data-empty class="portal-home__empty">
        暂无公告
      </p>
      <ul v-else class="portal-home__notices">
        <li v-for="item in items" :key="item.id" data-notice-row>
          <span data-cell-title>{{ item.title }}</span>
          <button type="button" :data-open="item.id" @click="open(item.id)">查看</button>
        </li>
      </ul>
    </template>
  </section>
</template>
