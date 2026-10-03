import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { POLL_INTERVAL_MS, needsPolling } from '../src/knowledge/polling.js'
import { vectorStatusLabel } from '../src/knowledge/status.js'
import KnowledgeView from '../src/views/KnowledgeView.vue'

function pagePayload(items, { total = items.length, page = 1, page_size = 10 } = {}) {
  return { items, total, page, page_size }
}

function row(overrides = {}) {
  return {
    id: 1,
    file_name: '指南.md',
    file_type: 'md',
    file_size: 120,
    chunk_count: 3,
    vector_status: 2,
    ...overrides,
  }
}

function fakeClient({ pages = [], fail } = {}) {
  let index = 0
  return {
    knowledgeFiles: vi.fn(async () => {
      if (fail) throw fail
      const result = pages[Math.min(index, pages.length - 1)] ?? pagePayload([])
      index += 1
      return result
    }),
    uploadKnowledge: vi.fn(async () => ({ id: 99, file_name: '新文档.md' })),
    revectorizeKnowledge: vi.fn(async () => null),
    deleteKnowledge: vi.fn(async () => null),
  }
}

afterEach(() => {
  vi.useRealTimers()
})

describe('vectorization status mapping (AC-F-11)', () => {
  it('labels the four states and falls back for an unknown value', () => {
    expect([0, 1, 2, 3].map(vectorStatusLabel)).toEqual([
      '已上传',
      '处理中',
      '已向量化',
      '失败',
    ])
    expect(vectorStatusLabel(9)).toBe('未知状态')
  })
})

describe('polling decision (AC-F-13)', () => {
  it('polls only while a row is uploaded or processing', () => {
    expect(needsPolling([{ vector_status: 0 }])).toBe(true)
    expect(needsPolling([{ vector_status: 1 }])).toBe(true)
    expect(needsPolling([{ vector_status: 2 }, { vector_status: 3 }])).toBe(false)
    expect(needsPolling([])).toBe(false)
  })
})

describe('KnowledgeView list (TICKET-015)', () => {
  it('renders the files with their status labels', async () => {
    const client = fakeClient({
      pages: [pagePayload([row({ id: 3, file_name: '高血压.md', vector_status: 2 })])],
    })
    const wrapper = mount(KnowledgeView, { props: { client } })
    await flushPromises()

    const rows = wrapper.findAll('[data-knowledge-row]')
    expect(rows).toHaveLength(1)
    expect(rows[0].text()).toContain('高血压.md')
    expect(rows[0].text()).toContain('已向量化')
  })

  it('shows an empty state when there are no files', async () => {
    const wrapper = mount(KnowledgeView, {
      props: { client: fakeClient({ pages: [pagePayload([])] }) },
    })
    await flushPromises()

    expect(wrapper.find('[data-empty]').text()).toContain('暂无')
  })

  it('shows an empty state and reports the failure when the list cannot load (AC-F-12)', async () => {
    const failure = Object.assign(new Error('无法加载'), { status: 500 })
    const wrapper = mount(KnowledgeView, { props: { client: fakeClient({ fail: failure }) } })
    await flushPromises()

    expect(wrapper.find('[data-error]').text()).toContain('加载失败')
    expect(wrapper.findAll('[data-knowledge-row]')).toHaveLength(0)
    expect(wrapper.emitted('error')).toHaveLength(1)
  })

  it('searches by file name and type and returns to the first page', async () => {
    const client = fakeClient({ pages: [pagePayload([])] })
    const wrapper = mount(KnowledgeView, { props: { client } })
    await flushPromises()

    await wrapper.find('[data-keyword]').setValue('糖尿病')
    await wrapper.find('[data-file-type]').setValue('pdf')
    await wrapper.find('[data-search]').trigger('submit.prevent')
    await flushPromises()

    expect(client.knowledgeFiles).toHaveBeenLastCalledWith(
      expect.objectContaining({ page: 1, keyword: '糖尿病', file_type: 'pdf' })
    )
  })
})

describe('KnowledgeView actions (TICKET-015)', () => {
  it('uploads the chosen file through the client and reloads the list', async () => {
    const client = fakeClient({ pages: [pagePayload([])] })
    const wrapper = mount(KnowledgeView, { props: { client } })
    await flushPromises()
    const file = new File(['高血压'], '指南.md', { type: 'text/markdown' })
    const input = wrapper.find('[data-upload]')
    Object.defineProperty(input.element, 'files', { value: [file] })

    await input.trigger('change')
    await flushPromises()

    expect(client.uploadKnowledge).toHaveBeenCalledWith(file)
    expect(client.knowledgeFiles).toHaveBeenCalledTimes(2)
  })

  it('revectorizes a failed row', async () => {
    const client = fakeClient({ pages: [pagePayload([row({ id: 8, vector_status: 3 })])] })
    const wrapper = mount(KnowledgeView, { props: { client } })
    await flushPromises()

    await wrapper.find('[data-revectorize]').trigger('click')
    await flushPromises()

    expect(client.revectorizeKnowledge).toHaveBeenCalledWith(8)
  })

  it('steps back a page when the last row of a page is deleted (AC-F-12)', async () => {
    const client = fakeClient({
      pages: [
        pagePayload([row({ id: 11 })], { total: 11, page: 1 }),
        pagePayload([row({ id: 11 })], { total: 11, page: 2 }),
        pagePayload([row({ id: 1 })], { total: 10, page: 1 }),
      ],
    })
    const wrapper = mount(KnowledgeView, { props: { client } })
    await flushPromises()
    await wrapper.find('[data-next]').trigger('click')
    await flushPromises()
    expect(client.knowledgeFiles).toHaveBeenLastCalledWith(
      expect.objectContaining({ page: 2 })
    )

    await wrapper.find('[data-delete]').trigger('click')
    await flushPromises()

    expect(client.deleteKnowledge).toHaveBeenCalledWith(11)
    expect(client.knowledgeFiles).toHaveBeenLastCalledWith(
      expect.objectContaining({ page: 1 })
    )
  })
})

describe('KnowledgeView polling (AC-F-13)', () => {
  it('polls while a row is pending and stops once every row is settled', async () => {
    vi.useFakeTimers()
    const client = fakeClient({
      pages: [
        pagePayload([row({ vector_status: 0 })]),
        pagePayload([row({ vector_status: 2 })]),
      ],
    })
    const wrapper = mount(KnowledgeView, { props: { client } })
    await flushPromises()
    expect(client.knowledgeFiles).toHaveBeenCalledTimes(1)

    vi.advanceTimersByTime(POLL_INTERVAL_MS)
    await flushPromises()
    expect(client.knowledgeFiles).toHaveBeenCalledTimes(2)

    vi.advanceTimersByTime(POLL_INTERVAL_MS * 3)
    await flushPromises()
    expect(client.knowledgeFiles).toHaveBeenCalledTimes(2)
    wrapper.unmount()
  })

  it('clears the timer when the component unmounts', async () => {
    vi.useFakeTimers()
    const client = fakeClient({ pages: [pagePayload([row({ vector_status: 1 })])] })
    const wrapper = mount(KnowledgeView, { props: { client } })
    await flushPromises()

    wrapper.unmount()
    vi.advanceTimersByTime(POLL_INTERVAL_MS * 3)
    await flushPromises()

    expect(client.knowledgeFiles).toHaveBeenCalledTimes(1)
  })
})
