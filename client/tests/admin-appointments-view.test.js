import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import AdminAppointmentsView from '../src/views/AdminAppointmentsView.vue'

function pagePayload(items, { total = items.length, page = 1, page_size = 10 } = {}) {
  return { items, total, page, page_size }
}

function row(overrides = {}) {
  return {
    id: 1,
    user_id: 1,
    user_name: '张三',
    doctor_id: 1,
    doctor_name: '李医生',
    department_id: 2,
    visit_date: '2026-10-20',
    time_slot: '上午',
    status: 0,
    remark: '',
    ...overrides,
  }
}

function fakeClient({ pages = [], fail, updateError } = {}) {
  let index = 0
  return {
    adminAppointments: vi.fn(async () => {
      if (fail) throw fail
      const result = pages[Math.min(index, pages.length - 1)] ?? pagePayload([])
      index += 1
      return result
    }),
    updateAppointmentStatus: vi.fn(async () => {
      if (updateError) throw updateError
      return null
    }),
    deleteAppointment: vi.fn(async () => null),
  }
}

describe('AdminAppointmentsView list (TICKET-017)', () => {
  it('renders the appointments with both names and the status label', async () => {
    const client = fakeClient({ pages: [pagePayload([row({ status: 3 })])] })
    const wrapper = mount(AdminAppointmentsView, { props: { client } })
    await flushPromises()

    const rows = wrapper.findAll('[data-appointment-row]')
    expect(rows).toHaveLength(1)
    expect(rows[0].text()).toContain('张三')
    expect(rows[0].text()).toContain('李医生')
    expect(rows[0].find('[data-status]').text()).toBe('已取消')
  })

  it('shows an empty state and reports the failure when the list cannot load (AC-F-12)', async () => {
    const failure = Object.assign(new Error('无法加载'), { status: 500 })
    const wrapper = mount(AdminAppointmentsView, {
      props: { client: fakeClient({ fail: failure }) },
    })
    await flushPromises()

    expect(wrapper.find('[data-error]').text()).toContain('加载失败')
    expect(wrapper.findAll('[data-appointment-row]')).toHaveLength(0)
    expect(wrapper.emitted('error')).toHaveLength(1)
  })

  it('filters by department, date, status and keyword, returning to page 1', async () => {
    const client = fakeClient({ pages: [pagePayload([])] })
    const wrapper = mount(AdminAppointmentsView, { props: { client } })
    await flushPromises()

    await wrapper.find('[data-filter-keyword]').setValue('张三')
    await wrapper.find('[data-filter-department-id]').setValue('3')
    await wrapper.find('[data-filter-visit-date]').setValue('2026-10-20')
    await wrapper.find('[data-filter-status]').setValue('1')
    await wrapper.find('[data-filter-form]').trigger('submit.prevent')
    await flushPromises()

    expect(client.adminAppointments).toHaveBeenLastCalledWith(
      expect.objectContaining({
        page: 1,
        keyword: '张三',
        department_id: 3,
        visit_date: '2026-10-20',
        status: 1,
      })
    )
  })
})

describe('AdminAppointmentsView actions (TICKET-017)', () => {
  it('updates a status through the client and reloads', async () => {
    const client = fakeClient({ pages: [pagePayload([row({ id: 8, status: 0 })])] })
    const wrapper = mount(AdminAppointmentsView, { props: { client } })
    await flushPromises()

    await wrapper.find('[data-set-status="2"]').trigger('click')
    await flushPromises()

    expect(client.updateAppointmentStatus).toHaveBeenCalledWith(8, 2)
    expect(client.adminAppointments).toHaveBeenCalledTimes(2)
  })

  it('steps back a page when the last row of a page is deleted (AC-F-12)', async () => {
    const client = fakeClient({
      pages: [
        pagePayload([row({ id: 11 })], { total: 11, page: 1 }),
        pagePayload([row({ id: 11 })], { total: 11, page: 2 }),
        pagePayload([row({ id: 1 })], { total: 10, page: 1 }),
      ],
    })
    const wrapper = mount(AdminAppointmentsView, { props: { client } })
    await flushPromises()
    await wrapper.find('[data-next]').trigger('click')
    await flushPromises()
    expect(client.adminAppointments).toHaveBeenLastCalledWith(
      expect.objectContaining({ page: 2 })
    )

    await wrapper.find('[data-delete]').trigger('click')
    await flushPromises()

    expect(client.deleteAppointment).toHaveBeenCalledWith(11)
    expect(client.adminAppointments).toHaveBeenLastCalledWith(
      expect.objectContaining({ page: 1 })
    )
  })
})
