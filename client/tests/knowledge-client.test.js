import { describe, expect, it } from 'vitest'

import { ApiError, createApiClient } from '../src/api/client.js'
import { createSessionStore } from '../src/session/store.js'

function recordingTransport(results = {}) {
  return {
    calls: [],
    async request(shape) {
      this.calls.push(shape)
      return results[shape.path] ?? { status: 200, payload: { code: 200, message: 'ok', data: null } }
    },
  }
}

describe('knowledge calls (TICKET-015, F-1)', () => {
  it('lists files with the page, page size and search filters as query parameters', async () => {
    const transport = recordingTransport({
      '/knowledge': {
        status: 200,
        payload: {
          code: 200,
          message: 'ok',
          data: { items: [], total: 0, page: 1, page_size: 10 },
        },
      },
    })
    const client = createApiClient({ transport })

    await client.knowledgeFiles({ page: 2, page_size: 10, keyword: '指南', file_type: 'md' })

    expect(transport.calls[0]).toEqual({
      method: 'GET',
      path: '/knowledge',
      query: { page: 2, page_size: 10, keyword: '指南', file_type: 'md' },
    })
  })

  it('uploads the file as multipart with the token attached', async () => {
    const session = createSessionStore()
    session.set({ token: 'admin-token', role: 'admin', user: {} })
    const transport = recordingTransport({
      '/knowledge': {
        status: 200,
        payload: { code: 200, message: 'ok', data: { id: 7, file_name: '指南.md' } },
      },
    })
    const client = createApiClient({ transport, session })

    await client.uploadKnowledge({ name: '指南.md' })

    const call = transport.calls[0]
    expect(call.method).toBe('POST')
    expect(call.path).toBe('/knowledge')
    expect(call.headers).toEqual({ Authorization: 'Bearer admin-token' })
    expect(call.body).toBeInstanceOf(FormData)
  })

  it('revectorizes and deletes through their declared paths', async () => {
    const transport = recordingTransport()
    const client = createApiClient({ transport })

    await client.revectorizeKnowledge(4)
    await client.deleteKnowledge(4)

    expect(transport.calls[0]).toEqual({
      method: 'POST',
      path: '/knowledge/4/revectorize',
    })
    expect(transport.calls[1]).toEqual({ method: 'DELETE', path: '/knowledge/4' })
  })

  it('surfaces a 413 from an oversized upload', async () => {
    const transport = {
      async request() {
        return {
          status: 413,
          payload: { code: 413, message: '文件超过大小上限', data: null },
        }
      },
    }
    const client = createApiClient({ transport })

    await expect(client.uploadKnowledge({ name: 'big.md' })).rejects.toMatchObject({
      status: 413,
      message: '文件超过大小上限',
    })
    await expect(client.uploadKnowledge({ name: 'big.md' })).rejects.toBeInstanceOf(
      ApiError
    )
  })
})
