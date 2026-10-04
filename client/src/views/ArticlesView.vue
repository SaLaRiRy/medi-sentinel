<!--
  患者侧健康科普（TICKET-021，FUNCTIONAL_SPEC 2.8）。

  公开的文章列表（可按分类过滤）与详情：列表分页，点标题读详情、可返回列表。文章
  详情加载失败或记录不存在时留在列表并上报（FUNCTIONAL_SPEC 5.21）；列表加载失败
  呈现空态而非错误页（本票验收）。后端调用都经 F-1 的 `client`。
-->
<script setup>
import { onMounted, ref } from 'vue'

import { ARTICLE_CATEGORIES } from '../content/status.js'

const props = defineProps({
  client: { type: Object, required: true },
})
const emit = defineEmits(['error'])

const PAGE_SIZE = 10
const items = ref([])
const total = ref(0)
const page = ref(1)
const category = ref('')
const loadError = ref(null)
const detail = ref(null)

async function load() {
  try {
    const data = await props.client.articles({
      page: page.value,
      page_size: PAGE_SIZE,
      category: category.value || undefined,
    })
    items.value = data.items ?? []
    total.value = data.total ?? 0
    loadError.value = null
  } catch (failure) {
    items.value = []
    total.value = 0
    loadError.value = '文章列表加载失败'
    emit('error', failure)
  }
}

function filterByCategory() {
  page.value = 1
  load()
}

function goTo(target) {
  if (target < 1 || target === page.value) return
  if ((page.value - 1) * PAGE_SIZE >= total.value && target > page.value) return
  page.value = target
  load()
}

async function open(articleId) {
  try {
    detail.value = await props.client.article(articleId)
  } catch (failure) {
    // 详情不存在或加载失败：留在列表并上报（FUNCTIONAL_SPEC 5.21）。
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
  <section class="articles">
    <article v-if="detail" data-detail class="articles__detail">
      <h2 data-detail-title>{{ detail.title }}</h2>
      <p data-detail-content>{{ detail.content }}</p>
      <button type="button" data-back @click="back">返回列表</button>
    </article>

    <template v-else>
      <select
        v-model="category"
        data-category-filter
        class="articles__filter"
        @change="filterByCategory"
      >
        <option value="">全部分类</option>
        <option v-for="name in ARTICLE_CATEGORIES" :key="name" :value="name">
          {{ name }}
        </option>
      </select>

      <p v-if="loadError" data-error class="articles__error">{{ loadError }}</p>
      <p v-else-if="items.length === 0" data-empty class="articles__empty">
        暂无文章
      </p>

      <ul v-else class="articles__list">
        <li v-for="item in items" :key="item.id" data-article-row>
          <span data-cell-title>{{ item.title }}</span>
          <span data-cell-category>{{ item.category ?? '-' }}</span>
          <button type="button" :data-open="item.id" @click="open(item.id)">阅读</button>
        </li>
      </ul>

      <footer class="articles__pager">
        <button type="button" data-prev :disabled="page <= 1" @click="goTo(page - 1)">
          上一页
        </button>
        <button
          type="button"
          data-next
          :disabled="page * PAGE_SIZE >= total"
          @click="goTo(page + 1)"
        >
          下一页
        </button>
      </footer>
    </template>
  </section>
</template>
