import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import { ElDatePicker } from 'element-plus'

import AdminAppointmentsView from '../src/views/AdminAppointmentsView.vue'
import { settle } from './helpers/mount.js'

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

// Phase 2: secondary status actions and delete now live in the row's 更多 dropdown.
async function openMore(wrapper) {
  await wrapper.find('.el-table__row').find('[data-more]').trigger('click')
  await settle()
}

describe('AdminAppointmentsView list (TICKET-017)', () => {
  it('renders the appointments with both names and the status label', async () => {
    const client = fakeClient({ pages: [pagePayload([row({ status: 3 })])] })
    const wrapper = mount(AdminAppointmentsView, { props: { client } })
    await flushPromises()

    // TICKET-030: ElTable rows are grouped by the stable `.el-table__row`.
    const rows = wrapper.findAll('.el-table__row')
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
    expect(wrapper.findAll('.el-table__row')).toHaveLength(0)
    expect(wrapper.emitted('error')).toHaveLength(1)
  })

  it('filters by department, date, status and keyword, returning to page 1', async () => {
    const client = fakeClient({ pages: [pagePayload([])] })
    const wrapper = mount(AdminAppointmentsView, { props: { client } })
    await flushPromises()

    await wrapper.find('[data-filter-keyword]').setValue('张三')
    await wrapper.find('[data-filter-department-id]').setValue('3')
    // TICKET-030: el-date-picker / el-select are components; drive their models.
    await wrapper.findComponent(ElDatePicker).setValue('2026-10-20')
    await wrapper.findComponent('[data-filter-status]').setValue('1')
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

    // TICKET-030: scope row actions to the stable `.el-table__row` — ElTable
    // renders a hidden measuring copy of every column's slot.
    await openMore(wrapper)
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
    await wrapper.find('.btn-next').trigger('click')
    await flushPromises()
    expect(client.adminAppointments).toHaveBeenLastCalledWith(
      expect.objectContaining({ page: 2 })
    )

    await openMore(wrapper)
    await wrapper.find('[data-delete]').trigger('click')
    await flushPromises()

    expect(client.deleteAppointment).toHaveBeenCalledWith(11)
    expect(client.adminAppointments).toHaveBeenLastCalledWith(
      expect.objectContaining({ page: 1 })
    )
  })
})
