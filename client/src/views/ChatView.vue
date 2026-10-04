<!--
  患者 AI 问诊界面（TICKET-014）。TICKET-029 改用 element-plus：会话列表 el-card，
  消息气泡 el-card + 自定义样式（element-plus 无现成气泡），输入 el-input(textarea)
  + el-button，degraded 标记 el-tag，coverage 用 el-progress。

  一次问诊是一条 SSE 流（SPEC.md 5.5）：`session` 关联新会话、`content` 逐段
  累加、`safety` 命中时只展示安全提示（AC-F-06）、`done` 带回引用与候选、`error`
  结束流。所有后端调用都走 F-1 的 `client`，本组件不认识传输层。data-* 锚点原样保留。
-->
<script setup>
import { onMounted, reactive, ref } from 'vue'

import { renderMarkdown } from '../chat/markdown.js'
import SafetyCard from '../components/SafetyCard.vue'
import { coveragePercent, sortedCandidates } from '../graph/candidates.js'

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
      <el-card shadow="never" class="chat__sessions-card">
        <template #header>
          <span class="card-title">对话</span>
        </template>
        <el-button type="primary" data-new-chat class="chat__new" @click="newChat">
          新对话
        </el-button>
        <ul data-sessions class="chat__session-list">
          <li v-for="session in sessions" :key="session.id" data-session-item class="chat__session">
            <button
              type="button"
              class="chat__session-button"
              :class="{ 'is-active': session.id === activeSessionId }"
              @click="openSession(session.id)"
            >
              <span class="chat__session-title">{{ session.title }}</span>
              <el-tag v-if="session.message_count" size="small" effect="plain">
                {{ session.message_count }}
              </el-tag>
            </button>
          </li>
        </ul>
      </el-card>
    </aside>

    <div class="chat__main">
      <p v-if="loadError" data-error class="chat__error">{{ loadError }}</p>

      <div class="chat__turns">
        <div
          v-for="turn in turns"
          :key="turn.id"
          :data-message="turn.role"
          class="chat__turn"
          :class="`chat__turn--${turn.role}`"
        >
          <template v-if="turn.safety">
            <SafetyCard :safety="turn.safety" />
          </template>
          <template v-else-if="turn.role === 'user'">
            <el-card shadow="never" class="chat__bubble chat__bubble--user">
              <p data-question class="chat__question">{{ turn.content }}</p>
            </el-card>
          </template>
          <template v-else>
            <el-card shadow="never" class="chat__bubble chat__bubble--assistant">
              <p v-if="turn.streaming" data-loading class="chat__loading">正在生成…</p>
              <div
                v-if="turn.content"
                data-answer
                class="chat__answer"
                v-html="renderMarkdown(turn.content)"
              ></div>
              <p v-if="turn.error" data-turn-error class="chat__turn-error">{{ turn.error }}</p>
              <div v-if="turn.references.length" data-references class="chat__references">
                <div
                  v-for="reference in turn.references"
                  :key="reference.index"
                  data-reference
                  class="chat__reference"
                >
                  <el-tag size="small" type="info">[{{ reference.index }}]</el-tag>
                  {{ reference.file_name }}：{{ reference.snippet }}
                </div>
              </div>
              <div v-if="turn.graph.length" data-candidates class="chat__candidates">
                <div
                  v-for="candidate in sortedCandidates(turn.graph)"
                  :key="candidate.disease"
                  :data-candidate="candidate.disease"
                  :data-disease="candidate.disease"
                  class="chat__candidate"
                >
                  <div class="chat__candidate-head">
                    <span class="chat__candidate-name">{{ candidate.disease }}</span>
                    <el-tag size="small" effect="plain">{{ candidate.department ?? '-' }}</el-tag>
                    <span class="chat__candidate-count">命中 {{ candidate.match_count }} 项</span>
                  </div>
                  <el-progress
                    v-if="coveragePercent(candidate.coverage) !== null"
                    data-coverage-bar
                    :percentage="coveragePercent(candidate.coverage)"
                    :stroke-width="8"
                  />
                </div>
              </div>
              <p v-if="turn.coverageNote" data-coverage-note class="chat__coverage-note">
                {{ turn.coverageNote }}
              </p>
              <div v-if="turn.degraded.length" data-degraded class="chat__degraded">
                <el-tag
                  v-for="part in turn.degraded"
                  :key="part"
                  data-degraded-badge
                  type="warning"
                  effect="plain"
                >
                  {{ degradedLabel(part) }}
                </el-tag>
              </div>
            </el-card>
          </template>
        </div>
      </div>

      <el-form class="chat__composer" @submit.prevent="send">
        <el-input
          v-model="draft"
          data-chat-input
          type="textarea"
          :rows="2"
          placeholder="描述你的症状…"
          @keydown.enter.exact.prevent="send"
        />
        <el-button
          type="primary"
          data-send
          native-type="submit"
          :disabled="streaming"
          :loading="streaming"
        >
          发送
        </el-button>
      </el-form>
    </div>
  </section>
</template>

<style scoped>
.chat {
  display: grid;
  grid-template-columns: 260px 1fr;
  gap: 16px;
  padding: 0;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
}

.chat__new {
  width: 100%;
  margin-bottom: 12px;
}

.chat__session-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.chat__session-button {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 10px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 6px;
  background: var(--el-fill-color-blank);
  cursor: pointer;
  text-align: left;
}

.chat__session-button.is-active {
  border-color: var(--el-color-primary);
  color: var(--el-color-primary);
}

.chat__main {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 60vh;
}

.chat__turns {
  display: flex;
  flex-direction: column;
  gap: 16px;
  flex: 1;
}

.chat__turn--user {
  display: flex;
  justify-content: flex-end;
}

.chat__bubble {
  max-width: 72%;
}

.chat__bubble--user {
  background: var(--el-color-primary-light-9);
}

.chat__question {
  margin: 0;
  white-space: pre-wrap;
}

.chat__loading {
  margin: 0;
  color: var(--el-text-color-secondary);
}

.chat__turn-error {
  margin: 8px 0 0;
  color: var(--el-color-danger);
}

.chat__references,
.chat__candidates,
.chat__degraded {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 12px;
}

.chat__degraded {
  flex-direction: row;
  flex-wrap: wrap;
}

.chat__candidate-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.chat__candidate-name {
  font-weight: 600;
}

.chat__candidate-count {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.chat__composer {
  display: flex;
  gap: 12px;
  align-items: flex-end;
  border-top: 1px solid var(--el-border-color-light);
  padding-top: 12px;
}

.chat__error {
  color: var(--el-color-danger);
}
</style>
