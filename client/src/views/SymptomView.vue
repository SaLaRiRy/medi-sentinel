<!--
  患者侧症状推理页（TICKET-016）。TICKET-029 改用 element-plus：el-form/el-input/
  el-button 录入，候选疾病用 el-card + el-tag + el-progress 展示。

  调用 006 的 graph-inference Skill（经 `POST /graph/infer`）把标准症状集合反查为
  候选疾病，按 `coverage` 降序展示；`coverage` 缺失时不画进度条（AC-F-14），
  科室缺失显示 `-`。图谱不可用时展示可理解的错误，而不是空白。所有后端调用都走
  F-1 的 `client`，本组件不认识传输层。data-* 锚点原样保留。
-->
<script setup>
import { computed, ref } from 'vue'

import { coveragePercent, sortedCandidates } from '../graph/candidates.js'

const props = defineProps({
  client: { type: Object, required: true },
})
const emit = defineEmits(['error'])

const draft = ref('')
const symptoms = ref([])
const candidates = ref([])
const loading = ref(false)
const loadError = ref(null)

const ordered = computed(() => sortedCandidates(candidates.value))

function addSymptom() {
  const text = draft.value.trim()
  if (text && !symptoms.value.includes(text)) {
    symptoms.value = [...symptoms.value, text]
  }
  draft.value = ''
}

function removeSymptom(text) {
  symptoms.value = symptoms.value.filter((item) => item !== text)
}

async function infer() {
  if (symptoms.value.length === 0 || loading.value) return
  loading.value = true
  loadError.value = null
  try {
    candidates.value = await props.client.inferGraph([...symptoms.value])
  } catch (failure) {
    candidates.value = []
    loadError.value = failure.message ?? '图谱推理失败，请稍后重试'
    emit('error', failure)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <section class="symptom">
    <el-card class="symptom__panel" shadow="never">
      <template #header>
        <div class="card-head">
          <span class="card-head__title">症状推理</span>
          <span class="card-head__hint">输入症状，按覆盖率推荐候选疾病</span>
        </div>
      </template>

      <el-form data-symptom-form class="symptom__composer" @submit.prevent="addSymptom">
        <el-input
          v-model="draft"
          data-symptom-input
          placeholder="添加症状，如：头疼"
          clearable
          @keydown.enter.prevent="addSymptom"
        />
        <el-button type="primary" data-add-symptom native-type="button" @click="addSymptom">
          添加
        </el-button>
      </el-form>

      <div data-symptom-list class="symptom__tags">
        <el-tag
          v-for="item in symptoms"
          :key="item"
          data-symptom-tag
          closable
          size="large"
          @close="removeSymptom(item)"
        >
          {{ item }}
        </el-tag>
        <span v-if="symptoms.length === 0" class="symptom__tags-empty">尚未添加症状</span>
      </div>

      <el-button
        type="primary"
        data-infer
        :disabled="symptoms.length === 0 || loading"
        :loading="loading"
        @click="infer"
      >
        开始推理
      </el-button>

      <p v-if="loadError" data-error class="symptom__message symptom__message--error">
        {{ loadError }}
      </p>
      <p v-else-if="candidates.length === 0" data-empty class="symptom__message">
        未匹配到候选疾病
      </p>

      <div v-else data-candidates class="symptom__candidates">
        <el-card
          v-for="candidate in ordered"
          :key="candidate.disease"
          data-candidate
          :data-disease="candidate.disease"
          shadow="hover"
          class="symptom__candidate"
        >
          <div class="symptom__candidate-head">
            <span data-disease-name class="symptom__disease">{{ candidate.disease }}</span>
            <el-tag data-department size="small" effect="plain">
              {{ candidate.department ?? '-' }}
            </el-tag>
          </div>
          <div class="symptom__candidate-meta">
            <span data-match-count class="symptom__count">
              命中 {{ candidate.match_count }} 项
            </span>
            <span
              v-if="coveragePercent(candidate.coverage) !== null"
              class="symptom__coverage-text"
            >
              覆盖率 {{ coveragePercent(candidate.coverage) }}%
            </span>
          </div>
          <el-progress
            v-if="coveragePercent(candidate.coverage) !== null"
            data-coverage-bar
            :percentage="coveragePercent(candidate.coverage)"
            :stroke-width="10"
          />
        </el-card>
      </div>
    </el-card>
  </section>
</template>

<style scoped>
.symptom {
  padding: 0;
}

.card-head {
  display: flex;
  align-items: baseline;
  gap: 12px;
}

.card-head__title {
  font-size: 16px;
  font-weight: 600;
}

.card-head__hint {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.symptom__composer {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
}

.symptom__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  min-height: 32px;
  margin-bottom: 16px;
  align-items: center;
}

.symptom__tags-empty {
  color: var(--el-text-color-placeholder);
  font-size: 13px;
}

.symptom__message {
  margin: 16px 0;
  color: var(--el-text-color-secondary);
}

.symptom__message--error {
  color: var(--el-color-danger);
}

.symptom__candidates {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 12px;
  margin-top: 16px;
}

.symptom__candidate-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.symptom__disease {
  font-weight: 600;
}

.symptom__candidate-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
</style>
