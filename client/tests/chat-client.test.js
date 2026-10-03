import { describe, expect, it } from 'vitest'

import { ApiError, createApiClient } from '../src/api/client.js'
import { createSessionStore } from '../src/session/store.js'

function transportWith({ payload = { code: 200, message: '操作成功', data: [] }, frames = [] } = {}) {
  return {
    calls: [],
    streams: [],
    async request(shape) {
      this.calls.push(shape)
      return { status: 200, payload }
    },
    async *stream(shape) {
      this.streams.push(shape)
      for (const frame of frames) yield frame
    },
  }
}

function bearerSession(token) {
  const session = createSessionStore()
  session.set({ token, role: 'user', user: { user_id: 1 } })
  return session
}

describe('chat endpoints through F-1 (TICKET-014)', () => {
  it('lists the patient sessions from the contract path with the token attached', async () => {
    const transport = transportWith({
      payload: { code: 200, message: '操作成功', data: [{ id: 3, title: '感冒' }] },
    })
    const client = createApiClient({ transport, session: bearerSession('token-1') })

    const sessions = await client.chatSessions()

    expect(transport.calls[0]).toEqual({
      method: 'GET',
      path: '/chat/sessions',
      headers: { Authorization: 'Bearer token-1' },
    })
    expect(sessions).toEqual([{ id: 3, title: '感冒' }])
  })

  it('reads one session history from the contract path', async () => {
    const transport = transportWith({
      payload: { code: 200, message: '操作成功', data: [{ id: 1, role: 'user' }] },
    })
    const client = createApiClient({ transport, session: bearerSession('token-2') })

    const messages = await client.chatMessages(7)

    expect(transport.calls[0]).toEqual({
      method: 'GET',
      path: '/chat/sessions/7/messages',
      headers: { Authorization: 'Bearer token-2' },
    })
    expect(messages).toEqual([{ id: 1, role: 'user' }])
  })

  it('streams a consult with the token attached and the request body intact', async () => {
    const frames = [
      { type: 'session', session_id: 1 },
      { type: 'content', content: '你好' },
      { type: 'done', trace_id: 't' },
    ]
    const transport = transportWith({ frames })
    const client = createApiClient({ transport, session: bearerSession('token-3') })

    const received = []
    for await (const frame of client.sendChat({ message: '我头疼' })) received.push(frame)

    expect(transport.streams[0]).toEqual({
      method: 'POST',
      path: '/chat/send',
      body: { message: '我头疼' },
      headers: { Authorization: 'Bearer token-3' },
    })
    expect(received.map((frame) => frame.type)).toEqual(['session', 'content', 'done'])
  })

  it('still sends the consult anonymously when there is no token', async () => {
    const transport = transportWith()
    const client = createApiClient({ transport })

    for await (const _frame of client.sendChat({ message: '我头疼' })) {
      // no frames in this stub
    }

    expect(transport.streams[0].headers).toBeUndefined()
  })

  it('surfaces a failing history call as an ApiError', async () => {
    const transport = {
      async request() {
        return { status: 404, payload: { code: 404, message: '会话不存在', data: null } }
      },
    }
    const client = createApiClient({ transport })

    await expect(client.chatMessages(9)).rejects.toBeInstanceOf(ApiError)
  })
})
