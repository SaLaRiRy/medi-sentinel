import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import AdminArticlesView from '../src/views/AdminArticlesView.vue'

function row(overrides = {}) {
  return {
    id: 1,
    title: '高血压防治',
    category: '健康科普',
    summary: '摘要',
    content: '正文',
    view_count: 3,
    status: 1,
    ...overrides,
  }
}

function fakeClient({
  items = [],
  total,
  pageItems,
  createError,
  deleteError,
} = {}) {
  const pages = pageItems ?? items
  return {
    adminArticles: vi.fn(async ({ page = 1 } = {}) => ({
      items: pages,
      total: total ?? items.length,
      page,
      page_size: 10,
    })),
    createArticle: vi.fn(async () => {
      if (createError) throw createError
      return { id: 99 }
    }),
    updateArticle: vi.fn(async () => null),
    deleteArticle: vi.fn(async () => {
      if (deleteError) throw deleteError
      return null
    }),
  }
}

// Phase 2: the create form lives in a dialog opened from the page header.
async function openCreate(wrapper) {
  await wrapper.find('[data-create]').trigger('click')
  await flushPromises()
}

describe('AdminArticlesView list (TICKET-021)', () => {
  it('renders the article title and the published label', async () => {
    const client = fakeClient({ items: [row(), row({ id: 2, status: 0 })] })
    const wrapper = mount(AdminArticlesView, { props: { client } })
    await flushPromises()

    // TICKET-030: ElTable rows are grouped by the stable `.el-table__row`.
    const rows = wrapper.findAll('.el-table__row')
    expect(rows).toHaveLength(2)
    expect(rows[0].text()).toContain('已发布')
    expect(rows[1].text()).toContain('已下架')
  })

  it('shows the empty state and reports a failed load', async () => {
    const failure = Object.assign(new Error('无法加载'), { status: 500 })
    const client = fakeClient()
    client.adminArticles = vi.fn(async () => {
      throw failure
    })
    const wrapper = mount(AdminArticlesView, { props: { client } })
    await flushPromises()

    expect(wrapper.find('[data-error]').text()).toContain('加载失败')
    expect(wrapper.findAll('.el-table__row')).toHaveLength(0)
    expect(wrapper.emitted('error')).toHaveLength(1)
  })
})

describe('AdminArticlesView create/edit/delete (TICKET-021)', () => {
  it('requires a title before calling the client', async () => {
    const client = fakeClient()
    const wrapper = mount(AdminArticlesView, { props: { client } })
    await flushPromises()

    await openCreate(wrapper)
    await wrapper.find('[data-article-form]').trigger('submit.prevent')
    await flushPromises()

    expect(wrapper.find('[data-form-error]').text()).toContain('必填')
    expect(client.createArticle).not.toHaveBeenCalled()
  })

  it('creates an article with the default published status', async () => {
    const client = fakeClient()
    const wrapper = mount(AdminArticlesView, { props: { client } })
    await flushPromises()

    await openCreate(wrapper)
    await wrapper.find('[data-title]').setValue('新文章')
    // TICKET-030: el-select is a component; drive its model.
    await wrapper.findComponent('[data-category]').setValue('用药指南')
    await wrapper.find('[data-article-form]').trigger('submit.prevent')
    await flushPromises()

    expect(client.createArticle).toHaveBeenCalledWith({
      title: '新文章',
      category: '用药指南',
      status: 1,
    })
    expect(client.adminArticles).toHaveBeenCalledTimes(2)
  })

  it('surfaces a create failure as an error', async () => {
    const failure = Object.assign(new Error('参数校验失败'), { status: 422 })
    const client = fakeClient({ createError: failure })
    const wrapper = mount(AdminArticlesView, { props: { client } })
    await flushPromises()

    await openCreate(wrapper)
    await wrapper.find('[data-title]').setValue('新文章')
    await wrapper.find('[data-article-form]').trigger('submit.prevent')
    await flushPromises()

    expect(wrapper.emitted('error')[0][0]).toBe(failure)
  })

  it('edits an article in place, publishing it', async () => {
    const client = fakeClient({ items: [row({ id: 7, status: 0 })] })
    const wrapper = mount(AdminArticlesView, { props: { client } })
    await flushPromises()

    await wrapper.find('[data-edit="7"]').trigger('click')
    await flushPromises()
    await wrapper.findComponent('[data-status]').setValue('1')
    await wrapper.find('[data-article-form]').trigger('submit.prevent')
    await flushPromises()

    expect(client.updateArticle).toHaveBeenCalledWith(7, {
      title: '高血压防治',
      category: '健康科普',
      summary: '摘要',
      content: '正文',
      status: 1,
    })
  })

  it('deletes an article through the client and reloads', async () => {
    const client = fakeClient({ items: [row({ id: 7 })] })
    const wrapper = mount(AdminArticlesView, { props: { client } })
    await flushPromises()

    await wrapper.find('[data-delete="7"]').trigger('click')
    await flushPromises()

    expect(client.deleteArticle).toHaveBeenCalledWith(7)
    expect(client.adminArticles).toHaveBeenCalledTimes(2)
  })

  it('steps back a page when the last row on the page is deleted', async () => {
    const client = fakeClient({ items: [row({ id: 7 })], total: 11 })
    const wrapper = mount(AdminArticlesView, { props: { client } })
    await flushPromises()

    await wrapper.find('.btn-next').trigger('click')
    await flushPromises()
    expect(client.adminArticles).toHaveBeenLastCalledWith({
      page: 2,
      page_size: 10,
      keyword: undefined,
    })

    await wrapper.find('[data-delete="7"]').trigger('click')
    await flushPromises()

    expect(client.adminArticles).toHaveBeenLastCalledWith({
      page: 1,
      page_size: 10,
      keyword: undefined,
    })
  })

  it('omits the category when the select is cleared instead of crashing', async () => {
    const client = fakeClient({ items: [row({ id: 7 })] })
    const wrapper = mount(AdminArticlesView, { props: { client } })
    await flushPromises()

    await wrapper.find('[data-edit="7"]').trigger('click')
    await flushPromises()
    // el-select clear emits an undefined model (valueOnClear default).
    await wrapper.findComponent('[data-category]').vm.$emit('update:modelValue', undefined)
    await wrapper.find('[data-article-form]').trigger('submit.prevent')
    await flushPromises()

    expect(client.updateArticle).toHaveBeenCalledWith(7, {
      title: '高血压防治',
      summary: '摘要',
      content: '正文',
      status: 1,
    })
  })
})
