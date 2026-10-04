import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import RecordsView from '../src/views/RecordsView.vue'

function row(overrides = {}) {
  return {
    id: 1,
    user_id: 1,
    user_name: '张三',
    doctor_id: 1,
    doctor_name: '李医生',
    record_type: '门诊记录',
    diagnosis: '上呼吸道感染',
    treatment: '多休息',
    prescription: '感冒灵',
    visit_date: '2026-10-20',
    create_time: '2026-10-20 09:00:00',
    update_time: '2026-10-20 09:00:00',
    ...overrides,
  }
}

function fakeClient({ records = [], loadError } = {}) {
  return {
    myRecords: vi.fn(async () => {
      if (loadError) throw loadError
      return records
    }),
  }
}

describe('RecordsView (TICKET-018)', () => {
  it('renders my records read-only', async () => {
    const wrapper = mount(RecordsView, {
      props: { client: fakeClient({ records: [row()] }) },
    })
    await flushPromises()

    const rows = wrapper.findAll('[data-record-row]')
    expect(rows).toHaveLength(1)
    expect(rows[0].text()).toContain('门诊记录')
    expect(rows[0].text()).toContain('上呼吸道感染')
    expect(rows[0].text()).toContain('多休息')
    expect(rows[0].text()).toContain('感冒灵')
    expect(rows[0].text()).toContain('2026-10-20')
    expect(rows[0].text()).toContain('李医生')
  })

  it('shows the empty state when the patient has no records', async () => {
    const wrapper = mount(RecordsView, { props: { client: fakeClient() } })
    await flushPromises()

    expect(wrapper.find('[data-empty]').text()).toContain('暂无')
  })

  it('shows an empty state and reports the failure when the list cannot load (AC-F-12)', async () => {
    const failure = Object.assign(new Error('无法加载'), { status: 500 })
    const wrapper = mount(RecordsView, {
      props: { client: fakeClient({ loadError: failure }) },
    })
    await flushPromises()

    expect(wrapper.find('[data-error]').text()).toContain('加载失败')
    expect(wrapper.findAll('[data-record-row]')).toHaveLength(0)
    expect(wrapper.emitted('error')).toHaveLength(1)
  })
})
