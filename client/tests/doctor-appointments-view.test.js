import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import DoctorAppointmentsView from '../src/views/DoctorAppointmentsView.vue'

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

function fakeClient({ appointments = [], loadError, updateError } = {}) {
  return {
    doctorAppointments: vi.fn(async () => {
      if (loadError) throw loadError
      return appointments
    }),
    updateAppointmentStatus: vi.fn(async () => {
      if (updateError) throw updateError
      return null
    }),
  }
}

describe('DoctorAppointmentsView (TICKET-017)', () => {
  it('renders the schedule with a colored status label', async () => {
    const client = fakeClient({ appointments: [row({ status: 1 })] })
    const wrapper = mount(DoctorAppointmentsView, { props: { client } })
    await flushPromises()

    // TICKET-029: rows are grouped by Element Plus' stable `.el-table__row`.
    const rows = wrapper.findAll('.el-table__row')
    expect(rows).toHaveLength(1)
    expect(rows[0].text()).toContain('张三')
    expect(rows[0].text()).toContain('2026-10-20')
    expect(rows[0].find('[data-status]').text()).toBe('已确认')
    expect(rows[0].find('[data-status]').attributes('data-status-color')).toBe(
      'success'
    )
  })

  it('shows the empty state when the doctor has no appointments', async () => {
    const wrapper = mount(DoctorAppointmentsView, {
      props: { client: fakeClient() },
    })
    await flushPromises()

    expect(wrapper.find('[data-empty]').text()).toContain('暂无')
  })

  it('shows an empty state and reports the failure when the schedule cannot load', async () => {
    const failure = Object.assign(new Error('无法加载'), { status: 500 })
    const wrapper = mount(DoctorAppointmentsView, {
      props: { client: fakeClient({ loadError: failure }) },
    })
    await flushPromises()

    expect(wrapper.find('[data-error]').text()).toContain('加载失败')
    expect(wrapper.emitted('error')).toHaveLength(1)
  })

  it('updates a status through the client and reloads', async () => {
    const client = fakeClient({ appointments: [row({ id: 7, status: 0 })] })
    const wrapper = mount(DoctorAppointmentsView, { props: { client } })
    await flushPromises()

    // TICKET-029: scope the action to the visible row (ElTable also renders a
    // hidden measurement copy of every cell).
    await wrapper.find('.el-table__row').find('[data-set-status="1"]').trigger('click')
    await flushPromises()

    expect(client.updateAppointmentStatus).toHaveBeenCalledWith(7, 1)
    expect(client.doctorAppointments).toHaveBeenCalledTimes(2)
  })

  it('reports a failed status update', async () => {
    const failure = Object.assign(new Error('预约不存在'), { status: 404 })
    const client = fakeClient({
      appointments: [row()],
      updateError: failure,
    })
    const wrapper = mount(DoctorAppointmentsView, { props: { client } })
    await flushPromises()

    await wrapper.find('.el-table__row').find('[data-set-status="2"]').trigger('click')
    await flushPromises()

    expect(wrapper.emitted('error')[0][0]).toBe(failure)
  })
})
