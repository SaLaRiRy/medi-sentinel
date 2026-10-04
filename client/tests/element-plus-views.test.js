/**
 * TICKET-029: the patient/doctor core views must be built from element-plus
 * components. This is a structural conformance test for the ticket's "每页要求"
 * section — it asserts the public component vocabulary each view owes the spec,
 * not internal markup. Behavioural guarantees stay in the per-view test files.
 */
import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import {
  ElButton,
  ElCard,
  ElDatePicker,
  ElForm,
  ElInput,
  ElProgress,
  ElSelect,
  ElTable,
  ElTag,
} from 'element-plus'

import ProfileView from '../src/views/ProfileView.vue'
import AppointmentView from '../src/views/AppointmentView.vue'
import ChatView from '../src/views/ChatView.vue'
import ConsultView from '../src/views/ConsultView.vue'
import DoctorAppointmentsView from '../src/views/DoctorAppointmentsView.vue'
import DoctorConsultsView from '../src/views/DoctorConsultsView.vue'
import DoctorPatientsView from '../src/views/DoctorPatientsView.vue'
import LoginView from '../src/views/LoginView.vue'
import PortalHomeView from '../src/views/PortalHomeView.vue'
import RecordsView from '../src/views/RecordsView.vue'
import RegisterView from '../src/views/RegisterView.vue'
import SymptomView from '../src/views/SymptomView.vue'
import { mountWithPlugins } from './helpers/mount.js'

function fakeClient(overrides = {}) {
  const base = {
    chatSessions: vi.fn(async () => []),
    chatMessages: vi.fn(async () => []),
    sendChat: vi.fn(async function* empty() {}),
    inferGraph: vi.fn(async () => []),
    myAppointments: vi.fn(async () => []),
    createAppointment: vi.fn(async () => ({})),
    doctors: vi.fn(async () => ({ items: [] })),
    departments: vi.fn(async () => []),
    doctorAppointments: vi.fn(async () => []),
    updateAppointmentStatus: vi.fn(async () => null),
    myRecords: vi.fn(async () => []),
    doctorRecords: vi.fn(async () => []),
    recordPatientOptions: vi.fn(async () => []),
    createRecord: vi.fn(async () => ({})),
    updateRecord: vi.fn(async () => ({})),
    deleteRecord: vi.fn(async () => null),
    myConsults: vi.fn(async () => []),
    createConsult: vi.fn(async () => ({})),
    pendingConsults: vi.fn(async () => []),
    replyConsult: vi.fn(async () => null),
    notices: vi.fn(async () => []),
    notice: vi.fn(async () => ({})),
    userOverview: vi.fn(async () => ({})),
    profileInfo: vi.fn(async () => ({ display_name: '张三' })),
    profileUpdate: vi.fn(async () => null),
    changePassword: vi.fn(async () => null),
    login: vi.fn(async () => ({})),
    register: vi.fn(async () => ({})),
  }
  return { ...base, ...overrides }
}

async function mountView(view, client = fakeClient()) {
  const wrapper = mount(view, { props: { client } })
  await flushPromises()
  return wrapper
}

function uses(wrapper, components) {
  for (const component of components) {
    expect(
      wrapper.findComponent(component).exists(),
      `${component.name ?? component} should be used`
    ).toBe(true)
  }
}

describe('TICKET-029 core views use element-plus components', () => {
  it('ChatView: el-card bubbles + el-input composer + el-button send', async () => {
    const client = fakeClient({
      chatSessions: vi.fn(async () => [{ id: 1, title: '旧会话', message_count: 2 }]),
      chatMessages: vi.fn(async () => [
        { id: 1, role: 'user', content: '旧问题' },
        { id: 2, role: 'assistant', content: '旧回答' },
      ]),
    })
    const wrapper = await mountView(ChatView, client)
    uses(wrapper, [ElCard, ElInput, ElButton])
  })

  it('SymptomView: el-form + el-input + el-button + el-progress coverage', async () => {
    const client = fakeClient({
      inferGraph: vi.fn(async () => [
        { disease: '感冒', match_count: 2, coverage: 0.67, department: '呼吸内科' },
      ]),
    })
    const wrapper = await mountView(SymptomView, client)
    await wrapper.find('[data-symptom-input]').setValue('头痛')
    await wrapper.find('[data-add-symptom]').trigger('click')
    await wrapper.find('[data-infer]').trigger('click')
    await flushPromises()
    uses(wrapper, [ElForm, ElInput, ElButton, ElProgress])
  })

  it('AppointmentView: el-form + el-select + el-date-picker + el-table', async () => {
    uses(await mountView(AppointmentView), [ElForm, ElSelect, ElDatePicker, ElTable])
  })

  it('DoctorAppointmentsView: el-table + el-tag status', async () => {
    const client = fakeClient({
      doctorAppointments: vi.fn(async () => [
        { id: 1, user_name: '张三', visit_date: '2026-10-20', time_slot: '上午', status: 1 },
      ]),
    })
    uses(await mountView(DoctorAppointmentsView, client), [ElTable, ElTag])
  })

  it('RecordsView: el-table', async () => {
    uses(await mountView(RecordsView), [ElTable])
  })

  it('DoctorPatientsView: el-form + el-select + el-date-picker + el-table', async () => {
    uses(await mountView(DoctorPatientsView), [ElForm, ElSelect, ElDatePicker, ElTable])
  })

  it('ConsultView: el-form + el-input + el-table', async () => {
    uses(await mountView(ConsultView), [ElForm, ElInput, ElTable])
  })

  it('DoctorConsultsView: el-table + el-input + el-button reply', async () => {
    const client = fakeClient({
      pendingConsults: vi.fn(async () => [
        { id: 3, user_name: '李四', chief_complaint: '咳嗽：一周', status: 0, replies: [] },
      ]),
    })
    uses(await mountView(DoctorConsultsView, client), [ElTable, ElInput, ElButton])
  })

  it('PortalHomeView: el-card hero/overview/sections (notices are a list, 图5)', async () => {
    uses(await mountView(PortalHomeView), [ElCard])
  })

  it('LoginView: el-form + el-select role + el-input + el-button', async () => {
    uses(await mountView(LoginView), [ElForm, ElSelect, ElInput, ElButton])
  })

  it('RegisterView: el-form + el-input + el-button', async () => {
    uses(await mountView(RegisterView), [ElForm, ElInput, ElButton])
  })

  it('ProfileView: el-form + el-input + el-button through the profile panel', async () => {
    const wrapper = mountWithPlugins(ProfileView, {
      props: { client: fakeClient() },
    })
    await flushPromises()
    uses(wrapper, [ElForm, ElInput, ElButton])
  })
})
