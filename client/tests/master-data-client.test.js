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

// SPEC.md 5.4「患者与医生主数据」：每一条路径在 F-1 里各声明一次。
describe('patient calls (F-1, TICKET-020)', () => {
  it('pages patients with the query string and the token', async () => {
    const transport = recordingTransport()
    const client = authedClient(transport)

    await client.adminUsers({ page: 2, page_size: 10, keyword: '张三' })

    expect(transport.calls[0]).toEqual({
      method: 'GET',
      path: '/users',
      query: { page: 2, page_size: 10, keyword: '张三' },
      headers: { Authorization: 'Bearer token-1' },
    })
  })

  it('creates, updates, deletes and toggles a patient', async () => {
    const transport = recordingTransport()
    const client = authedClient(transport)

    await client.createUser({ username: 'a', password: 'b', confirm_password: 'b' })
    await client.updateUser(7, { real_name: '新名' })
    await client.updateUserStatus(7, 0)
    await client.deleteUser(7)

    expect(transport.calls[0]).toEqual({
      method: 'POST',
      path: '/users',
      body: { username: 'a', password: 'b', confirm_password: 'b' },
      headers: { Authorization: 'Bearer token-1' },
    })
    expect(transport.calls[1]).toEqual({
      method: 'PUT',
      path: '/users/7',
      body: { real_name: '新名' },
      headers: { Authorization: 'Bearer token-1' },
    })
    expect(transport.calls[2]).toEqual({
      method: 'PUT',
      path: '/users/7/status',
      body: { status: 0 },
      headers: { Authorization: 'Bearer token-1' },
    })
    expect(transport.calls[3]).toEqual({
      method: 'DELETE',
      path: '/users/7',
      headers: { Authorization: 'Bearer token-1' },
    })
  })
})

describe('doctor calls (F-1, TICKET-020)', () => {
  it('reads the public list without a token, passing the department filter', async () => {
    const transport = recordingTransport()
    const client = createApiClient({ transport })

    await client.doctors({ page: 1, page_size: 20, department_id: 3 })

    expect(transport.calls[0]).toEqual({
      method: 'GET',
      path: '/doctors',
      query: { page: 1, page_size: 20, department_id: 3 },
    })
  })

  it('pages the admin list and mutates doctors through their paths', async () => {
    const transport = recordingTransport()
    const client = authedClient(transport)

    await client.adminDoctors({ page: 1, page_size: 10, keyword: '李' })
    await client.createDoctor({ username: 'doc', real_name: '李医生' })
    await client.updateDoctor(5, { title: '主任医师' })
    await client.updateDoctorStatus(5, 0)
    await client.deleteDoctor(5)

    expect(transport.calls[0]).toEqual({
      method: 'GET',
      path: '/doctors/admin',
      query: { page: 1, page_size: 10, keyword: '李' },
      headers: { Authorization: 'Bearer token-1' },
    })
    expect(transport.calls[1]).toEqual({
      method: 'POST',
      path: '/doctors',
      body: { username: 'doc', real_name: '李医生' },
      headers: { Authorization: 'Bearer token-1' },
    })
    expect(transport.calls[2]).toEqual({
      method: 'PUT',
      path: '/doctors/5',
      body: { title: '主任医师' },
      headers: { Authorization: 'Bearer token-1' },
    })
    expect(transport.calls[3]).toEqual({
      method: 'PUT',
      path: '/doctors/5/status',
      body: { status: 0 },
      headers: { Authorization: 'Bearer token-1' },
    })
    expect(transport.calls[4]).toEqual({
      method: 'DELETE',
      path: '/doctors/5',
      headers: { Authorization: 'Bearer token-1' },
    })
  })
})

describe('department calls (F-1, TICKET-020)', () => {
  it('reads the public list without a token', async () => {
    const transport = recordingTransport({ code: 200, message: 'ok', data: [] })
    const client = createApiClient({ transport })

    await client.departments()

    expect(transport.calls[0]).toEqual({ method: 'GET', path: '/departments' })
  })

  it('pages the admin list and mutates departments through their paths', async () => {
    const transport = recordingTransport()
    const client = authedClient(transport)

    await client.adminDepartments({ page: 1, page_size: 10, keyword: '内' })
    await client.createDepartment({ name: '内科' })
    await client.updateDepartment(4, { name: '心内科', sort_order: 2 })
    await client.deleteDepartment(4)

    expect(transport.calls[0]).toEqual({
      method: 'GET',
      path: '/departments/admin',
      query: { page: 1, page_size: 10, keyword: '内' },
      headers: { Authorization: 'Bearer token-1' },
    })
    expect(transport.calls[1]).toEqual({
      method: 'POST',
      path: '/departments',
      body: { name: '内科' },
      headers: { Authorization: 'Bearer token-1' },
    })
    expect(transport.calls[2]).toEqual({
      method: 'PUT',
      path: '/departments/4',
      body: { name: '心内科', sort_order: 2 },
      headers: { Authorization: 'Bearer token-1' },
    })
    expect(transport.calls[3]).toEqual({
      method: 'DELETE',
      path: '/departments/4',
      headers: { Authorization: 'Bearer token-1' },
    })
  })
})
