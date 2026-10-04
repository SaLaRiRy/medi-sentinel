<!--
  管理端图谱可视化页（TICKET-016，FUNCTIONAL_SPEC 2.4 / 5.20）。
  TICKET-030 改用 element-plus：el-form/el-input/el-select/el-button 检索，el-card
  载疾病详情，节点用 el-tag 按类型着色。

  全图 `GET /graph` 默认加载；按关键字搜索实体 `GET /graph/search`，选中后加载
  实体邻域 `GET /graph/entities/{name}/neighbors`（`depth` 真实生效），疾病再取
  `GET /graph/diseases/{name}` 详情。节点按标签着色（疾病 / 症状 / 其他），关系名
  按既定映射展示、未知值回退原文；图谱不可用时展示可理解的错误。所有后端调用都走
  F-1 的 `client`。
-->
<script setup>
import { onMounted, ref, watch } from 'vue'

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

// el-select emits model updates, not a native change; a watcher re-queries the
// neighbourhood only once an entity is selected.
watch(depth, () => {
  if (selected.value) loadNeighbors()
})

onMounted(loadOverview)
</script>

<template>
  <section class="graph">
    <el-card class="graph__card" shadow="never">
      <template #header>
        <span class="card-title">知识图谱</span>
      </template>

      <header class="graph__toolbar">
        <el-form data-search class="graph__search" @submit.prevent="search">
          <el-input v-model="keyword" data-search-keyword placeholder="搜索实体名称" clearable />
          <el-button type="primary" native-type="submit">搜索</el-button>
        </el-form>
        <div class="graph__depth">
          <span class="graph__depth-label">邻域深度</span>
          <el-select v-model="depth" data-depth class="graph__depth-select" :teleported="false">
            <el-option v-for="value in DEPTHS" :key="value" :value="value" :label="String(value)" />
          </el-select>
        </div>
      </header>

      <ul v-if="results.length" data-search-results class="graph__results">
        <li v-for="entity in results" :key="entity.id">
          <el-button size="small" data-search-result @click="select(entity)">
            {{ entity.name }}
          </el-button>
        </li>
      </ul>

      <p v-if="loadError" data-error class="graph__message graph__message--error">{{ loadError }}</p>

      <el-card v-if="detail" data-disease-detail class="graph__detail" shadow="never">
        <template #header><span class="card-title">{{ detail.disease }}</span></template>
        <p data-detail-department>{{ detail.department ?? '-' }}</p>
      </el-card>

      <p v-if="!loadError && nodes.length === 0" data-empty class="graph__message">
        暂无可展示的图谱数据
      </p>

      <ul v-if="nodes.length" data-nodes class="graph__nodes">
        <li v-for="node in nodes" :key="node.id" class="graph__node">
          <el-tag
            :data-node="node.name"
            :data-node-group="nodeGroup(node.label)"
            :style="{ color: nodeColor(node.label) }"
            effect="plain"
            size="large"
          >
            {{ node.name }} · {{ nodeGroupLabel(node.label) }}
          </el-tag>
        </li>
      </ul>

      <ul v-if="edges.length" data-edges class="graph__edges">
        <li v-for="(edge, index) in edges" :key="index" data-edge class="graph__edge">
          {{ labelOf(edge.source) }} — {{ relationLabel(edge.type) }} →
          {{ labelOf(edge.target) }}
        </li>
      </ul>
    </el-card>
  </section>
</template>

<style scoped>
.graph {
  padding: 0;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
}

.graph__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.graph__search {
  display: flex;
  gap: 12px;
}

.graph__search :deep(.el-input) {
  width: 240px;
}

.graph__depth {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.graph__depth-select {
  width: 90px;
}

.graph__results {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 0 0 12px;
  padding: 0;
  list-style: none;
}

.graph__message {
  margin: 8px 0;
  color: var(--el-text-color-secondary);
}

.graph__message--error {
  color: var(--el-color-danger);
}

.graph__detail {
  margin-bottom: 12px;
}

.graph__nodes {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 0 0 12px;
  padding: 0;
  list-style: none;
}

.graph__edges {
  margin: 0;
  padding: 0;
  list-style: none;
}

.graph__edge {
  padding: 4px 0;
  color: var(--el-text-color-regular);
  font-size: 13px;
}
</style>
