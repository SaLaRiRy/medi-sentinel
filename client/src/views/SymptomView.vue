<!--
  患者侧症状推理页（TICKET-016）。

  调用 006 的 graph-inference Skill（经 `POST /graph/infer`）把标准症状集合反查为
  候选疾病，按 `coverage` 降序展示；`coverage` 缺失时不画进度条（AC-F-14），
  科室缺失显示 `-`。图谱不可用时展示可理解的错误，而不是空白。所有后端调用都走
  F-1 的 `client`，本组件不认识传输层。
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
    <form data-symptom-form class="symptom__composer" @submit.prevent="addSymptom">
      <input v-model="draft" data-symptom-input placeholder="添加症状，如：头疼" />
      <button type="button" data-add-symptom @click="addSymptom">添加</button>
    </form>

    <ul data-symptom-list class="symptom__tags">
      <li v-for="item in symptoms" :key="item" data-symptom-tag class="symptom__tag">
        {{ item }}
        <button type="button" data-remove-symptom @click="removeSymptom(item)">×</button>
      </li>
    </ul>

    <button
      type="button"
      data-infer
      :disabled="symptoms.length === 0 || loading"
      @click="infer"
    >
      开始推理
    </button>

    <p v-if="loadError" data-error class="symptom__error">{{ loadError }}</p>
    <p v-else-if="candidates.length === 0" data-empty class="symptom__empty">
      未匹配到候选疾病
    </p>

    <ul v-else data-candidates class="symptom__candidates">
      <li
        v-for="candidate in ordered"
        :key="candidate.disease"
        data-candidate
        :data-disease="candidate.disease"
        class="symptom__candidate"
      >
        <span data-disease-name class="symptom__disease">{{ candidate.disease }}</span>
        <span data-department class="symptom__department">
          {{ candidate.department ?? '-' }}
        </span>
        <span data-match-count class="symptom__count">
          命中 {{ candidate.match_count }} 项
        </span>
        <div class="symptom__coverage">
          <div
            v-if="coveragePercent(candidate.coverage) !== null"
            data-coverage-bar
            :style="{ width: `${coveragePercent(candidate.coverage)}%` }"
          ></div>
        </div>
      </li>
    </ul>
  </section>
</template>
