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
  session.set({ token: 'token-1', role: 'user', user: {} })
  return createApiClient({ transport, session })
}

// FUNCTIONAL_SPEC 2.7 + SPEC.md 5.4「预约与健康档案」：六条路径各声明一次。
describe('appointment calls (F-1, TICKET-017)', () => {
  it('submits an appointment through POST /appointments', async () => {
    const transport = recordingTransport({ code: 200, message: 'ok', data: { id: 5 } })
    const client = authedClient(transport)

    const data = await client.createAppointment({
      doctor_id: 1,
      department_id: 2,
      visit_date: '2026-10-20',
      time_slot: '上午',
      remark: '复诊',
    })

    expect(data).toEqual({ id: 5 })
    expect(transport.calls[0]).toEqual({
      method: 'POST',
      path: '/appointments',
      body: {
        doctor_id: 1,
        department_id: 2,
        visit_date: '2026-10-20',
        time_slot: '上午',
        remark: '复诊',
      },
      headers: { Authorization: 'Bearer token-1' },
    })
  })

  it('reads the patient list and the doctor schedule', async () => {
    const transport = recordingTransport()
    const client = authedClient(transport)

    await client.myAppointments()
    await client.doctorAppointments()

    expect(transport.calls[0]).toEqual({
      method: 'GET',
      path: '/appointments/my',
      headers: { Authorization: 'Bearer token-1' },
    })
    expect(transport.calls[1]).toEqual({
      method: 'GET',
      path: '/appointments/doctor',
      headers: { Authorization: 'Bearer token-1' },
    })
  })

  it('passes the admin filters as the query string', async () => {
    const transport = recordingTransport()
    const client = authedClient(transport)

    await client.adminAppointments({
      page: 2,
      page_size: 10,
      department_id: 3,
      visit_date: '2026-10-20',
      status: 0,
      keyword: '张三',
    })

    expect(transport.calls[0]).toEqual({
      method: 'GET',
      path: '/appointments/admin',
      query: {
        page: 2,
        page_size: 10,
        department_id: 3,
        visit_date: '2026-10-20',
        status: 0,
        keyword: '张三',
      },
      headers: { Authorization: 'Bearer token-1' },
    })
  })

  it('updates the status and deletes through their paths', async () => {
    const transport = recordingTransport()
    const client = authedClient(transport)

    await client.updateAppointmentStatus(7, 2)
    await client.deleteAppointment(7)

    expect(transport.calls[0]).toEqual({
      method: 'PUT',
      path: '/appointments/7/status',
      body: { status: 2 },
      headers: { Authorization: 'Bearer token-1' },
    })
    expect(transport.calls[1]).toEqual({
      method: 'DELETE',
      path: '/appointments/admin/7',
      headers: { Authorization: 'Bearer token-1' },
    })
  })

  it('surfaces the 404 envelope as an ApiError', async () => {
    const transport = recordingTransport(
      { code: 404, message: '预约不存在', data: null },
      404
    )
    const client = authedClient(transport)

    await expect(client.updateAppointmentStatus(9999, 1)).rejects.toMatchObject({
      status: 404,
      message: '预约不存在',
    })
    expect(new ApiError({ status: 404, code: 404, message: 'x' }).status).toBe(404)
  })
})
