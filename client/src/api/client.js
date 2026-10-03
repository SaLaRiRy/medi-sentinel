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

export function createApiClient({ transport = createHttpTransport(), session = null } = {}) {
  const bearer = () => {
    const token = session && session.get().token
    return token ? { Authorization: `Bearer ${token}` } : undefined
  }

  // The request shape is built once so `health` keeps sending exactly
  // `{method, path}` and only the authed calls carry an Authorization header.
  const shape = ({ method = 'GET', path, query, body, authed = false }) => {
    const request = { method, path }
    if (query !== undefined) request.query = query
    if (body !== undefined) request.body = body
    if (authed) {
      const headers = bearer()
      if (headers) request.headers = headers
    }
    return request
  }

  const call = async (args) => {
    const { status, payload } = await transport.request(shape(args))
    return unwrap(status, payload)
  }

  const remember = (data) => {
    session?.set({ token: data.access_token, role: data.role, user: data })
    return data
  }

  return {
    async health() {
      return call({ method: 'GET', path: '/health' })
    },

    async login(credentials) {
      return remember(await call({ method: 'POST', path: '/auth/login', body: credentials }))
    },

    async register(payload) {
      return remember(await call({ method: 'POST', path: '/auth/register', body: payload }))
    },

    logout() {
      session?.clear()
    },

    async profileInfo() {
      return call({ path: '/profile/info', authed: true })
    },

    async profileUpdate(fields) {
      return call({ method: 'PUT', path: '/profile/update', body: fields, authed: true })
    },

    async changePassword(payload) {
      return call({ method: 'PUT', path: '/profile/password', body: payload, authed: true })
    },

    async uploadAvatar(file) {
      const form = new FormData()
      form.append('file', file)
      return call({ method: 'POST', path: '/profile/avatar', body: form, authed: true })
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
