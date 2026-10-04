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
    replyConsult: vi.fn(async () => null),
  }
}

describe('DoctorConsultsView (TICKET-019)', () => {
  it('lists claimable tickets with the patient and decoded complaint', async () => {
    const wrapper = mount(DoctorConsultsView, {
      props: { client: fakeClient({ tickets: [row()] }) },
    })
    await flushPromises()

    const rows = wrapper.findAll('[data-consult-row]')
    expect(rows).toHaveLength(1)
    expect(rows[0].text()).toContain('李四')
    expect(rows[0].text()).toContain('咳嗽')
    expect(rows[0].text()).toContain('一周，夜间加重')
  })

  it('claims and replies through the client, then reloads (先到先得)', async () => {
    const client = fakeClient({ tickets: [row()] })
    const wrapper = mount(DoctorConsultsView, { props: { client } })
    await flushPromises()

    await wrapper.find('[data-reply-input]').setValue('请多休息，必要时就诊。')
    await wrapper.find('[data-reply-submit]').trigger('click')
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

    await wrapper.find('[data-reply-submit]').trigger('click')
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
})
