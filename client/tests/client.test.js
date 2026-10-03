import { describe, expect, it, vi } from 'vitest'

import { ApiError, createApiClient } from '../src/api/client.js'

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
