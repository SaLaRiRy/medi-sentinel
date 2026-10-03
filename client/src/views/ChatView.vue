<!--
  患者 AI 问诊界面（TICKET-014）。

  一次问诊是一条 SSE 流（SPEC.md 5.5）：`session` 关联新会话、`content` 逐段
  累加、`safety` 命中时只展示安全提示（AC-F-06）、`done` 带回引用与候选、`error`
  结束流。所有后端调用都走 F-1 的 `client`，本组件不认识传输层。
-->
<script setup>
import { onMounted, reactive, ref } from 'vue'

import { renderMarkdown } from '../chat/markdown.js'
import SafetyCard from '../components/SafetyCard.vue'

const props = defineProps({
  client: { type: Object, required: true },
})
const emit = defineEmits(['error'])

const DEGRADED_LABELS = { retrieval: '知识库检索降级', graph: '图谱推理降级' }

const sessions = ref([])
const activeSessionId = ref(null)
const turns = ref([])
const draft = ref('')
const streaming = ref(false)
const loadError = ref(null)

let nextId = 0

function degradedLabel(part) {
  return DEGRADED_LABELS[part] ?? part
}

function sortedCandidates(turn) {
  return [...(turn.graph ?? [])].sort(
    (left, right) => (right.coverage ?? -1) - (left.coverage ?? -1)
  )
}

function turnFromMessage(message) {
  return {
    id: nextId++,
    role: message.role,
    content: message.content ?? '',
    references: message.references ?? [],
    graph: message.graph ?? [],
    degraded: [],
    coverageNote: null,
    safety: null,
    error: null,
    streaming: false,
  }
}

async function loadSessions() {
  try {
    sessions.value = await props.client.chatSessions()
    loadError.value = null
  } catch (failure) {
    loadError.value = '无法加载会话列表，请稍后重试'
    emit('error', failure)
  }
}

async function openSession(sessionId) {
  activeSessionId.value = sessionId
  turns.value = []
  loadError.value = null
  try {
    const history = await props.client.chatMessages(sessionId)
    turns.value = history.map(turnFromMessage)
  } catch (failure) {
    loadError.value = '无法加载历史消息，请稍后重试'
    emit('error', failure)
  }
}

function newChat() {
  activeSessionId.value = null
  turns.value = []
  loadError.value = null
}

async function send() {
  const text = draft.value.trim()
  if (!text || streaming.value) return
  draft.value = ''
  loadError.value = null
  turns.value.push({ id: nextId++, role: 'user', content: text })

  const turn = reactive({
    id: nextId++,
    role: 'assistant',
    content: '',
    references: [],
    graph: [],
    degraded: [],
    coverageNote: null,
    safety: null,
    error: null,
    streaming: true,
  })
  turns.value.push(turn)
  streaming.value = true
  let createdSession = false

  try {
    const request = { session_id: activeSessionId.value, message: text }
    for await (const frame of props.client.sendChat(request)) {
      if (frame.type === 'session') {
        if (activeSessionId.value === null) createdSession = true
        activeSessionId.value = frame.session_id
      } else if (frame.type === 'content') {
        turn.content += frame.content
      } else if (frame.type === 'safety') {
        turn.safety = frame
      } else if (frame.type === 'done') {
        turn.references = frame.references ?? []
        turn.graph = frame.graph ?? []
        turn.degraded = frame.degraded ?? []
        turn.coverageNote = frame.coverage_note ?? null
      } else if (frame.type === 'error') {
        turn.error = frame.message ?? '生成失败，请稍后重试'
      }
    }
  } catch (failure) {
    turn.error = failure.message ?? '网络异常，请稍后重试'
    emit('error', failure)
  } finally {
    turn.streaming = false
    streaming.value = false
  }

  if (createdSession) await loadSessions()
}

onMounted(loadSessions)
</script>

<template>
  <section class="chat">
    <aside class="chat__sessions">
      <button type="button" data-new-chat @click="newChat">新对话</button>
      <ul data-sessions>
        <li v-for="session in sessions" :key="session.id" data-session-item>
          <button type="button" :class="{ 'is-active': session.id === activeSessionId }" @click="openSession(session.id)">
            {{ session.title }}
          </button>
        </li>
      </ul>
    </aside>

    <div class="chat__main">
      <p v-if="loadError" data-error class="chat__error">{{ loadError }}</p>

      <div class="chat__turns">
        <div v-for="turn in turns" :key="turn.id" :data-message="turn.role" class="chat__turn">
          <template v-if="turn.safety">
            <SafetyCard :safety="turn.safety" />
          </template>
          <template v-else-if="turn.role === 'user'">
            <p data-question class="chat__question">{{ turn.content }}</p>
          </template>
          <template v-else>
            <p v-if="turn.streaming" data-loading class="chat__loading">正在生成…</p>
            <div v-if="turn.content" data-answer class="chat__answer" v-html="renderMarkdown(turn.content)"></div>
            <p v-if="turn.error" data-turn-error class="chat__turn-error">{{ turn.error }}</p>
            <div v-if="turn.references.length" data-references class="chat__references">
              <div v-for="reference in turn.references" :key="reference.index" data-reference>
                [{{ reference.index }}] {{ reference.file_name }}：{{ reference.snippet }}
              </div>
            </div>
            <div v-if="turn.graph.length" data-candidates class="chat__candidates">
              <div
                v-for="candidate in sortedCandidates(turn)"
                :key="candidate.disease"
                :data-candidate="candidate.disease"
                :data-disease="candidate.disease"
                class="chat__candidate"
              >
                <span class="chat__candidate-name">{{ candidate.disease }}</span>
                <span class="chat__candidate-department">{{ candidate.department ?? '-' }}</span>
                <span class="chat__candidate-count">命中 {{ candidate.match_count }} 项</span>
                <div class="chat__coverage">
                  <div
                    v-if="typeof candidate.coverage === 'number'"
                    data-coverage-bar
                    :style="{ width: `${Math.round(candidate.coverage * 100)}%` }"
                  ></div>
                </div>
              </div>
            </div>
            <p v-if="turn.coverageNote" data-coverage-note class="chat__coverage-note">
              {{ turn.coverageNote }}
            </p>
            <ul v-if="turn.degraded.length" data-degraded class="chat__degraded">
              <li v-for="part in turn.degraded" :key="part" data-degraded-badge>
                {{ degradedLabel(part) }}
              </li>
            </ul>
          </template>
        </div>
      </div>

      <form class="chat__composer" @submit.prevent="send">
        <textarea
          v-model="draft"
          data-chat-input
          rows="2"
          placeholder="描述你的症状…"
          @keydown.enter.exact.prevent="send"
        ></textarea>
        <button type="submit" data-send :disabled="streaming">发送</button>
      </form>
    </div>
  </section>
</template>
