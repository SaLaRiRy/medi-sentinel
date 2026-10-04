import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import ConsultView from '../src/views/ConsultView.vue'

function row(overrides = {}) {
  return {
    id: 1,
    user_id: 1,
    user_name: '张三',
    doctor_id: null,
    doctor_name: null,
    chief_complaint: '头痛：三天，伴发热',
    status: 0,
    create_time: '2026-10-20 09:00:00',
    update_time: '2026-10-20 09:00:00',
    replies: [],
    ...overrides,
  }
}

function fakeClient({ tickets = [], loadError } = {}) {
  return {
    myConsults: vi.fn(async () => {
      if (loadError) throw loadError
      return tickets
    }),
    createConsult: vi.fn(async () => ({ id: 9 })),
  }
}

describe('ConsultView (TICKET-019)', () => {
  it('renders my tickets, decoding the complaint and labelling the status', async () => {
    const wrapper = mount(ConsultView, {
      props: { client: fakeClient({ tickets: [row()] }) },
    })
    await flushPromises()

    const rows = wrapper.findAll('[data-consult-row]')
    expect(rows).toHaveLength(1)
    expect(rows[0].text()).toContain('头痛')
    expect(rows[0].text()).toContain('三天，伴发热')
    expect(rows[0].text()).toContain('待回复')
  })

  it('encodes the title and body into one chief complaint on submit (AC-F-15)', async () => {
    const client = fakeClient()
    const wrapper = mount(ConsultView, { props: { client } })
    await flushPromises()

    await wrapper.find('[data-complaint-title]').setValue('咳嗽')
    await wrapper.find('[data-complaint-body]').setValue('一周')
    await wrapper.find('[data-doctor-id]').setValue('2')
    await wrapper.find('[data-consult-form]').trigger('submit')
    await flushPromises()

    expect(client.createConsult).toHaveBeenCalledWith({
      doctor_id: 2,
      chief_complaint: '咳嗽：一周',
    })
  })

  it('requires a title before submitting', async () => {
    const client = fakeClient()
    const wrapper = mount(ConsultView, { props: { client } })
    await flushPromises()

    await wrapper.find('[data-complaint-body]').setValue('一周')
    await wrapper.find('[data-consult-form]').trigger('submit')
    await flushPromises()

    expect(wrapper.find('[data-form-error]').exists()).toBe(true)
    expect(client.createConsult).not.toHaveBeenCalled()
  })

  it('shows the empty state when the patient has no tickets', async () => {
    const wrapper = mount(ConsultView, { props: { client: fakeClient() } })
    await flushPromises()

    expect(wrapper.find('[data-empty]').text()).toContain('暂无')
  })

  it('shows an empty state and reports the failure when the list cannot load (AC-F-12)', async () => {
    const failure = Object.assign(new Error('无法加载'), { status: 500 })
    const wrapper = mount(ConsultView, {
      props: { client: fakeClient({ loadError: failure }) },
    })
    await flushPromises()

    expect(wrapper.find('[data-error]').text()).toContain('加载失败')
    expect(wrapper.findAll('[data-consult-row]')).toHaveLength(0)
    expect(wrapper.emitted('error')).toHaveLength(1)
  })
})
