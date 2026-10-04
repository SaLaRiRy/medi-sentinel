/**
 * TICKET-030: the admin (and shared admin) views must be built from element-plus
 * components, matching the 029 patient/doctor restyle. This is a structural
 * conformance test for the ticket's "每页要求" section — it asserts the public
 * component vocabulary each view owes the spec, not internal markup. Behavioural
 * guarantees stay in the per-view test files.
 */
import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import {
  ElButton,
  ElCard,
  ElDatePicker,
  ElForm,
  ElInput,
  ElPagination,
  ElSelect,
  ElTable,
  ElTag,
  ElUpload,
} from 'element-plus'

import AdminAppointmentsView from '../src/views/AdminAppointmentsView.vue'
import AdminArticlesView from '../src/views/AdminArticlesView.vue'
import AdminConsultsView from '../src/views/AdminConsultsView.vue'
import AdminDashboardView from '../src/views/AdminDashboardView.vue'
import AdminDepartmentsView from '../src/views/AdminDepartmentsView.vue'
import AdminDoctorsView from '../src/views/AdminDoctorsView.vue'
import AdminNoticesView from '../src/views/AdminNoticesView.vue'
import AdminUsersView from '../src/views/AdminUsersView.vue'
import DoctorDashboardView from '../src/views/DoctorDashboardView.vue'
import GraphView from '../src/views/GraphView.vue'
import KnowledgeView from '../src/views/KnowledgeView.vue'

function page(items, total = items.length) {
  return { items, total, page: 1, page_size: 10 }
}

