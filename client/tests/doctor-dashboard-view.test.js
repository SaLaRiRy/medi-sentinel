import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import DoctorDashboardView from '../src/views/DoctorDashboardView.vue'

function fakeClient(overrides = {}) {
  return {
    statOverview: vi.fn(async () => ({
      pending_consults: 2,
      today_appointments: 1,
      replied_consults: 3,
      total_patients: 4,
    })),
    ...overrides,
  }
}

describe('DoctorDashboardView (TICKET-022)', () => {
  it('renders the four workbench counts', async () => {
    const wrapper = mount(DoctorDashboardView, { props: { client: fakeClient() } })
    await flushPromises()

    const text = wrapper.find('[data-overview]').text()
    expect(text).toContain('待处理工单')
    expect(text).toContain('2')
    expect(text).toContain('今日预约')
    expect(text).toContain('患者总数')
    expect(wrapper.findAll('[data-overview-stat]')).toHaveLength(4)
  })

  it('shows the error state and reports a failed load', async () => {
    const failure = Object.assign(new Error('无法加载'), { status: 403 })
    const client = fakeClient({
      statOverview: vi.fn(async () => {
        throw failure
      }),
    })
    const wrapper = mount(DoctorDashboardView, { props: { client } })
    await flushPromises()

    expect(wrapper.find('[data-error]').text()).toContain('加载失败')
    expect(wrapper.emitted('error')).toHaveLength(1)
  })
})
