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

// SPEC.md 5.4「内容与统计」：每条统计路径在 F-1 里各声明一次。
describe('stat calls (F-1, TICKET-022)', () => {
  it('reads the role overview with the token', async () => {
    const transport = recordingTransport()
    const client = authedClient(transport)

    await client.statOverview()

    expect(transport.calls[0]).toEqual({
      method: 'GET',
      path: '/stat/overview',
      headers: { Authorization: 'Bearer token-1' },
    })
  })

  it('reads the patient overview with the token', async () => {
    const transport = recordingTransport()
    const client = authedClient(transport)

    await client.userOverview()

    expect(transport.calls[0]).toEqual({
      method: 'GET',
      path: '/stat/user-overview',
      headers: { Authorization: 'Bearer token-1' },
    })
  })

  it('reads the trends with a days query, defaulting to seven', async () => {
    const transport = recordingTransport()
    const client = authedClient(transport)

    await client.consultTrend()
    await client.consultTrend(30)
    await client.userGrowth(14)

    expect(transport.calls[0]).toEqual({
      method: 'GET',
      path: '/stat/consult-trend',
      query: { days: 7 },
      headers: { Authorization: 'Bearer token-1' },
    })
    expect(transport.calls[1]).toEqual({
      method: 'GET',
      path: '/stat/consult-trend',
      query: { days: 30 },
      headers: { Authorization: 'Bearer token-1' },
    })
    expect(transport.calls[2]).toEqual({
      method: 'GET',
      path: '/stat/user-growth',
      query: { days: 14 },
      headers: { Authorization: 'Bearer token-1' },
    })
  })

  it('reads the two distributions with the token', async () => {
    const transport = recordingTransport()
    const client = authedClient(transport)

    await client.appointmentsByDepartment()
    await client.knowledgeTypes()

    expect(transport.calls[0]).toEqual({
      method: 'GET',
      path: '/stat/appointments-by-department',
      headers: { Authorization: 'Bearer token-1' },
    })
    expect(transport.calls[1]).toEqual({
      method: 'GET',
      path: '/stat/knowledge-types',
      headers: { Authorization: 'Bearer token-1' },
    })
  })
})
