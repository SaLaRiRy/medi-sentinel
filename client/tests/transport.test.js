import { describe, expect, it, vi } from 'vitest'

import { createHttpTransport, parseSse } from '../src/api/transport.js'

function chunked(...chunks) {
  return (async function* generate() {
    for (const chunk of chunks) yield chunk
  })()
}

async function collect(iterable) {
  const items = []
  for await (const item of iterable) items.push(item)
  return items
}

describe('parseSse (F-2)', () => {
  it('parses a frame split across several chunks', async () => {
    const frames = await collect(
      parseSse(chunked('data: {"type":"session",', '"session_id":1}\n\n'))
    )

    expect(frames).toEqual([{ type: 'session', session_id: 1 }])
  })

  it('parses several frames arriving in one chunk', async () => {
    const frames = await collect(
      parseSse(
        chunked(
          'data: {"type":"session","session_id":1}\n\ndata: {"type":"trace","trace_id":"a"}\n\n'
        )
      )
    )

    expect(frames.map((frame) => frame.type)).toEqual(['session', 'trace'])
  })

  it('ignores empty frames', async () => {
    const frames = await collect(
      parseSse(chunked('\n\ndata: {"type":"trace","trace_id":"a"}\n\n\n\n'))
    )

    expect(frames).toEqual([{ type: 'trace', trace_id: 'a' }])
  })
})

describe('createHttpTransport (F-2)', () => {
  it('builds the request from the contract and returns status with the parsed body', async () => {
    const payload = { code: 200, message: '操作成功', data: { status: 'ok' } }
    const fetchImpl = vi.fn(
      async () =>
        new Response(JSON.stringify(payload), {
          status: 200,
          headers: { 'content-type': 'application/json' },
        })
    )
    const transport = createHttpTransport({ fetchImpl, baseUrl: '/api/v1' })

    const result = await transport.request({
      method: 'GET',
      path: '/health',
      query: { page: 2 },
    })

    const [url, init] = fetchImpl.mock.calls[0]
    expect(url).toBe('/api/v1/health?page=2')
    expect(init.method).toBe('GET')
    expect(result).toEqual({ status: 200, payload })
  })

  it('omits query parameters that were not supplied', async () => {
    const fetchImpl = vi.fn(
      async () => new Response('{"code":200}', { status: 200 })
    )
    const transport = createHttpTransport({ fetchImpl, baseUrl: '/api/v1' })

    await transport.request({ method: 'GET', path: '/health' })

    expect(fetchImpl.mock.calls[0][0]).toBe('/api/v1/health')
  })
})
