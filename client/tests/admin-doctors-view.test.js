import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import AdminDoctorsView from '../src/views/AdminDoctorsView.vue'

function row(overrides = {}) {
  return {
    id: 1,
    username: 'doctor',
    real_name: '李医生',
    department_id: 3,
    department_name: '内科',
    title: '主任医师',
    specialty: '心内科',
    introduction: '从业二十年',
    phone: '13900000000',
    status: 1,
    ...overrides,
  }
}

function fakeClient({ doctors = [], departments = [{ id: 3, name: '内科' }], createError } = {}) {
  return {
    adminDoctors: vi.fn(async () => ({
      items: doctors,
      total: doctors.length,
      page: 1,
      page_size: 10,
    })),
    adminDepartments: vi.fn(async () => ({
      items: departments,
      total: departments.length,
      page: 1,
      page_size: 100,
    })),
    createDoctor: vi.fn(async () => {
      if (createError) throw createError
      return { id: 99 }
    }),
    updateDoctor: vi.fn(async () => ({})),
    updateDoctorStatus: vi.fn(async () => null),
    deleteDoctor: vi.fn(async () => null),
  }
}

async function fillCreate(
  wrapper,
  { username = 'newdoc', password = 'secret1', realName = '新医生', department = '3' } = {}
) {
  await wrapper.find('[data-username]').setValue(username)
  await wrapper.find('[data-password]').setValue(password)
  await wrapper.find('[data-confirm-password]').setValue(password)
  await wrapper.find('[data-real-name]').setValue(realName)
  // TICKET-030: el-select is a component; drive its model.
  await wrapper.findComponent('[data-department]').setValue(department)
}

// Phase 2: the create form lives in a dialog opened from the page header.
async function openCreate(wrapper) {
  await wrapper.find('[data-create]').trigger('click')
  await flushPromises()
}

describe('AdminDoctorsView list (TICKET-020)', () => {
  it('renders the doctors with the department and account-status label', async () => {
    const client = fakeClient({ doctors: [row(), row({ id: 2, status: 0, department_name: null })] })
    const wrapper = mount(AdminDoctorsView, { props: { client } })
    await flushPromises()

    // TICKET-030: ElTable rows are grouped by the stable `.el-table__row`.
    const rows = wrapper.findAll('.el-table__row')
    expect(rows).toHaveLength(2)
    expect(rows[0].text()).toContain('李医生')
    expect(rows[0].text()).toContain('内科')
    expect(rows[0].text()).toContain('正常')
    expect(rows[1].text()).toContain('禁用')
  })

  it('loads the department options into the select', async () => {
    const client = fakeClient({ departments: [{ id: 7, name: '外科' }] })
    const wrapper = mount(AdminDoctorsView, { props: { client } })
    await flushPromises()

    await openCreate(wrapper)
    const options = wrapper.findAll('[data-department-option]')
    expect(options).toHaveLength(1)
    expect(options[0].text()).toContain('外科')
    // TICKET-030: el-option does not render its `value` prop as an attribute.
    expect(wrapper.findComponent('[data-department-option]').props('value')).toBe(7)
  })
})

describe('AdminDoctorsView create/edit/delete/status (TICKET-020)', () => {
  it('requires a username, a name and matching passwords', async () => {
    const client = fakeClient()
    const wrapper = mount(AdminDoctorsView, { props: { client } })
    await flushPromises()

    await openCreate(wrapper)
    await wrapper.find('[data-doctor-form]').trigger('submit.prevent')
    await flushPromises()

    expect(wrapper.find('[data-form-error]').text()).toContain('必填')
    expect(client.createDoctor).not.toHaveBeenCalled()
  })

  it('creates a doctor through the client and reloads', async () => {
    const client = fakeClient()
    const wrapper = mount(AdminDoctorsView, { props: { client } })
    await flushPromises()

    await openCreate(wrapper)
    await fillCreate(wrapper)
    await wrapper.find('[data-doctor-form]').trigger('submit.prevent')
    await flushPromises()

    expect(client.createDoctor).toHaveBeenCalledWith({
      username: 'newdoc',
      password: 'secret1',
      confirm_password: 'secret1',
      real_name: '新医生',
      department_id: 3,
    })
    expect(client.adminDoctors).toHaveBeenCalledTimes(2)
  })

  it('surfaces a duplicate username as an error', async () => {
    const failure = Object.assign(new Error('用户名已存在'), { status: 409 })
    const client = fakeClient({ createError: failure })
    const wrapper = mount(AdminDoctorsView, { props: { client } })
    await flushPromises()

    await openCreate(wrapper)
    await fillCreate(wrapper)
    await wrapper.find('[data-doctor-form]').trigger('submit.prevent')
    await flushPromises()

    expect(wrapper.emitted('error')[0][0]).toBe(failure)
  })

  it('edits a doctor in place', async () => {
    const client = fakeClient({ doctors: [row({ id: 7 })] })
    const wrapper = mount(AdminDoctorsView, { props: { client } })
    await flushPromises()

    await wrapper.find('[data-edit="7"]').trigger('click')
    await flushPromises()
    await wrapper.find('[data-title]').setValue('副主任医师')
    await wrapper.find('[data-doctor-form]').trigger('submit.prevent')
    await flushPromises()

    expect(client.updateDoctor).toHaveBeenCalledWith(7, {
      real_name: '李医生',
      department_id: 3,
      title: '副主任医师',
      specialty: '心内科',
      introduction: '从业二十年',
      phone: '13900000000',
    })
  })

  it('toggles the status and deletes through the client', async () => {
    const client = fakeClient({ doctors: [row({ id: 7, status: 1 })] })
    const wrapper = mount(AdminDoctorsView, { props: { client } })
    await flushPromises()

    await wrapper.find('[data-status-toggle="7"]').trigger('click')
    await flushPromises()
    await wrapper.find('[data-delete="7"]').trigger('click')
    await flushPromises()

    expect(client.updateDoctorStatus).toHaveBeenCalledWith(7, 0)
    expect(client.deleteDoctor).toHaveBeenCalledWith(7)
  })

  it('omits the department when the select is cleared instead of sending NaN', async () => {
    const client = fakeClient({ doctors: [row({ id: 7 })] })
    const wrapper = mount(AdminDoctorsView, { props: { client } })
    await flushPromises()

    await wrapper.find('[data-edit="7"]').trigger('click')
    await flushPromises()
    // el-select clear emits an undefined model (valueOnClear default).
    await wrapper.findComponent('[data-department]').vm.$emit('update:modelValue', undefined)
    await wrapper.find('[data-doctor-form]').trigger('submit.prevent')
    await flushPromises()

    expect(client.updateDoctor).toHaveBeenCalledWith(7, {
      real_name: '李医生',
      title: '主任医师',
      specialty: '心内科',
      introduction: '从业二十年',
      phone: '13900000000',
    })
  })
})
