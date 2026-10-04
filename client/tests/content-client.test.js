import { describe, expect, it } from 'vitest'

import { createApiClient } from '../src/api/client.js'
import { createSessionStore } from '../src/session/store.js'

function recordingTransport(payload = { code: 200, message: '操作成功', data: {} }) {
  return {
    calls: [],
    async request(shape) {
      this.calls.push(shape)
      return { status: 200, payload }
    },
  }
}

function authedClient(transport) {
  const session = createSessionStore()
  session.set({ token: 'token-1', role: 'admin', user: {} })
  return createApiClient({ transport, session })
}

// SPEC.md 5.4「内容与统计」：每一条路径在 F-1 里各声明一次。
describe('article calls (F-1, TICKET-021)', () => {
  it('reads the public list with the category filter and without a token', async () => {
    const transport = recordingTransport({ code: 200, message: 'ok', data: {} })
    const client = createApiClient({ transport })

    await client.articles({ page: 2, page_size: 10, category: '健康科普' })

    expect(transport.calls[0]).toEqual({
      method: 'GET',
      path: '/articles',
      query: { page: 2, page_size: 10, keyword: undefined, category: '健康科普' },
    })
  })

  it('reads a public article detail without a token', async () => {
    const transport = recordingTransport()
    const client = createApiClient({ transport })

    await client.article(7)

    expect(transport.calls[0]).toEqual({ method: 'GET', path: '/articles/7' })
  })

  it('pages and mutates articles through the admin paths with the token', async () => {
    const transport = recordingTransport()
    const client = authedClient(transport)

    await client.adminArticles({ page: 1, page_size: 10, keyword: '高血压' })
    await client.createArticle({ title: '新文章' })
    await client.updateArticle(7, { title: '改标题', status: 0 })
    await client.deleteArticle(7)

    expect(transport.calls[0]).toEqual({
      method: 'GET',
      path: '/articles/admin',
      query: { page: 1, page_size: 10, keyword: '高血压' },
      headers: { Authorization: 'Bearer token-1' },
    })
    expect(transport.calls[1]).toEqual({
      method: 'POST',
      path: '/articles',
      body: { title: '新文章' },
      headers: { Authorization: 'Bearer token-1' },
    })
    expect(transport.calls[2]).toEqual({
      method: 'PUT',
      path: '/articles/7',
      body: { title: '改标题', status: 0 },
      headers: { Authorization: 'Bearer token-1' },
    })
    expect(transport.calls[3]).toEqual({
      method: 'DELETE',
      path: '/articles/7',
      headers: { Authorization: 'Bearer token-1' },
    })
  })
})

describe('notice calls (F-1, TICKET-021)', () => {
  it('reads the public list and a detail without a token', async () => {
    const transport = recordingTransport({ code: 200, message: 'ok', data: [] })
    const client = createApiClient({ transport })

    await client.notices()
    await client.notice(3)

    expect(transport.calls[0]).toEqual({ method: 'GET', path: '/notices' })
    expect(transport.calls[1]).toEqual({ method: 'GET', path: '/notices/3' })
  })

  it('pages and mutates notices through the admin paths with the token', async () => {
    const transport = recordingTransport()
    const client = authedClient(transport)

    await client.adminNotices({ page: 1, page_size: 10, keyword: '停机' })
    await client.createNotice({ title: '新公告' })
    await client.updateNotice(3, { title: '改标题', status: 0 })
    await client.deleteNotice(3)

    expect(transport.calls[0]).toEqual({
      method: 'GET',
      path: '/notices/admin',
      query: { page: 1, page_size: 10, keyword: '停机' },
      headers: { Authorization: 'Bearer token-1' },
    })
    expect(transport.calls[1]).toEqual({
      method: 'POST',
      path: '/notices',
      body: { title: '新公告' },
      headers: { Authorization: 'Bearer token-1' },
    })
    expect(transport.calls[2]).toEqual({
      method: 'PUT',
      path: '/notices/3',
      body: { title: '改标题', status: 0 },
      headers: { Authorization: 'Bearer token-1' },
    })
    expect(transport.calls[3]).toEqual({
      method: 'DELETE',
      path: '/notices/3',
      headers: { Authorization: 'Bearer token-1' },
    })
  })
})
