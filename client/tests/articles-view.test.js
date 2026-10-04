import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import ArticlesView from '../src/views/ArticlesView.vue'

function row(overrides = {}) {
  return {
    id: 1,
    title: '高血压防治',
    category: '健康科普',
    summary: '摘要',
    view_count: 3,
    status: 1,
    ...overrides,
  }
}

function fakeClient({ articles = [], total, article, listError, detailError } = {}) {
  return {
    articles: vi.fn(async () => {
      if (listError) throw listError
      return {
        items: articles,
        total: total ?? articles.length,
        page: 1,
        page_size: 10,
      }
    }),
    article: vi.fn(async () => {
      if (detailError) throw detailError
      return article ?? { id: 1, title: '高血压防治', content: '正文' }
    }),
  }
}

describe('ArticlesView list (TICKET-021)', () => {
  it('renders published articles with their category', async () => {
    const client = fakeClient({ articles: [row(), row({ id: 2, title: '糖尿病饮食' })] })
    const wrapper = mount(ArticlesView, { props: { client } })
    await flushPromises()

    const rows = wrapper.findAll('[data-article-row]')
    expect(rows).toHaveLength(2)
    expect(rows[0].text()).toContain('高血压防治')
    expect(rows[0].text()).toContain('健康科普')
  })

  it('filters by category through the client', async () => {
    const client = fakeClient({ articles: [row()] })
    const wrapper = mount(ArticlesView, { props: { client } })
    await flushPromises()

    await wrapper.find('[data-category-filter]').setValue('疾病预防')
    await flushPromises()

    expect(client.articles).toHaveBeenLastCalledWith({
      page: 1,
      page_size: 10,
      category: '疾病预防',
    })
  })

  it('shows the empty state and reports a failed load', async () => {
    const failure = Object.assign(new Error('无法加载'), { status: 500 })
    const client = fakeClient({ listError: failure })
    const wrapper = mount(ArticlesView, { props: { client } })
    await flushPromises()

    expect(wrapper.find('[data-error]').text()).toContain('加载失败')
    expect(wrapper.findAll('[data-article-row]')).toHaveLength(0)
    expect(wrapper.emitted('error')).toHaveLength(1)
  })
})

describe('ArticlesView detail (TICKET-021)', () => {
  it('opens a detail through the client and can return to the list', async () => {
    const client = fakeClient({
      articles: [row({ id: 5 })],
      article: { id: 5, title: '高血压防治', content: '正文内容' },
    })
    const wrapper = mount(ArticlesView, { props: { client } })
    await flushPromises()

    await wrapper.find('[data-open="5"]').trigger('click')
    await flushPromises()

    expect(client.article).toHaveBeenCalledWith(5)
    expect(wrapper.find('[data-detail-content]').text()).toContain('正文内容')

    await wrapper.find('[data-back]').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-detail]').exists()).toBe(false)
    expect(wrapper.findAll('[data-article-row]')).toHaveLength(1)
  })

  it('reports a failed detail and stays on the list', async () => {
    const failure = Object.assign(new Error('文章不存在'), { status: 404 })
    const client = fakeClient({ articles: [row({ id: 5 })], detailError: failure })
    const wrapper = mount(ArticlesView, { props: { client } })
    await flushPromises()

    await wrapper.find('[data-open="5"]').trigger('click')
    await flushPromises()

    expect(wrapper.emitted('error')[0][0]).toBe(failure)
    expect(wrapper.find('[data-detail]').exists()).toBe(false)
    expect(wrapper.findAll('[data-article-row]')).toHaveLength(1)
  })
})
