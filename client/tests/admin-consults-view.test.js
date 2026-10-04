import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import AdminConsultsView from '../src/views/AdminConsultsView.vue'

function row(overrides = {}) {
  return {
    id: 1,
    user_id: 1,
    user_name: '张三',
    doctor_id: 1,
    doctor_name: '李医生',
    chief_complaint: '头痛：三天',
    status: 1,
    create_time: '2026-10-20 09:00:00',
    update_time: '2026-10-20 09:00:00',
    replies: [],
    ...overrides,
  }
}

function fakeClient(pages) {
  return {
    adminConsults: vi.fn(async ({ page, page_size, status } = {}) => {
      const key = `${page}:${page_size}:${status ?? ''}`
      return pages[key] ?? { items: [], total: 0, page, page_size }
    }),
    deleteConsult: vi.fn(async () => null),
  }
}

describe('AdminConsultsView (TICKET-019)', () => {
  it('renders the paginated rows with patient, status label and replies count', async () => {
    const client = fakeClient({
      '1:10:': { items: [row()], total: 1, page: 1, page_size: 10 },
    })
    const wrapper = mount(AdminConsultsView, { props: { client } })
    await flushPromises()

    // TICKET-030: ElTable rows are grouped by the stable `.el-table__row`.
    const rows = wrapper.findAll('.el-table__row')
    expect(rows).toHaveLength(1)
    expect(rows[0].text()).toContain('张三')
    expect(rows[0].text()).toContain('李医生')
    expect(rows[0].text()).toContain('已回复')
    expect(client.adminConsults).toHaveBeenCalledWith({ page: 1, page_size: 10 })
  })

  it('filters by status through the query', async () => {
    const client = fakeClient({
      '1:10:': { items: [row()], total: 1, page: 1, page_size: 10 },
      '1:10:0': { items: [], total: 0, page: 1, page_size: 10 },
    })
    const wrapper = mount(AdminConsultsView, { props: { client } })
    await flushPromises()

    // TICKET-030: el-select is a component; drive its model.
    await wrapper.findComponent('[data-status-filter]').setValue('0')
    await flushPromises()

    expect(client.adminConsults).toHaveBeenLastCalledWith({
      page: 1,
      page_size: 10,
      status: 0,
    })
  })

  it('deletes a ticket and falls back a page when the last row goes (AC-F-12)', async () => {
    const client = fakeClient({
      '1:10:': { items: [row({ id: 41 })], total: 11, page: 1, page_size: 10 },
      '2:10:': { items: [row({ id: 42 })], total: 11, page: 2, page_size: 10 },
    })
    const wrapper = mount(AdminConsultsView, { props: { client } })
    await flushPromises()
    await wrapper.find('.btn-next').trigger('click')
    await flushPromises()

    await wrapper.find('[data-delete="42"]').trigger('click')
    await flushPromises()

    expect(client.deleteConsult).toHaveBeenCalledWith(42)
    expect(client.adminConsults).toHaveBeenLastCalledWith({ page: 1, page_size: 10 })
  })

  it('shows the empty state when there are no tickets', async () => {
    const wrapper = mount(AdminConsultsView, { props: { client: fakeClient({}) } })
    await flushPromises()

    expect(wrapper.find('[data-empty]').text()).toContain('暂无')
  })
})
