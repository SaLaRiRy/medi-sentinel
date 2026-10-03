import { describe, expect, it } from 'vitest'

import { createApiClient } from '../src/api/client.js'
import { createSessionStore } from '../src/session/store.js'

function recordingTransport(results = {}) {
  return {
    calls: [],
    async request(shape) {
      this.calls.push(shape)
      return (
        results[shape.path] ?? {
          status: 200,
          payload: { code: 200, message: 'ok', data: null },
        }
      )
    },
  }
}

describe('graph calls (TICKET-016, F-1)', () => {
  it('reads the full graph, a disease detail and its stats from their paths', async () => {
    const transport = recordingTransport({
      '/graph': {
        status: 200,
        payload: {
          code: 200,
          message: 'ok',
          data: { nodes: [], edges: [] },
        },
      },
      '/graph/diseases/高血压': {
        status: 200,
        payload: { code: 200, message: 'ok', data: { disease: '高血压' } },
      },
      '/graph/stats': {
        status: 200,
        payload: { code: 200, message: 'ok', data: { Disease: 3 } },
      },
    })
    const session = createSessionStore()
    session.set({ token: 'admin-token', role: 'admin', user: {} })
    const client = createApiClient({ transport, session })

    await client.graphOverview()
    await client.graphDisease('高血压')
    await client.graphStats()

    expect(transport.calls[0]).toEqual({ method: 'GET', path: '/graph' })
    expect(transport.calls[1]).toEqual({
      method: 'GET',
      path: '/graph/diseases/%E9%AB%98%E8%A1%80%E5%8E%8B',
    })
    expect(transport.calls[2]).toEqual({
      method: 'GET',
      path: '/graph/stats',
      headers: { Authorization: 'Bearer admin-token' },
    })
  })

  it('passes the search keyword as a query parameter', async () => {
    const transport = recordingTransport({
      '/graph/search': {
        status: 200,
        payload: { code: 200, message: 'ok', data: [] },
      },
    })
    const client = createApiClient({ transport })

    await client.graphSearch('高')

    expect(transport.calls[0]).toEqual({
      method: 'GET',
      path: '/graph/search',
      query: { keyword: '高' },
    })
  })

  it('sends the entity and depth to the neighbourhood path', async () => {
    const transport = recordingTransport({
      '/graph/entities/%E9%AB%98%E8%A1%80%E5%8E%8B/neighbors': {
        status: 200,
        payload: { code: 200, message: 'ok', data: { nodes: [], edges: [] } },
      },
    })
    const client = createApiClient({ transport })

    await client.graphNeighbors('高血压', 3)

    expect(transport.calls[0]).toEqual({
      method: 'GET',
      path: '/graph/entities/%E9%AB%98%E8%A1%80%E5%8E%8B/neighbors',
      query: { depth: 3 },
    })
  })

  it('posts the symptoms to the inference path with the token attached', async () => {
    const transport = recordingTransport({
      '/graph/infer': {
        status: 200,
        payload: { code: 200, message: 'ok', data: [] },
      },
    })
    const session = createSessionStore()
    session.set({ token: 'user-token', role: 'user', user: {} })
    const client = createApiClient({ transport, session })

    await client.inferGraph(['头痛', '发热'])

    expect(transport.calls[0]).toEqual({
      method: 'POST',
      path: '/graph/infer',
      body: { symptoms: ['头痛', '发热'] },
      headers: { Authorization: 'Bearer user-token' },
    })
  })

  it('surfaces a 503 so the view can show an error state', async () => {
    const transport = {
      async request() {
        return {
          status: 503,
          payload: { code: 503, message: '图谱服务不可用', data: null },
        }
      },
    }
    const client = createApiClient({ transport })

    await expect(client.graphOverview()).rejects.toMatchObject({
      status: 503,
      message: '图谱服务不可用',
    })
  })
})
