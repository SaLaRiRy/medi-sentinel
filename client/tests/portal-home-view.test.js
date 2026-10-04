import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import PortalHomeView from '../src/views/PortalHomeView.vue'

function noticeRow(overrides = {}) {
  return {
    id: 1,
    title: '系统维护公告',
    content: '今晚停机维护',
    status: 1,
    ...overrides,
  }
}

function fakeClient({ notices = [], detail, listError, detailError, overview } = {}) {
  return {
    notices: vi.fn(async () => {
      if (listError) throw listError
      return notices
    }),
    notice: vi.fn(async () => {
      if (detailError) throw detailError
      return detail ?? noticeRow()
    }),
    userOverview: vi.fn(
      async () =>
        overview ?? {
          consult_count: 0,
          appointment_count: 0,
          record_count: 0,
          session_count: 0,
        }
    ),
  }
}

describe('PortalHomeView patient overview (TICKET-022)', () => {
  it('renders the four personal counts', async () => {
    const client = fakeClient({
      overview: {
        consult_count: 2,
        appointment_count: 1,
        record_count: 3,
        session_count: 4,
      },
    })
    const wrapper = mount(PortalHomeView, { props: { client } })
    await flushPromises()

    const overview = wrapper.find('[data-user-overview]').text()
    expect(overview).toContain('人工问诊')
    expect(overview).toContain('健康档案')
    expect(wrapper.findAll('[data-overview-stat]')).toHaveLength(4)
  })
})

describe('PortalHomeView notices (TICKET-021)', () => {
  it('renders the published notices', async () => {
    const client = fakeClient({
      notices: [noticeRow(), noticeRow({ id: 2, title: '停诊通知' })],
    })
    const wrapper = mount(PortalHomeView, { props: { client } })
    await flushPromises()

    const rows = wrapper.findAll('[data-notice-row]')
    expect(rows).toHaveLength(2)
    expect(rows[1].text()).toContain('停诊通知')
  })

  it('shows the empty state and reports a failed load', async () => {
    const failure = Object.assign(new Error('无法加载'), { status: 500 })
    const client = fakeClient({ listError: failure })
    const wrapper = mount(PortalHomeView, { props: { client } })
    await flushPromises()

    expect(wrapper.find('[data-error]').text()).toContain('加载失败')
    expect(wrapper.findAll('[data-notice-row]')).toHaveLength(0)
    expect(wrapper.emitted('error')).toHaveLength(1)
  })

  it('opens a notice detail and returns to the list', async () => {
    const client = fakeClient({
      notices: [noticeRow({ id: 4 })],
      detail: { id: 4, title: '系统维护公告', content: '详情正文' },
    })
    const wrapper = mount(PortalHomeView, { props: { client } })
    await flushPromises()

    await wrapper.find('[data-open="4"]').trigger('click')
    await flushPromises()

    expect(client.notice).toHaveBeenCalledWith(4)
    expect(wrapper.find('[data-notice-detail]').text()).toContain('详情正文')

    await wrapper.find('[data-back]').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-notice-detail]').exists()).toBe(false)
  })
})
