import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import ChatView from '../src/views/ChatView.vue'

function fakeClient({ sessions = [], messages = {}, frames = [], failSessions, failStream } = {}) {
  return {
    chatSessions: vi.fn(async () => {
      if (failSessions) throw failSessions
      return sessions
    }),
    chatMessages: vi.fn(async (id) => messages[id] ?? []),
    sendChat: vi.fn(async function* generate() {
      if (failStream) throw failStream
      for (const frame of frames) yield frame
    }),
  }
}

async function send(wrapper, text = '我头疼') {
  await wrapper.find('[data-chat-input]').setValue(text)
  await wrapper.find('form').trigger('submit.prevent')
  await flushPromises()
}

describe('ChatView session list and history (TICKET-014)', () => {
  it('loads and shows the patient sessions on mount', async () => {
    const client = fakeClient({
      sessions: [
        { id: 2, title: '第二段对话', message_count: 2 },
        { id: 1, title: '第一段对话', message_count: 2 },
      ],
    })
    const wrapper = mount(ChatView, { props: { client } })
    await flushPromises()

    const items = wrapper.findAll('[data-session-item]')
    expect(items).toHaveLength(2)
    expect(items[0].text()).toContain('第二段对话')
  })

  it('opens a session and renders its history as Markdown', async () => {
    const client = fakeClient({
      sessions: [{ id: 3, title: '旧会话', message_count: 2 }],
      messages: {
        3: [
          { id: 1, role: 'user', content: '旧问题' },
          {
            id: 2,
            role: 'assistant',
            content: '**旧回答**',
            references: [{ index: 1, file_name: '指南.md', snippet: '片段' }],
            graph: [],
          },
        ],
      },
    })
    const wrapper = mount(ChatView, { props: { client } })
    await flushPromises()

    await wrapper.find('[data-session-item] button').trigger('click')
    await flushPromises()

    expect(client.chatMessages).toHaveBeenCalledWith(3)
    const answer = wrapper.find('[data-message="assistant"] [data-answer]')
    expect(answer.html()).toContain('<strong>旧回答</strong>')
    expect(wrapper.find('[data-reference]').text()).toContain('指南.md')
  })
})

describe('ChatView streaming (TICKET-014)', () => {
  it('streams the answer segment by segment and reloads the list for a new session', async () => {
    const client = fakeClient({
      frames: [
        { type: 'session', session_id: 9 },
        { type: 'trace', trace_id: 't' },
        { type: 'route', skills_run: [], skills_skipped: [] },
        { type: 'content', content: '您好，' },
        { type: 'content', content: '建议监测体温。' },
        {
          type: 'done',
          references: [],
          graph: [],
          coverage_note: null,
          degraded: [],
          cost_time: 12,
          trace_id: 't',
        },
      ],
    })
    const wrapper = mount(ChatView, { props: { client } })
    await flushPromises()

    await send(wrapper)

    expect(client.sendChat).toHaveBeenCalledWith({ session_id: null, message: '我头疼' })
    const answer = wrapper.find('[data-message="assistant"] [data-answer]')
    expect(answer.text()).toContain('您好，建议监测体温。')
    // The `session` frame associates the new session, then the list is refreshed.
    expect(client.chatSessions).toHaveBeenCalledTimes(2)
  })

  it('shows the degraded branches the done frame names', async () => {
    const client = fakeClient({
      frames: [
        { type: 'session', session_id: 1 },
        { type: 'trace', trace_id: 't' },
        {
          type: 'done',
          references: [],
          graph: [],
          coverage_note: null,
          degraded: ['retrieval', 'graph'],
          cost_time: 12,
          trace_id: 't',
        },
      ],
    })
    const wrapper = mount(ChatView, { props: { client } })
    await flushPromises()

    await send(wrapper)

    const badges = wrapper.findAll('[data-degraded-badge]')
    expect(badges.map((badge) => badge.text())).toEqual(['知识库检索降级', '图谱推理降级'])
  })
})

