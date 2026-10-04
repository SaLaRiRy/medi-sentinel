import { describe, expect, it } from 'vitest'

import { createApiClient } from '../src/api/client.js'
import { createSessionStore } from '../src/session/store.js'

function recordingTransport(
  payload = { code: 200, message: '操作成功', data: {} },
  status = 200
) {
  return {
    calls: [],
    async request(shape) {
      this.calls.push(shape)
      return { status, payload }
    },
  }
}

function authedClient(transport, role = 'doctor') {
  const session = createSessionStore()
  session.set({ token: 'token-1', role, user: {} })
  return createApiClient({ transport, session })
}

// SPEC.md 5.4「人工问诊」：六条路径各声明一次，主诉与抢单都在这里。
describe('consult calls (F-1, TICKET-019)', () => {
  it('submits and reads the patient tickets through their paths', async () => {
    const transport = recordingTransport()
    const client = authedClient(transport, 'user')

    await client.createConsult({ doctor_id: 1, chief_complaint: '头痛：三天' })
    await client.myConsults()

    expect(transport.calls[0]).toEqual({
      method: 'POST',
      path: '/consults',
      body: { doctor_id: 1, chief_complaint: '头痛：三天' },
      headers: { Authorization: 'Bearer token-1' },
    })
    expect(transport.calls[1]).toEqual({
      method: 'GET',
      path: '/consults/my',
      headers: { Authorization: 'Bearer token-1' },
    })
  })

  it('reads pending tickets and posts a reply through their paths', async () => {
    const transport = recordingTransport()
    const client = authedClient(transport)

    await client.pendingConsults()
    await client.replyConsult(5, { consult_id: 5, content: '请及时就医。' })

    expect(transport.calls[0]).toEqual({
      method: 'GET',
      path: '/consults/pending',
      headers: { Authorization: 'Bearer token-1' },
    })
    expect(transport.calls[1]).toEqual({
      method: 'POST',
      path: '/consults/5/replies',
      body: { consult_id: 5, content: '请及时就医。' },
      headers: { Authorization: 'Bearer token-1' },
    })
  })

  it('pages and filters the admin list, and deletes a ticket', async () => {
    const transport = recordingTransport()
    const client = authedClient(transport, 'admin')

    await client.adminConsults({ page: 1, page_size: 10, status: 0 })
    await client.deleteConsult(7)

    expect(transport.calls[0]).toEqual({
      method: 'GET',
      path: '/consults/admin',
      query: { page: 1, page_size: 10, status: 0 },
      headers: { Authorization: 'Bearer token-1' },
    })
    expect(transport.calls[1]).toEqual({
      method: 'DELETE',
      path: '/consults/admin/7',
      headers: { Authorization: 'Bearer token-1' },
    })
  })

  it('pages every patient session for the admin (SPEC.md 5.4)', async () => {
    const transport = recordingTransport()
    const client = authedClient(transport, 'admin')

    await client.adminChatSessions({ page: 2, page_size: 5 })

    expect(transport.calls[0]).toEqual({
      method: 'GET',
      path: '/chat/admin/sessions',
      query: { page: 2, page_size: 5 },
      headers: { Authorization: 'Bearer token-1' },
    })
  })

  it('surfaces the 409 envelope as an ApiError', async () => {
    const transport = recordingTransport(
      { code: 409, message: '该工单已被其他医生认领', data: null },
      409
    )
    const client = authedClient(transport)

    await expect(
      client.replyConsult(5, { consult_id: 5, content: '抢单' })
    ).rejects.toMatchObject({ status: 409, message: '该工单已被其他医生认领' })
  })
})
