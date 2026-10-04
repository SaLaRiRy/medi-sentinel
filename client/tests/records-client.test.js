import { describe, expect, it } from 'vitest'

import { ApiError, createApiClient } from '../src/api/client.js'
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

function authedClient(transport) {
  const session = createSessionStore()
  session.set({ token: 'token-1', role: 'doctor', user: {} })
  return createApiClient({ transport, session })
}

// SPEC.md 5.4「预约与健康档案」：六条路径各声明一次。
describe('health record calls (F-1, TICKET-018)', () => {
  it('reads my records and the doctor records through their paths', async () => {
    const transport = recordingTransport()
    const client = authedClient(transport)

    await client.myRecords()
    await client.doctorRecords()
    await client.recordPatientOptions()

    expect(transport.calls[0]).toEqual({
      method: 'GET',
      path: '/records/my',
      headers: { Authorization: 'Bearer token-1' },
    })
    expect(transport.calls[1]).toEqual({
      method: 'GET',
      path: '/records/doctor',
      headers: { Authorization: 'Bearer token-1' },
    })
    expect(transport.calls[2]).toEqual({
      method: 'GET',
      path: '/records/doctor/patient-options',
      headers: { Authorization: 'Bearer token-1' },
    })
  })

  it('creates a record through POST /records/doctor', async () => {
    const transport = recordingTransport({ code: 200, message: 'ok', data: { id: 5 } })
    const client = authedClient(transport)

    const data = await client.createRecord({
      user_id: 1,
      record_type: '门诊记录',
      diagnosis: '感冒',
    })

    expect(data).toEqual({ id: 5 })
    expect(transport.calls[0]).toEqual({
      method: 'POST',
      path: '/records/doctor',
      body: { user_id: 1, record_type: '门诊记录', diagnosis: '感冒' },
      headers: { Authorization: 'Bearer token-1' },
    })
  })

  it('updates and deletes a record through its path', async () => {
    const transport = recordingTransport()
    const client = authedClient(transport)

    await client.updateRecord(7, { record_type: '复诊记录' })
    await client.deleteRecord(7)

    expect(transport.calls[0]).toEqual({
      method: 'PUT',
      path: '/records/doctor/7',
      body: { record_type: '复诊记录' },
      headers: { Authorization: 'Bearer token-1' },
    })
    expect(transport.calls[1]).toEqual({
      method: 'DELETE',
      path: '/records/doctor/7',
      headers: { Authorization: 'Bearer token-1' },
    })
  })

  it('surfaces the 404 envelope as an ApiError', async () => {
    const transport = recordingTransport(
      { code: 404, message: '档案不存在', data: null },
      404
    )
    const client = authedClient(transport)

    await expect(client.updateRecord(9999, { record_type: 'x' })).rejects.toMatchObject({
      status: 404,
      message: '档案不存在',
    })
    expect(new ApiError({ status: 404, code: 404, message: 'x' }).status).toBe(404)
  })
})
