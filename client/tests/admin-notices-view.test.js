import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import AdminNoticesView from '../src/views/AdminNoticesView.vue'

function row(overrides = {}) {
  return {
    id: 1,
    title: '系统维护公告',
    content: '今晚停机维护',
    status: 1,
    ...overrides,
  }
}

function fakeClient({ items = [], total, pageItems, createError } = {}) {
  const pages = pageItems ?? items
  return {
    adminNotices: vi.fn(async ({ page = 1 } = {}) => ({
      items: pages,
      total: total ?? items.length,
      page,
      page_size: 10,
    })),
    createNotice: vi.fn(async () => {
      if (createError) throw createError
      return { id: 99 }
    }),
    updateNotice: vi.fn(async () => null),
    deleteNotice: vi.fn(async () => null),
  }
}

describe('AdminNoticesView list (TICKET-021)', () => {
  it('renders the notice title and the published label', async () => {
    const client = fakeClient({ items: [row(), row({ id: 2, status: 0 })] })
    const wrapper = mount(AdminNoticesView, { props: { client } })
    await flushPromises()

    const rows = wrapper.findAll('[data-notice-row]')
    expect(rows).toHaveLength(2)
    expect(rows[0].text()).toContain('已发布')
    expect(rows[1].text()).toContain('已下架')
  })

  it('shows the empty state and reports a failed load', async () => {
    const failure = Object.assign(new Error('无法加载'), { status: 500 })
    const client = fakeClient()
    client.adminNotices = vi.fn(async () => {
      throw failure
    })
    const wrapper = mount(AdminNoticesView, { props: { client } })
    await flushPromises()

    expect(wrapper.find('[data-error]').text()).toContain('加载失败')
    expect(wrapper.findAll('[data-notice-row]')).toHaveLength(0)
    expect(wrapper.emitted('error')).toHaveLength(1)
  })
})

describe('AdminNoticesView create/edit/delete (TICKET-021)', () => {
  it('requires a title before calling the client', async () => {
    const client = fakeClient()
    const wrapper = mount(AdminNoticesView, { props: { client } })
    await flushPromises()

    await wrapper.find('[data-notice-form]').trigger('submit.prevent')
    await flushPromises()

    expect(wrapper.find('[data-form-error]').text()).toContain('必填')
    expect(client.createNotice).not.toHaveBeenCalled()
  })

  it('creates a notice with the default published status', async () => {
    const client = fakeClient()
    const wrapper = mount(AdminNoticesView, { props: { client } })
    await flushPromises()

    await wrapper.find('[data-title]').setValue('新公告')
    await wrapper.find('[data-content]').setValue('正文')
    await wrapper.find('[data-notice-form]').trigger('submit.prevent')
    await flushPromises()

    expect(client.createNotice).toHaveBeenCalledWith({
      title: '新公告',
      content: '正文',
      status: 1,
    })
    expect(client.adminNotices).toHaveBeenCalledTimes(2)
  })

  it('edits a notice in place, taking it offline', async () => {
    const client = fakeClient({ items: [row({ id: 9, status: 1 })] })
    const wrapper = mount(AdminNoticesView, { props: { client } })
    await flushPromises()

    await wrapper.find('[data-edit="9"]').trigger('click')
    await flushPromises()
    await wrapper.find('[data-status]').setValue('0')
    await wrapper.find('[data-notice-form]').trigger('submit.prevent')
    await flushPromises()

    expect(client.updateNotice).toHaveBeenCalledWith(9, {
      title: '系统维护公告',
      content: '今晚停机维护',
      status: 0,
    })
  })

  it('deletes a notice through the client and reloads', async () => {
    const client = fakeClient({ items: [row({ id: 9 })] })
    const wrapper = mount(AdminNoticesView, { props: { client } })
    await flushPromises()

    await wrapper.find('[data-delete="9"]').trigger('click')
    await flushPromises()

    expect(client.deleteNotice).toHaveBeenCalledWith(9)
    expect(client.adminNotices).toHaveBeenCalledTimes(2)
  })

  it('steps back a page when the last row on the page is deleted', async () => {
    const client = fakeClient({ items: [row({ id: 9 })], total: 11 })
    const wrapper = mount(AdminNoticesView, { props: { client } })
    await flushPromises()

    await wrapper.find('[data-next]').trigger('click')
    await flushPromises()

    await wrapper.find('[data-delete="9"]').trigger('click')
    await flushPromises()

    expect(client.adminNotices).toHaveBeenLastCalledWith({
      page: 1,
      page_size: 10,
      keyword: undefined,
    })
  })
})