describe('ChatView safety gate (AC-F-06)', () => {
  it('shows only the safety card on a red-flag intercept', async () => {
    const client = fakeClient({
      frames: [
        { type: 'session', session_id: 5 },
        { type: 'trace', trace_id: 't' },
        {
          type: 'safety',
          decision: 'intercept',
          level: 'emergency',
          red_flags: [
            { id: 'chest-pain', label: '急性胸痛', matched_surface: '胸口剧痛', severity: 'emergency' },
          ],
          message: '检测到需要立即处理的急症信号：急性胸痛。请立即拨打 120。',
          suggested_action: '立即拨打 120 或前往最近的急诊科就诊。',
        },
        {
          type: 'done',
          references: [],
          graph: [],
          coverage_note: null,
          degraded: [],
          cost_time: 3,
          trace_id: 't',
        },
      ],
    })
    const wrapper = mount(ChatView, { props: { client } })
    await flushPromises()

    await send(wrapper, '胸口剧痛，出冷汗')

    expect(wrapper.find('[data-safety-card]').exists()).toBe(true)
    expect(wrapper.find('[data-safety-message]').text()).toContain('请立即拨打 120')
    expect(wrapper.find('[data-red-flag]').text()).toContain('急性胸痛')
    // No generated-content placeholder, references or candidates on this turn.
    const assistantTurn = wrapper.find('[data-message="assistant"]')
    expect(assistantTurn.find('[data-answer]').exists()).toBe(false)
    expect(assistantTurn.find('[data-references]').exists()).toBe(false)
    expect(assistantTurn.find('[data-candidates]').exists()).toBe(false)
    expect(wrapper.find('[data-loading]').exists()).toBe(false)
  })
})

describe('ChatView done frame payload (AC-F-14)', () => {
  it('sorts candidates by coverage and hides the bar when coverage is missing', async () => {
    const client = fakeClient({
      frames: [
        { type: 'session', session_id: 1 },
        { type: 'trace', trace_id: 't' },
        {
          type: 'done',
          references: [{ index: 1, file_name: '指南.md', snippet: '片段' }],
          graph: [
            { disease: '低覆盖', match_count: 1, coverage: 0.2, department: null, matched_symptoms: [] },
            { disease: '高覆盖', match_count: 3, coverage: 0.8, department: '呼吸内科', matched_symptoms: [] },
            { disease: '无覆盖', match_count: 1, coverage: null, department: null, matched_symptoms: [] },
          ],
          coverage_note: null,
          degraded: [],
          cost_time: 12,
          trace_id: 't',
        },
      ],
    })
    const wrapper = mount(ChatView, { props: { client } })
    await flushPromises()

    await send(wrapper)

    const order = wrapper.findAll('[data-candidate]').map((el) => el.attributes('data-disease'))
    expect(order).toEqual(['高覆盖', '低覆盖', '无覆盖'])
    expect(wrapper.findAll('[data-coverage-bar]')).toHaveLength(2)
    expect(wrapper.find('[data-candidate="无覆盖"]').text()).toContain('-')
  })
})

describe('ChatView error states (issue: 可理解的错误状态而非空白)', () => {
  it('shows the error frame message and clears the loading state', async () => {
    const client = fakeClient({
      frames: [
        { type: 'session', session_id: 1 },
        { type: 'trace', trace_id: 't' },
        { type: 'error', code: 503, message: '生成失败：上游不可用', trace_id: 't' },
      ],
    })
    const wrapper = mount(ChatView, { props: { client } })
    await flushPromises()

    await send(wrapper)

    expect(wrapper.find('[data-turn-error]').text()).toContain('上游不可用')
    expect(wrapper.find('[data-loading]').exists()).toBe(false)
  })

  it('shows a readable error state, not a blank page, when the backend is unreachable', async () => {
    const failure = Object.assign(new Error('网络异常'), { status: 500 })
    const client = fakeClient({ failSessions: failure })
    const wrapper = mount(ChatView, { props: { client } })
    await flushPromises()

    expect(wrapper.find('[data-error]').text()).toContain('无法加载')
    expect(wrapper.emitted('error')).toHaveLength(1)
  })

  it('catches a stream that breaks mid-answer', async () => {
    const failure = Object.assign(new Error('连接中断'), { status: 0 })
    const client = fakeClient({ failStream: failure })
    const wrapper = mount(ChatView, { props: { client } })
    await flushPromises()

    await send(wrapper)

    expect(wrapper.find('[data-turn-error]').text()).toContain('连接中断')
    expect(wrapper.find('[data-loading]').exists()).toBe(false)
  })
})
