/**
 * F-1: the single exit module. Views call this and nothing else — no view touches
 * the transport, and every contract path is named exactly once, here.
 */

import { createHttpTransport } from './transport.js'

const KNOWN_FRAME_TYPES = new Set([
  'session',
  'trace',
  'route',
  'safety',
  'content',
  'done',
  'error',
])

export class ApiError extends Error {
  constructor({ status, code, message }) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

export function createApiClient({ transport = createHttpTransport() } = {}) {
  return {
    async health() {
      const { status, payload } = await transport.request({
        method: 'GET',
        path: '/health',
      })
      return unwrap(status, payload)
    },

    async *sendChat(request) {
      const frames = transport.stream({
        method: 'POST',
        path: '/chat/send',
        body: request,
      })
      for await (const frame of frames) {
        // Unknown frame types are ignored so the client survives a newer server (SPEC.md 5.5).
        if (KNOWN_FRAME_TYPES.has(frame.type)) yield frame
      }
    },
  }
}

function unwrap(status, payload) {
  if (payload === null || typeof payload !== 'object' || typeof payload.code !== 'number') {
    throw new ApiError({ status, code: status, message: '响应不符合契约' })
  }
  if (status < 200 || status >= 300 || payload.code !== status) {
    throw new ApiError({
      status,
      code: payload.code,
      message: payload.message ?? '请求失败',
    })
  }
  return payload.data
}
