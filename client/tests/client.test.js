import { describe, expect, it, vi } from 'vitest'

import { ApiError, createApiClient } from '../src/api/client.js'
import { createSessionStore } from '../src/session/store.js'

function transportReturning(status, payload) {
  return { request: vi.fn(async () => ({ status, payload })) }
}

describe('createApiClient (F-1)', () => {
  it('returns the envelope data for a conforming response', async () => {
    const client = createApiClient({
      transport: transportReturning(200, {
        code: 200,
        message: '操作成功',
        data: { status: 'ok', database: 'ok', version: '0.1.0' },
      }),
    })

    await expect(client.health()).resolves.toEqual({
      status: 'ok',
      database: 'ok',
      version: '0.1.0',
    })
  })

  it('calls the contract path through the transport', async () => {
    const transport = transportReturning(200, { code: 200, message: 'ok', data: {} })

    await createApiClient({ transport }).health()

    expect(transport.request).toHaveBeenCalledWith({ method: 'GET', path: '/health' })
  })

  it('rejects a response whose body is not the envelope', async () => {
    const client = createApiClient({
      transport: transportReturning(200, { detail: 'Not Found' }),
    })

    await expect(client.health()).rejects.toBeInstanceOf(ApiError)
  })

  it('rejects when the status code and the envelope code disagree', async () => {
    const client = createApiClient({
      transport: transportReturning(200, { code: 400, message: '参数错误', data: null }),
    })

    await expect(client.health()).rejects.toMatchObject({ code: 400 })
  })

  it('carries the server message on a real error status', async () => {
    const client = createApiClient({
      transport: transportReturning(404, { code: 404, message: '资源不存在', data: null }),
    })

    await expect(client.health()).rejects.toMatchObject({
      status: 404,
      message: '资源不存在',
    })
  })
})

describe('chat stream consumption (F-1, C-1)', () => {
  function streamingTransport(frames) {
    return {
      stream: vi.fn(async function* generate() {
        for (const frame of frames) yield frame
      }),
    }
  }

  it('keeps known frame types in order', async () => {
    const client = createApiClient({
      transport: streamingTransport([
        { type: 'session', session_id: 1 },
        { type: 'content', content: '你好' },
        { type: 'done', trace_id: 'a' },
      ]),
    })

    const received = []
    for await (const frame of client.sendChat({ message: '你好' })) received.push(frame)

    expect(received.map((frame) => frame.type)).toEqual(['session', 'content', 'done'])
  })

  it('ignores a frame type the contract does not know, without stopping the stream', async () => {
    const client = createApiClient({
      transport: streamingTransport([
        { type: 'session', session_id: 1 },
        { type: 'experiment', payload: 'x' },
        { type: 'done', trace_id: 'a' },
      ]),
    })

    const received = []
    for await (const frame of client.sendChat({ message: '你好' })) received.push(frame)

    expect(received.map((frame) => frame.type)).toEqual(['session', 'done'])
  })
})

describe('auth and profile calls (F-1, TICKET-012)', () => {
  function recordingTransport(payload = { code: 200, message: '操作成功', data: {} }) {
    return {
      calls: [],
      async request(shape) {
        this.calls.push(shape)
        return { status: 200, payload }
      },
    }
  }

  it('logs in through the contract path and stores the token', async () => {
    const session = createSessionStore()
    const transport = recordingTransport({
      code: 200,
      message: '操作成功',
      data: {
        access_token: 'token-1',
        token_type: 'bearer',
        role: 'user',
        user_id: 3,
        username: 'alice',
        display_name: '爱丽丝',
        avatar: null,
      },
    })
    const client = createApiClient({ transport, session })

    const data = await client.login({ username: 'alice', password: 'secret', role: 'user' })

    expect(transport.calls[0]).toEqual({
      method: 'POST',
      path: '/auth/login',
      body: { username: 'alice', password: 'secret', role: 'user' },
    })
    expect(data.token_type).toBe('bearer')
    expect(session.get().token).toBe('token-1')
    expect(session.get().role).toBe('user')
  })

  it('does not attach a bearer token to the login request', async () => {
    const session = createSessionStore()
    session.set({ token: 'stale', role: 'user', user: {} })
    const transport = recordingTransport()
    const client = createApiClient({ transport, session })

    await client.login({ username: 'a', password: 'b', role: 'user' })

    expect(transport.calls[0].headers).toBeUndefined()
  })

  it('attaches the stored token to profile calls', async () => {
    const session = createSessionStore()
    session.set({ token: 'token-2', role: 'doctor', user: {} })
    const transport = recordingTransport({ code: 200, message: 'ok', data: { id: 2 } })
    const client = createApiClient({ transport, session })

    await client.profileInfo()

    expect(transport.calls[0]).toEqual({
      method: 'GET',
      path: '/profile/info',
      headers: { Authorization: 'Bearer token-2' },
    })
  })

  it('updates the profile and changes the password through their paths', async () => {
    const transport = recordingTransport()
    const client = createApiClient({ transport })

    await client.profileUpdate({ real_name: '新名' })
    await client.changePassword({ old_password: 'a', new_password: 'b' })

    expect(transport.calls[0]).toEqual({
      method: 'PUT',
      path: '/profile/update',
      body: { real_name: '新名' },
    })
    expect(transport.calls[1]).toEqual({
      method: 'PUT',
      path: '/profile/password',
      body: { old_password: 'a', new_password: 'b' },
    })
  })

  it('uploads an avatar as multipart with the token attached', async () => {
    const session = createSessionStore()
    session.set({ token: 'token-3', role: 'admin', user: {} })
    const transport = recordingTransport({
      code: 200,
      message: 'ok',
      data: { avatar: '/uploads33/avatar/x.png' },
    })
    const client = createApiClient({ transport, session })

    await client.uploadAvatar({ name: 'x.png' })

    const call = transport.calls[0]
    expect(call.method).toBe('POST')
    expect(call.path).toBe('/profile/avatar')
    expect(call.headers).toEqual({ Authorization: 'Bearer token-3' })
    expect(call.body).toBeInstanceOf(FormData)
  })

  it('logs out by clearing the local session', () => {
    const session = createSessionStore()
    session.set({ token: 'token-4', role: 'user', user: { name: 'x' } })
    const client = createApiClient({ transport: recordingTransport(), session })

    client.logout()

    expect(session.get().token).toBeNull()
    expect(session.get().role).toBeNull()
  })

  it('surfaces a 401 so the caller can clear the session (F-3)', async () => {
    const transport = {
      async request() {
        return { status: 401, payload: { code: 401, message: '未登录', data: null } }
      },
    }
    const client = createApiClient({ transport })

    await expect(client.profileInfo()).rejects.toMatchObject({ status: 401 })
  })
})
