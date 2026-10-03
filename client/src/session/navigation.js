/**
 * F-3: the role → home / shell / menu model. The guard reads `homeFor`, the two
 * shells read `menuFor` / `portalNav`, and the header dropdown reads
 * `personalCenterFor` — so the "admin 10 items, doctor 4 items, personal center
 * only from the dropdown" rule lives in exactly one place (SPEC.md 6.2 AC-F-10).
 */

export const ROLE_HOME = {
  user: '/portal/home',
  doctor: '/doctor/dashboard',
  admin: '/admin/dashboard',
}

export const ROLE_LAYOUT = {
  user: 'portal',
  doctor: 'console',
  admin: 'console',
}

const PORTAL_NAV = [
  { label: '首页', to: '/portal/home' },
  { label: '智能问诊', to: '/portal/chat' },
  { label: '症状推理', to: '/portal/symptom' },
  { label: '人工问诊', to: '/portal/consult' },
  { label: '预约挂号', to: '/portal/appointment' },
  { label: '健康档案', to: '/portal/records' },
  { label: '健康科普', to: '/portal/articles' },
]

// Administrator: the ten views of the 管理后台,个人中心不在其中 (FUNCTIONAL_SPEC 2.12).
const ADMIN_MENU = [
  { label: '数据概览', to: '/admin/dashboard' },
  { label: '患者管理', to: '/admin/users' },
  { label: '医生管理', to: '/admin/doctors' },
  { label: '科室管理', to: '/admin/departments' },
  { label: '知识库管理', to: '/admin/knowledge' },
  { label: '图谱可视化', to: '/admin/graph' },
  { label: '人工问诊', to: '/admin/consults' },
  { label: '预约管理', to: '/admin/appointments' },
  { label: '文章管理', to: '/admin/articles' },
  { label: '公告管理', to: '/admin/notices' },
]

// Doctor: the four views of the 医生工作台, personal center excluded like the admin's.
const DOCTOR_MENU = [
  { label: '工作台', to: '/doctor/dashboard' },
  { label: '人工问诊', to: '/doctor/consults' },
  { label: '预约管理', to: '/doctor/appointments' },
  { label: '患者列表', to: '/doctor/patients' },
]

const MENUS = { user: [], doctor: DOCTOR_MENU, admin: ADMIN_MENU }

export function homeFor(role) {
  return ROLE_HOME[role] ?? null
}

export function layoutFor(role) {
  return ROLE_LAYOUT[role] ?? null
}

export function menuFor(role) {
  return MENUS[role] ?? []
}

export function portalNav() {
  return PORTAL_NAV
}

export function personalCenterFor(role) {
  const home = ROLE_HOME[role]
  if (!home) return null
  return { label: '个人中心', to: `${home.replace(/\/home$|\/dashboard$/, '')}/profile` }
}
