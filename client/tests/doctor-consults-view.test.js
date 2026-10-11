import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import DoctorConsultsView from '../src/views/DoctorConsultsView.vue'

function row(overrides = {}) {
  return {
    id: 3,
    user_id: 2,
    user_name: '李四',
    doctor_id: null,
    doctor_name: null,
    chief_complaint: '咳嗽：一周，夜间加重',
    status: 0,
    create_time: '2026-10-20 09:00:00',
    update_time: '2026-10-20 09:00:00',
    replies: [],
    ...overrides,
  }
}

function fakeClient({ tickets = [], loadError } = {}) {
  return {
    pendingConsults: vi.fn(async () => {
      if (loadError) throw loadError
      return tickets
    }),
    consultAiContext: vi.fn(async () => ({
      consult_id: 3,
      session_id: 12,
      chief_complaint: '咳嗽：一周，夜间加重',
      summary: '建议先休息，必要时就诊。',
      graph: [
        {
          disease: '急性支气管炎',
          match_count: 2,
          coverage: 0.5,
          department: '呼吸内科',
          matched_symptoms: ['咳嗽', '夜间加重'],
        },
      ],
      references: [{ index: 1, file_name: '感冒与流感指南.md', snippet: '咳嗽……' }],
    })),
    createRecordFromConsult: vi.fn(async () => ({ id: 5, source: 'ai' })),
    replyConsult: vi.fn(async () => null),
  }
}

describe('DoctorConsultsView (TICKET-019)', () => {
  it('lists claimable tickets with the patient and decoded complaint', async () => {
    const wrapper = mount(DoctorConsultsView, {
      props: { client: fakeClient({ tickets: [row()] }) },
    })
    await flushPromises()

    // TICKET-029: ElTable rows are grouped by the stable `.el-table__row`.
    const rows = wrapper.findAll('.el-table__row')
    expect(rows).toHaveLength(1)
    expect(rows[0].text()).toContain('李四')
    expect(rows[0].text()).toContain('咳嗽')
    expect(rows[0].text()).toContain('一周，夜间加重')
  })

  it('claims and replies through the client, then reloads (先到先得)', async () => {
    const client = fakeClient({ tickets: [row()] })
    const wrapper = mount(DoctorConsultsView, { props: { client } })
    await flushPromises()

    const tableRow = wrapper.find('.el-table__row')
    await tableRow.find('[data-reply-input]').setValue('请多休息，必要时就诊。')
    await tableRow.find('[data-reply-submit]').trigger('click')
    await flushPromises()

    expect(client.replyConsult).toHaveBeenCalledWith(3, {
      consult_id: 3,
      content: '请多休息，必要时就诊。',
    })
    expect(client.pendingConsults).toHaveBeenCalledTimes(2)
  })

  it('ignores an empty reply', async () => {
    const client = fakeClient({ tickets: [row()] })
    const wrapper = mount(DoctorConsultsView, { props: { client } })
    await flushPromises()

    await wrapper.find('.el-table__row').find('[data-reply-submit]').trigger('click')
    await flushPromises()

    expect(client.replyConsult).not.toHaveBeenCalled()
  })

  it('shows an empty state and reports the failure when loading fails', async () => {
    const failure = Object.assign(new Error('无法加载'), { status: 500 })
    const wrapper = mount(DoctorConsultsView, {
      props: { client: fakeClient({ loadError: failure }) },
    })
    await flushPromises()

    expect(wrapper.find('[data-error]').text()).toContain('加载失败')
    expect(wrapper.emitted('error')).toHaveLength(1)
  })

  it('shows the empty state when there is nothing to claim', async () => {
    const wrapper = mount(DoctorConsultsView, {
      props: { client: fakeClient() },
    })
    await flushPromises()

    expect(wrapper.find('[data-empty]').text()).toContain('暂无')
  })

  it('opens the AI context of a ticket (TICKET-AC-05)', async () => {
    const client = fakeClient({ tickets: [row()] })
    const wrapper = mount(DoctorConsultsView, { props: { client } })
    await flushPromises()

    await wrapper.find('[data-ai-context]').trigger('click')
    await flushPromises()

    expect(client.consultAiContext).toHaveBeenCalledWith(3)
    const dialog = wrapper.text()
    expect(dialog).toContain('AI 问诊上下文')
    expect(dialog).toContain('急性支气管炎')
    expect(dialog).toContain('感冒与流感指南.md')
    expect(dialog).toContain('建议先休息')
  })

  it('reports a failure and shows no context when the call fails', async () => {
    const client = fakeClient({ tickets: [row()] })
    client.consultAiContext = vi.fn(async () => {
      throw Object.assign(new Error('403'), { status: 403 })
    })
    const wrapper = mount(DoctorConsultsView, { props: { client } })
    await flushPromises()

    await wrapper.find('[data-ai-context]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-context-error]').text()).toContain('加载失败')
    expect(wrapper.emitted('error')).toHaveLength(1)
  })

  it('settles the ticket into a record only after the doctor confirms (TICKET-AC-06)', async () => {
    const client = fakeClient({ tickets: [row()] })
    const wrapper = mount(DoctorConsultsView, { props: { client } })
    await flushPromises()
    await wrapper.find('[data-ai-context]').trigger('click')
    await flushPromises()

    // 只提交空表单：不落档案，给出必填提示。
    await wrapper.find('[data-settle-form]').trigger('submit')
    await flushPromises()
    expect(client.createRecordFromConsult).not.toHaveBeenCalled()
    expect(wrapper.find('[data-settle-error]').exists()).toBe(true)

    await wrapper.find('[data-settle-type]').setValue('门诊记录')
    await wrapper.find('[data-settle-diagnosis]').setValue('急性支气管炎')
    await wrapper.find('[data-settle-form]').trigger('submit')
    await flushPromises()

    expect(client.createRecordFromConsult).toHaveBeenCalledWith({
      consult_id: 3,
      record_type: '门诊记录',
      diagnosis: '急性支气管炎',
      source: 'ai',
    })
    expect(wrapper.find('[data-settled]').text()).toContain('已沉淀为档案')
  })
})
