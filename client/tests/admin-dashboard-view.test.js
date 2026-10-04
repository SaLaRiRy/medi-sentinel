import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import AdminDashboardView from '../src/views/AdminDashboardView.vue'

function fakeClient(overrides = {}) {
  return {
    statOverview: vi.fn(async () => ({
      user_count: 3,
      doctor_count: 2,
      session_count: 5,
      appointment_count: 4,
      knowledge_count: 1,
      article_count: 2,
    })),
    consultTrend: vi.fn(async () => [
      { date: '2026-10-01', count: 2 },
      { date: '2026-10-02', count: 0 },
    ]),
    userGrowth: vi.fn(async () => [{ date: '2026-10-01', count: 1 }]),
    appointmentsByDepartment: vi.fn(async () => [
      { name: '内科', value: 4 },
      { name: '外科', value: 0 },
    ]),
    knowledgeTypes: vi.fn(async () => [
      { name: 'markdown', value: 3 },
      { name: 'medical-imaging', value: 1 },
    ]),
    ...overrides,
  }
}

describe('AdminDashboardView (TICKET-022)', () => {
  it('renders the six operating totals', async () => {
    const wrapper = mount(AdminDashboardView, { props: { client: fakeClient() } })
    await flushPromises()

    const text = wrapper.find('[data-overview]').text()
    expect(text).toContain('患者')
    expect(text).toContain('5') // AI 会话数
    expect(wrapper.findAll('[data-overview-stat]')).toHaveLength(6)
  })

  it('renders the trends and distributions, with a fallback label for an unknown type', async () => {
    const wrapper = mount(AdminDashboardView, { props: { client: fakeClient() } })
    await flushPromises()

    expect(wrapper.findAll('[data-consult-trend-row]')).toHaveLength(2)
    expect(wrapper.findAll('[data-user-growth-row]')).toHaveLength(1)
    const departmentRows = wrapper.findAll('[data-department-row]')
    expect(departmentRows[1].text()).toContain('外科')
    expect(departmentRows[1].text()).toContain('0')

    const knowledgeRows = wrapper.findAll('[data-knowledge-row]')
    expect(knowledgeRows[0].text()).toContain('Markdown')
    expect(knowledgeRows[1].text()).toContain('未知类型')
  })

  it('reloads the trends when the day window changes', async () => {
    const client = fakeClient()
    const wrapper = mount(AdminDashboardView, { props: { client } })
    await flushPromises()

    // TICKET-030: el-select is a component; drive its model.
    await wrapper.findComponent('[data-days]').setValue('30')
    await flushPromises()

    expect(client.consultTrend).toHaveBeenLastCalledWith(30)
    expect(client.userGrowth).toHaveBeenLastCalledWith(30)
  })

  it('shows the error state and reports a failed load', async () => {
    const failure = Object.assign(new Error('无法加载'), { status: 500 })
    const client = fakeClient({
      statOverview: vi.fn(async () => {
        throw failure
      }),
    })
    const wrapper = mount(AdminDashboardView, { props: { client } })
    await flushPromises()

    expect(wrapper.find('[data-error]').text()).toContain('加载失败')
    expect(wrapper.find('[data-overview]').exists()).toBe(false)
    expect(wrapper.emitted('error')).toHaveLength(1)
  })
})
