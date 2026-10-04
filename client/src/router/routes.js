/**
 * TICKET-028: the vue-router route table.
 *
 * `session/routes.js` ROUTE_TABLE stays the single source of truth for
 * (path → screen + access). Here we only attach the component, name and layout
 * each entry needs, so the role / requiresAuth semantics can never drift
 * between the guard and the menu model. 029/030 migrate the views themselves.
 */

import { roleForPath, ROUTE_TABLE } from '../session/routes.js'
import AdminAppointmentsView from '../views/AdminAppointmentsView.vue'
import AdminArticlesView from '../views/AdminArticlesView.vue'
import AdminConsultsView from '../views/AdminConsultsView.vue'
import AdminDashboardView from '../views/AdminDashboardView.vue'
import AdminDepartmentsView from '../views/AdminDepartmentsView.vue'
import AdminDoctorsView from '../views/AdminDoctorsView.vue'
import AdminNoticesView from '../views/AdminNoticesView.vue'
import AdminUsersView from '../views/AdminUsersView.vue'
import AppointmentView from '../views/AppointmentView.vue'
import ArticlesView from '../views/ArticlesView.vue'
import ChatView from '../views/ChatView.vue'
import ConsultView from '../views/ConsultView.vue'
import DoctorAppointmentsView from '../views/DoctorAppointmentsView.vue'
import DoctorConsultsView from '../views/DoctorConsultsView.vue'
import DoctorDashboardView from '../views/DoctorDashboardView.vue'
import DoctorPatientsView from '../views/DoctorPatientsView.vue'
import GraphView from '../views/GraphView.vue'
import KnowledgeView from '../views/KnowledgeView.vue'
import LoginView from '../views/LoginView.vue'
import PortalHomeView from '../views/PortalHomeView.vue'
import ProfileView from '../views/ProfileView.vue'
import RecordsView from '../views/RecordsView.vue'
import RegisterView from '../views/RegisterView.vue'
import SymptomView from '../views/SymptomView.vue'

// screen → component. `home` is role-dependent, so it is resolved separately.
const SCREEN_COMPONENTS = {
  login: LoginView,
  register: RegisterView,
  profile: ProfileView,
  chat: ChatView,
  symptom: SymptomView,
  appointment: AppointmentView,
  records: RecordsView,
  consult: ConsultView,
  articles: ArticlesView,
  knowledge: KnowledgeView,
  graph: GraphView,
  'doctor-appointments': DoctorAppointmentsView,
  'doctor-patients': DoctorPatientsView,
  'doctor-consults': DoctorConsultsView,
  'admin-appointments': AdminAppointmentsView,
  'admin-consults': AdminConsultsView,
  'admin-users': AdminUsersView,
  'admin-doctors': AdminDoctorsView,
  'admin-departments': AdminDepartmentsView,
  'admin-articles': AdminArticlesView,
  'admin-notices': AdminNoticesView,
}

const HOME_COMPONENTS = {
  user: PortalHomeView,
  doctor: DoctorDashboardView,
  admin: AdminDashboardView,
}

const LAYOUT_BY_ROLE = { user: 'portal', doctor: 'console', admin: 'console' }

// A blank component for the two redirect-only records (`/` and the catch-all);
// the guard always resolves them before anything renders.
const RedirectorView = { name: 'RedirectorView', render: () => null }

function toRoute(entry) {
  const role = roleForPath(entry.path)
  const component =
    entry.screen === 'home' ? HOME_COMPONENTS[role] : SCREEN_COMPONENTS[entry.screen]
  return {
    path: entry.path,
    name: entry.path.replace(/^\//, '').replace(/\//g, '-'),
    component,
    meta: {
      role,
      requiresAuth: entry.requiresAuth,
      roles: entry.roles ?? [],
      layout: LAYOUT_BY_ROLE[role] ?? 'public',
      guestOnly: !entry.requiresAuth,
    },
  }
}

export const routes = [
  {
    path: '/',
    name: 'root',
    component: RedirectorView,
    meta: { requiresAuth: true, roles: [], layout: 'public', redirectToHome: true },
  },
  ...ROUTE_TABLE.map(toRoute),
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: RedirectorView,
    meta: { requiresAuth: true, roles: [], layout: 'public', redirectToHome: true },
  },
]
