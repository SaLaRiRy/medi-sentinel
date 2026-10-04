import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import DoctorPatientsView from '../src/views/DoctorPatientsView.vue'

function row(overrides = {}) {
  return {
    id: 1,
    user_id: 1,
    user_name: '张三',
    doctor_id: 1,
    doctor_name: '李医生',
    record_type: '门诊记录',
    diagnosis: '上呼吸道感染',
    treatment: '多休息',
    prescription: '感冒灵',
    visit_date: '2026-10-20',
    ...overrides,
  }
}

function fakeClient({
  records = [],
  options = [{ id: 1, name: '张三' }],
  loadError,
  createError,
  deleteError,
} = {}) {
  return {
    doctorRecords: vi.fn(async () => {
      if (loadError) throw loadError
      return records
    }),
    recordPatientOptions: vi.fn(async () => options),
    createRecord: vi.fn(async () => {
      if (createError) throw createError
      return { id: 99 }
    }),
    updateRecord: vi.fn(async () => ({})),
    deleteRecord: vi.fn(async () => {
      if (deleteError) throw deleteError
      return null
    }),
  }
}

async function fill(wrapper, { patient = 1, type = '门诊记录' } = {}) {
  // TICKET-029: el-select is a component; drive its model.
  await wrapper.findComponent('[data-patient-select]').setValue(patient)
  await wrapper.findComponent('[data-record-type]').setValue(type)
}

describe('DoctorPatientsView list (TICKET-018)', () => {
  it('renders the records under the doctor name', async () => {
    const wrapper = mount(DoctorPatientsView, {
      props: { client: fakeClient({ records: [row()] }) },
    })
    await flushPromises()

    // TICKET-029: ElTable rows are grouped by the stable `.el-table__row`.
    const rows = wrapper.findAll('.el-table__row')
    expect(rows).toHaveLength(1)
    expect(rows[0].text()).toContain('张三')
    expect(rows[0].text()).toContain('门诊记录')
    expect(rows[0].text()).toContain('上呼吸道感染')
  })

  it('shows the empty state and reports a failed load', async () => {
    const failure = Object.assign(new Error('无法加载'), { status: 500 })
    const wrapper = mount(DoctorPatientsView, {
      props: { client: fakeClient({ loadError: failure }) },
    })
    await flushPromises()

    expect(wrapper.find('[data-error]').text()).toContain('加载失败')
    expect(wrapper.emitted('error')).toHaveLength(1)
  })

  it('loads the patient options into the select', async () => {
    const client = fakeClient({ options: [{ id: 7, name: '李四' }] })
    const wrapper = mount(DoctorPatientsView, { props: { client } })
    await flushPromises()

    const options = wrapper.findAll('[data-patient-option]')
    expect(options).toHaveLength(1)
    expect(options[0].text()).toContain('李四')
    // TICKET-029: el-option does not render its `value` prop as an attribute.
    expect(wrapper.findComponent('[data-patient-option]').props('value')).toBe(7)
  })
})

describe('DoctorPatientsView create/edit/delete (TICKET-018)', () => {
  it('requires a patient and a record type (FUNCTIONAL_SPEC 5.19)', async () => {
    const client = fakeClient()
    const wrapper = mount(DoctorPatientsView, { props: { client } })
    await flushPromises()

    await wrapper.find('[data-record-form]').trigger('submit.prevent')
    await flushPromises()

    expect(wrapper.find('[data-form-error]').text()).toContain('必填')
    expect(client.createRecord).not.toHaveBeenCalled()
  })

  it('creates a record through the client and reloads', async () => {
    const client = fakeClient()
    const wrapper = mount(DoctorPatientsView, { props: { client } })
    await flushPromises()

    await fill(wrapper)
    await wrapper.find('[data-diagnosis]').setValue('感冒')
    await wrapper.find('[data-record-form]').trigger('submit.prevent')
    await flushPromises()

    expect(client.createRecord).toHaveBeenCalledWith({
      user_id: 1,
      record_type: '门诊记录',
      diagnosis: '感冒',
    })
    expect(client.doctorRecords).toHaveBeenCalledTimes(2)
  })

  it('edits a record in place and updates through the client', async () => {
    const client = fakeClient({ records: [row({ id: 7 })] })
    const wrapper = mount(DoctorPatientsView, { props: { client } })
    await flushPromises()

    await wrapper.find('.el-table__row').find('[data-edit="7"]').trigger('click')
    await flushPromises()
    await wrapper.find('[data-diagnosis]').setValue('已好转')
    await wrapper.find('[data-record-form]').trigger('submit.prevent')
    await flushPromises()

    expect(client.updateRecord).toHaveBeenCalledWith(7, {
      record_type: '门诊记录',
      diagnosis: '已好转',
      treatment: '多休息',
      prescription: '感冒灵',
      visit_date: '2026-10-20',
    })
    expect(client.doctorRecords).toHaveBeenCalledTimes(2)
  })

  it('deletes a record through the client and reloads', async () => {
    const client = fakeClient({ records: [row({ id: 7 })] })
    const wrapper = mount(DoctorPatientsView, { props: { client } })
    await flushPromises()

    await wrapper.find('.el-table__row').find('[data-delete="7"]').trigger('click')
    await flushPromises()

    expect(client.deleteRecord).toHaveBeenCalledWith(7)
    expect(client.doctorRecords).toHaveBeenCalledTimes(2)
  })

  it('reports a failed delete', async () => {
    const failure = Object.assign(new Error('档案不存在'), { status: 404 })
    const client = fakeClient({ records: [row({ id: 7 })], deleteError: failure })
    const wrapper = mount(DoctorPatientsView, { props: { client } })
    await flushPromises()

    await wrapper.find('.el-table__row').find('[data-delete="7"]').trigger('click')
    await flushPromises()

    expect(wrapper.emitted('error')[0][0]).toBe(failure)
  })
})
