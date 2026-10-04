import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import AdminUsersView from '../src/views/AdminUsersView.vue'

function row(overrides = {}) {
  return {
    id: 1,
    username: 'alice',
    real_name: '爱丽丝',
    gender: 2,
    age: 30,
    phone: '13800000000',
    allergy_history: '青霉素',
    status: 1,
    ...overrides,
  }
}

function fakeClient({ users = [], createError, deleteError, statusError } = {}) {
  return {
    adminUsers: vi.fn(async () => ({
      items: users,
      total: users.length,
      page: 1,
      page_size: 10,
    })),
    createUser: vi.fn(async () => {
      if (createError) throw createError
      return { id: 99 }
    }),
    updateUser: vi.fn(async () => ({})),
    updateUserStatus: vi.fn(async () => {
      if (statusError) throw statusError
      return null
    }),
    deleteUser: vi.fn(async () => {
      if (deleteError) throw deleteError
      return null
    }),
  }
}

async function fillCreate(wrapper, { username = 'newuser', password = 'secret1' } = {}) {
  await wrapper.find('[data-username]').setValue(username)
  await wrapper.find('[data-password]').setValue(password)
  await wrapper.find('[data-confirm-password]').setValue(password)
}

// Phase 2: the create form lives in a dialog opened from the page header.
async function openCreate(wrapper) {
  await wrapper.find('[data-create]').trigger('click')
  await flushPromises()
}

describe('AdminUsersView list (TICKET-020)', () => {
  it('renders the patients with the account-status label', async () => {
    const client = fakeClient({ users: [row(), row({ id: 2, status: 0 })] })
    const wrapper = mount(AdminUsersView, { props: { client } })
    await flushPromises()

    // TICKET-030: ElTable cannot stamp attributes on <tr>, so rows are grouped
    // by Element Plus' stable `.el-table__row`; cell anchors are unchanged.
    const rows = wrapper.findAll('.el-table__row')
    expect(rows).toHaveLength(2)
    expect(rows[0].text()).toContain('爱丽丝')
    expect(rows[0].text()).toContain('正常')
    expect(rows[1].text()).toContain('禁用')
  })

  it('shows the empty state and reports a failed load', async () => {
    const failure = Object.assign(new Error('无法加载'), { status: 500 })
    const client = fakeClient()
    client.adminUsers = vi.fn(async () => {
      throw failure
    })
    const wrapper = mount(AdminUsersView, { props: { client } })
    await flushPromises()

    expect(wrapper.find('[data-error]').text()).toContain('加载失败')
    expect(wrapper.emitted('error')).toHaveLength(1)
  })
})

describe('AdminUsersView create/edit/delete/status (TICKET-020)', () => {
  it('validates the username and password before calling the client', async () => {
    const client = fakeClient()
    const wrapper = mount(AdminUsersView, { props: { client } })
    await flushPromises()

    await openCreate(wrapper)
    await wrapper.find('[data-user-form]').trigger('submit.prevent')
    await flushPromises()

    expect(wrapper.find('[data-form-error]').text()).toContain('必填')
    expect(client.createUser).not.toHaveBeenCalled()
  })

  it('creates a patient through the client and reloads', async () => {
    const client = fakeClient()
    const wrapper = mount(AdminUsersView, { props: { client } })
    await flushPromises()

    await openCreate(wrapper)
    await fillCreate(wrapper)
    await wrapper.find('[data-real-name]').setValue('新患者')
    await wrapper.find('[data-user-form]').trigger('submit.prevent')
    await flushPromises()

    expect(client.createUser).toHaveBeenCalledWith({
      username: 'newuser',
      password: 'secret1',
      confirm_password: 'secret1',
      real_name: '新患者',
      gender: 1,
    })
    expect(client.adminUsers).toHaveBeenCalledTimes(2)
  })

  it('surfaces a duplicate username as an error without reloading', async () => {
    const failure = Object.assign(new Error('用户名已存在'), { status: 409 })
    const client = fakeClient({ createError: failure })
    const wrapper = mount(AdminUsersView, { props: { client } })
    await flushPromises()

    await openCreate(wrapper)
    await fillCreate(wrapper)
    await wrapper.find('[data-user-form]').trigger('submit.prevent')
    await flushPromises()

    expect(wrapper.emitted('error')[0][0]).toBe(failure)
    expect(client.adminUsers).toHaveBeenCalledTimes(1)
  })

  it('edits a patient in place', async () => {
    const client = fakeClient({ users: [row({ id: 7 })] })
    const wrapper = mount(AdminUsersView, { props: { client } })
    await flushPromises()

    await wrapper.find('[data-edit="7"]').trigger('click')
    await flushPromises()
    await wrapper.find('[data-real-name]').setValue('改后')
    await wrapper.find('[data-user-form]').trigger('submit.prevent')
    await flushPromises()

    expect(client.updateUser).toHaveBeenCalledWith(7, {
      real_name: '改后',
      gender: 2,
      age: 30,
      phone: '13800000000',
      allergy_history: '青霉素',
    })
  })

  it('toggles the account status to the flipped value', async () => {
    const client = fakeClient({ users: [row({ id: 7, status: 1 })] })
    const wrapper = mount(AdminUsersView, { props: { client } })
    await flushPromises()

    await wrapper.find('[data-status-toggle="7"]').trigger('click')
    await flushPromises()

    expect(client.updateUserStatus).toHaveBeenCalledWith(7, 0)
    expect(client.adminUsers).toHaveBeenCalledTimes(2)
  })

  it('deletes a patient through the client and reloads', async () => {
    const client = fakeClient({ users: [row({ id: 7 })] })
    const wrapper = mount(AdminUsersView, { props: { client } })
    await flushPromises()

    await wrapper.find('[data-delete="7"]').trigger('click')
    await flushPromises()

    expect(client.deleteUser).toHaveBeenCalledWith(7)
    expect(client.adminUsers).toHaveBeenCalledTimes(2)
  })

  it('reports a failed delete', async () => {
    const failure = Object.assign(new Error('用户不存在'), { status: 404 })
    const client = fakeClient({ users: [row({ id: 7 })], deleteError: failure })
    const wrapper = mount(AdminUsersView, { props: { client } })
    await flushPromises()

    await wrapper.find('[data-delete="7"]').trigger('click')
    await flushPromises()

    expect(wrapper.emitted('error')[0][0]).toBe(failure)
  })
})
