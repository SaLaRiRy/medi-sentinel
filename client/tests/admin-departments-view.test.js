import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import AdminDepartmentsView from '../src/views/AdminDepartmentsView.vue'

function row(overrides = {}) {
  return {
    id: 1,
    name: '内科',
    description: '心血管',
    sort_order: 2,
    status: 1,
    doctor_count: 3,
    ...overrides,
  }
}

function fakeClient({ departments = [], createError, deleteError } = {}) {
  return {
    adminDepartments: vi.fn(async () => ({
      items: departments,
      total: departments.length,
      page: 1,
      page_size: 10,
    })),
    createDepartment: vi.fn(async () => {
      if (createError) throw createError
      return { id: 99 }
    }),
    updateDepartment: vi.fn(async () => null),
    deleteDepartment: vi.fn(async () => {
      if (deleteError) throw deleteError
      return null
    }),
  }
}

describe('AdminDepartmentsView list (TICKET-020)', () => {
  it('renders the departments with their doctor count', async () => {
    const client = fakeClient({ departments: [row(), row({ id: 2, doctor_count: 0 })] })
    const wrapper = mount(AdminDepartmentsView, { props: { client } })
    await flushPromises()

    const rows = wrapper.findAll('[data-department-row]')
    expect(rows).toHaveLength(2)
    expect(rows[0].text()).toContain('内科')
    expect(rows[0].text()).toContain('3')
  })

  it('shows the empty state and reports a failed load', async () => {
    const failure = Object.assign(new Error('无法加载'), { status: 500 })
    const client = fakeClient()
    client.adminDepartments = vi.fn(async () => {
      throw failure
    })
    const wrapper = mount(AdminDepartmentsView, { props: { client } })
    await flushPromises()

    expect(wrapper.find('[data-error]').text()).toContain('加载失败')
    expect(wrapper.emitted('error')).toHaveLength(1)
  })
})

describe('AdminDepartmentsView create/edit/delete (TICKET-020)', () => {
  it('requires a name before calling the client', async () => {
    const client = fakeClient()
    const wrapper = mount(AdminDepartmentsView, { props: { client } })
    await flushPromises()

    await wrapper.find('[data-department-form]').trigger('submit.prevent')
    await flushPromises()

    expect(wrapper.find('[data-form-error]').text()).toContain('必填')
    expect(client.createDepartment).not.toHaveBeenCalled()
  })

  it('creates a department through the client and reloads', async () => {
    const client = fakeClient()
    const wrapper = mount(AdminDepartmentsView, { props: { client } })
    await flushPromises()

    await wrapper.find('[data-name]').setValue('心内科')
    await wrapper.find('[data-description]').setValue('心血管')
    await wrapper.find('[data-sort-order]').setValue('3')
    await wrapper.find('[data-department-form]').trigger('submit.prevent')
    await flushPromises()

    expect(client.createDepartment).toHaveBeenCalledWith({
      name: '心内科',
      description: '心血管',
      sort_order: 3,
    })
    expect(client.adminDepartments).toHaveBeenCalledTimes(2)
  })

  it('surfaces a duplicate name as an error', async () => {
    const failure = Object.assign(new Error('科室名已存在'), { status: 409 })
    const client = fakeClient({ createError: failure })
    const wrapper = mount(AdminDepartmentsView, { props: { client } })
    await flushPromises()

    await wrapper.find('[data-name]').setValue('内科')
    await wrapper.find('[data-department-form]').trigger('submit.prevent')
    await flushPromises()

    expect(wrapper.emitted('error')[0][0]).toBe(failure)
  })

  it('edits a department in place', async () => {
    const client = fakeClient({ departments: [row({ id: 7 })] })
    const wrapper = mount(AdminDepartmentsView, { props: { client } })
    await flushPromises()

    await wrapper.find('[data-edit="7"]').trigger('click')
    await flushPromises()
    await wrapper.find('[data-name]').setValue('心内科')
    await wrapper.find('[data-department-form]').trigger('submit.prevent')
    await flushPromises()

    expect(client.updateDepartment).toHaveBeenCalledWith(7, {
      name: '心内科',
      description: '心血管',
      sort_order: 2,
    })
  })

  it('deletes a department through the client and reloads', async () => {
    const client = fakeClient({ departments: [row({ id: 7 })] })
    const wrapper = mount(AdminDepartmentsView, { props: { client } })
    await flushPromises()

    await wrapper.find('[data-delete="7"]').trigger('click')
    await flushPromises()

    expect(client.deleteDepartment).toHaveBeenCalledWith(7)
    expect(client.adminDepartments).toHaveBeenCalledTimes(2)
  })

  it('reports the 409 when the department still has doctors', async () => {
    const failure = Object.assign(new Error('该科室下还有 3 位医生，无法删除'), {
      status: 409,
    })
    const client = fakeClient({ departments: [row({ id: 7 })], deleteError: failure })
    const wrapper = mount(AdminDepartmentsView, { props: { client } })
    await flushPromises()

    await wrapper.find('[data-delete="7"]').trigger('click')
    await flushPromises()

    expect(wrapper.emitted('error')[0][0]).toBe(failure)
  })
})
