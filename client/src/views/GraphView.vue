<!--
  管理端图谱可视化页（TICKET-016，FUNCTIONAL_SPEC 2.4 / 5.20）。

  全图 `GET /graph` 默认加载；按关键字搜索实体 `GET /graph/search`，选中后加载
  实体邻域 `GET /graph/entities/{name}/neighbors`（`depth` 真实生效），疾病再取
  `GET /graph/diseases/{name}` 详情。节点按标签着色（疾病 / 症状 / 其他），关系名
  按既定映射展示、未知值回退原文；图谱不可用时展示可理解的错误。所有后端调用都走
  F-1 的 `client`。
-->
<script setup>
import { onMounted, ref } from 'vue'

import { nodeColor, nodeGroup, nodeGroupLabel } from '../graph/nodes.js'
import { relationLabel } from '../graph/relations.js'

const props = defineProps({
  client: { type: Object, required: true },
})
const emit = defineEmits(['error'])

const DEPTHS = [1, 2, 3, 4, 5]

const keyword = ref('')
const depth = ref(1)
const nodes = ref([])
const edges = ref([])
const results = ref([])
const detail = ref(null)
const selected = ref(null)
const loadError = ref(null)

function applyGraph(payload) {
  nodes.value = payload?.nodes ?? []
  edges.value = payload?.edges ?? []
}

function labelOf(id) {
  return nodes.value.find((node) => node.id === id)?.name ?? id
}

async function loadOverview() {
  loadError.value = null
  try {
    applyGraph(await props.client.graphOverview())
  } catch (failure) {
    nodes.value = []
    edges.value = []
    loadError.value = failure.message ?? '图谱加载失败'
    emit('error', failure)
  }
}

async function search() {
  const text = keyword.value.trim()
  if (!text) return
  loadError.value = null
  try {
    results.value = await props.client.graphSearch(text)
  } catch (failure) {
    results.value = []
    loadError.value = failure.message ?? '实体搜索失败'
    emit('error', failure)
  }
}

async function loadNeighbors() {
  if (!selected.value) return
  loadError.value = null
  try {
    applyGraph(await props.client.graphNeighbors(selected.value.name, Number(depth.value)))
  } catch (failure) {
    nodes.value = []
    edges.value = []
    loadError.value = failure.message ?? '邻域加载失败'
    emit('error', failure)
  }
}

async function select(entity) {
  selected.value = entity
  detail.value = null
  await loadNeighbors()
  if (entity.label === 'Disease') {
    try {
      detail.value = await props.client.graphDisease(entity.name)
    } catch (failure) {
      emit('error', failure)
    }
  }
}

onMounted(loadOverview)
</script>

<template>
  <section class="graph">
    <header class="graph__toolbar">
      <form data-search class="graph__search" @submit.prevent="search">
        <input v-model="keyword" data-search-keyword placeholder="搜索实体名称" />
        <button type="submit">搜索</button>
      </form>
      <label class="graph__depth">
        邻域深度
        <select v-model="depth" data-depth @change="loadNeighbors">
          <option v-for="value in DEPTHS" :key="value" :value="value">{{ value }}</option>
        </select>
      </label>
    </header>

    <ul v-if="results.length" data-search-results class="graph__results">
      <li v-for="entity in results" :key="entity.id">
        <button type="button" data-search-result @click="select(entity)">
          {{ entity.name }}
        </button>
      </li>
    </ul>

    <p v-if="loadError" data-error class="graph__error">{{ loadError }}</p>

    <section v-if="detail" data-disease-detail class="graph__detail">
      <h3>{{ detail.disease }}</h3>
      <p data-detail-department>{{ detail.department ?? '-' }}</p>
    </section>

    <p v-if="!loadError && nodes.length === 0" data-empty class="graph__empty">
      暂无可展示的图谱数据
    </p>

    <ul v-if="nodes.length" data-nodes class="graph__nodes">
      <li
        v-for="node in nodes"
        :key="node.id"
        :data-node="node.name"
        :data-node-group="nodeGroup(node.label)"
        :style="{ color: nodeColor(node.label) }"
        class="graph__node"
      >
        {{ node.name }}
        <small>{{ nodeGroupLabel(node.label) }}</small>
      </li>
    </ul>

    <ul v-if="edges.length" data-edges class="graph__edges">
      <li v-for="(edge, index) in edges" :key="index" data-edge class="graph__edge">
        {{ labelOf(edge.source) }} — {{ relationLabel(edge.type) }} →
        {{ labelOf(edge.target) }}
      </li>
    </ul>
  </section>
</template>
