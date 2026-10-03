import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import AppointmentView from '../src/views/AppointmentView.vue'

function row(overrides = {}) {
  return {
    id: 1,
    user_id: 1,
    user_name: '张三',
    doctor_id: 1,
    doctor_name: '李医生',
    department_id: 2,
    visit_date: '2026-10-20',
    time_slot: '上午',
    status: 0,
    remark: '',
    ...overrides,
  }
}

function fakeClient({ appointments = [], loadError, createError } = {}) {
  return {
    myAppointments: vi.fn(async () => {
      if (loadError) throw loadError
      return appointments
    }),
    createAppointment: vi.fn(async () => {
      if (createError) throw createError
      return { id: 99 }
    }),
  }
}

async function fill(wrapper, { doctor = '1', department = '2', date = '2026-10-20' } = {}) {
  await wrapper.find('[data-doctor-id]').setValue(doctor)
  await wrapper.find('[data-department-id]').setValue(department)
  await wrapper.find('[data-visit-date]').setValue(date)
  await wrapper.find('[data-time-slot]').setValue('上午')
}

describe('AppointmentView list (TICKET-017)', () => {
  it('renders my appointments with the mapped status label', async () => {
    const client = fakeClient({ appointments: [row({ status: 1 })] })
    const wrapper = mount(AppointmentView, { props: { client } })
    await flushPromises()

    const rows = wrapper.findAll('[data-appointment-row]')
    expect(rows).toHaveLength(1)
    expect(rows[0].text()).toContain('李医生')
    expect(rows[0].text()).toContain('2026-10-20')
    expect(rows[0].text()).toContain('上午')
    expect(rows[0].text()).toContain('已确认')
  })

  it('shows an empty state when there are no appointments', async () => {
    const wrapper = mount(AppointmentView, { props: { client: fakeClient() } })
    await flushPromises()

    expect(wrapper.find('[data-empty]').text()).toContain('暂无')
  })

  it('shows an empty state and reports the failure when the list cannot load (AC-F-12)', async () => {
    const failure = Object.assign(new Error('无法加载'), { status: 500 })
    const wrapper = mount(AppointmentView, {
      props: { client: fakeClient({ loadError: failure }) },
    })
    await flushPromises()

    expect(wrapper.find('[data-error]').text()).toContain('加载失败')
    expect(wrapper.findAll('[data-appointment-row]')).toHaveLength(0)
    expect(wrapper.emitted('error')).toHaveLength(1)
  })
})

describe('AppointmentView submit (TICKET-017)', () => {
  it('requires doctor, department, date and time slot (FUNCTIONAL_SPEC 5.19)', async () => {
    const client = fakeClient()
    const wrapper = mount(AppointmentView, { props: { client } })
    await flushPromises()

    await wrapper.find('[data-appointment-form]').trigger('submit.prevent')
    await flushPromises()

    expect(wrapper.find('[data-form-error]').text()).toContain('必填')
    expect(client.createAppointment).not.toHaveBeenCalled()
  })

  it('submits through the client and reloads the list', async () => {
    const client = fakeClient()
    const wrapper = mount(AppointmentView, { props: { client } })
    await flushPromises()

    await fill(wrapper)
    await wrapper.find('[data-remark]').setValue('复诊')
    await wrapper.find('[data-appointment-form]').trigger('submit.prevent')
    await flushPromises()

    expect(client.createAppointment).toHaveBeenCalledWith({
      doctor_id: 1,
      department_id: 2,
      visit_date: '2026-10-20',
      time_slot: '上午',
      remark: '复诊',
    })
    expect(client.myAppointments).toHaveBeenCalledTimes(2)
  })

  it('reports a failed submission without clearing the form', async () => {
    const failure = Object.assign(new Error('失败'), { status: 422 })
    const client = fakeClient({ createError: failure })
    const wrapper = mount(AppointmentView, { props: { client } })
    await flushPromises()

    await fill(wrapper)
    await wrapper.find('[data-appointment-form]').trigger('submit.prevent')
    await flushPromises()

    expect(wrapper.emitted('error')).toHaveLength(1)
    expect(wrapper.find('[data-doctor-id]').element.value).toBe('1')
  })
})