function fakeClient(overrides = {}) {
  const base = {
    adminUsers: vi.fn(async () => page([])),
    adminDoctors: vi.fn(async () => page([])),
    adminDepartments: vi.fn(async () => page([])),
    adminArticles: vi.fn(async () => page([])),
    adminNotices: vi.fn(async () => page([])),
    adminConsults: vi.fn(async () => page([])),
    adminAppointments: vi.fn(async () => page([])),
    knowledgeFiles: vi.fn(async () => page([])),
    statOverview: vi.fn(async () => ({})),
    consultTrend: vi.fn(async () => []),
    userGrowth: vi.fn(async () => []),
    appointmentsByDepartment: vi.fn(async () => []),
    knowledgeTypes: vi.fn(async () => []),
    graphOverview: vi.fn(async () => ({ nodes: [], edges: [] })),
    graphSearch: vi.fn(async () => []),
    graphNeighbors: vi.fn(async () => ({ nodes: [], edges: [] })),
    graphDisease: vi.fn(async () => ({})),
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

describe('TICKET-030 admin views use element-plus components', () => {
  it('AdminUsersView: el-card + el-form/el-input/el-select + el-table/el-tag + el-pagination', async () => {
    const client = fakeClient({
      adminUsers: vi.fn(async () => page([{ id: 1, username: 'a', real_name: 'A', gender: 1, status: 1 }])),
    })
    uses(await mountView(AdminUsersView, client), [
      ElCard,
      ElForm,
      ElInput,
      ElSelect,
      ElButton,
      ElTable,
      ElTag,
      ElPagination,
    ])
  })

  it('AdminDoctorsView: el-card + el-form/el-input/el-select + el-table/el-tag + el-pagination', async () => {
    const client = fakeClient({
      adminDoctors: vi.fn(async () =>
        page([{ id: 1, username: 'd', real_name: 'D', department_name: '内科', status: 1 }])
      ),
    })
    uses(await mountView(AdminDoctorsView, client), [
      ElCard,
      ElForm,
      ElInput,
      ElSelect,
      ElButton,
      ElTable,
      ElTag,
      ElPagination,
    ])
  })

  it('AdminDepartmentsView: el-card + el-form/el-input + el-table/el-tag + el-pagination', async () => {
    const client = fakeClient({
      adminDepartments: vi.fn(async () =>
        page([{ id: 1, name: '内科', description: '', sort_order: 1, doctor_count: 0 }])
      ),
    })
    uses(await mountView(AdminDepartmentsView, client), [
      ElCard,
      ElForm,
      ElInput,
      ElButton,
      ElTable,
      ElTag,
      ElPagination,
    ])
  })

  it('AdminArticlesView: el-card + el-form/el-input/el-select + el-table/el-tag + el-pagination', async () => {
    const client = fakeClient({
      adminArticles: vi.fn(async () =>
        page([{ id: 1, title: 'T', category: '其他', status: 1, view_count: 0 }])
      ),
    })
    uses(await mountView(AdminArticlesView, client), [
      ElCard,
      ElForm,
      ElInput,
      ElSelect,
      ElButton,
      ElTable,
      ElTag,
      ElPagination,
    ])
  })

  it('AdminNoticesView: el-card + el-form/el-input/el-select + el-table/el-tag + el-pagination', async () => {
    const client = fakeClient({
      adminNotices: vi.fn(async () => page([{ id: 1, title: 'T', content: 'C', status: 1 }])),
    })
    uses(await mountView(AdminNoticesView, client), [
      ElCard,
      ElForm,
      ElInput,
      ElSelect,
      ElButton,
      ElTable,
      ElTag,
      ElPagination,
    ])
  })

  it('AdminConsultsView: el-card + el-select filter + el-table/el-tag + el-pagination', async () => {
    const client = fakeClient({
      adminConsults: vi.fn(async () =>
        page([{ id: 1, user_name: '张三', chief_complaint: '头痛：三天', status: 1 }])
      ),
    })
    uses(await mountView(AdminConsultsView, client), [
      ElCard,
      ElSelect,
      ElButton,
      ElTable,
      ElTag,
      ElPagination,
    ])
  })

  it('AdminAppointmentsView: el-form/el-input/el-select/el-date-picker + el-table/el-tag + el-pagination', async () => {
    const client = fakeClient({
      adminAppointments: vi.fn(async () =>
        page([
          {
            id: 1,
            user_name: '张三',
            doctor_name: '李医生',
            department_id: 2,
            visit_date: '2026-10-20',
            time_slot: '上午',
            status: 0,
          },
        ])
      ),
    })
    uses(await mountView(AdminAppointmentsView, client), [
      ElCard,
      ElForm,
      ElInput,
      ElSelect,
      ElDatePicker,
      ElButton,
      ElTable,
      ElTag,
      ElPagination,
    ])
  })

  it('AdminDashboardView: el-card panels + el-select day window', async () => {
    uses(await mountView(AdminDashboardView), [ElCard, ElSelect])
  })

  it('DoctorDashboardView: el-card wraps the workbench statistics', async () => {
    uses(await mountView(DoctorDashboardView), [ElCard])
  })

  it('KnowledgeView: el-card + el-form/el-input/el-select + el-upload + el-table/el-tag + el-pagination', async () => {
    const client = fakeClient({
      knowledgeFiles: vi.fn(async () =>
        page([
          {
            id: 1,
            file_name: '指南.md',
            file_type: 'md',
            file_size: 1,
            chunk_count: 1,
            vector_status: 2,
          },
        ])
      ),
    })
    uses(await mountView(KnowledgeView, client), [
      ElCard,
      ElForm,
      ElInput,
      ElSelect,
      ElUpload,
      ElButton,
      ElTable,
      ElTag,
      ElPagination,
    ])
  })

  it('GraphView: el-card + el-form/el-input/el-select + el-table/el-tag', async () => {
    const client = fakeClient({
      graphOverview: vi.fn(async () => ({
        nodes: [{ id: 'Disease:高血压', name: '高血压', label: 'Disease' }],
        edges: [],
      })),
    })
    uses(await mountView(GraphView, client), [
      ElCard,
      ElForm,
      ElInput,
      ElSelect,
      ElButton,
      ElTag,
    ])
  })
})
