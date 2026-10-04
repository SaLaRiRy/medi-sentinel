/**
 * F-3: the front-end's single route table, framework-free.
 *
 * 014–022 shipped without vue-router (012 时离线装不上), so the route table is
 * one plain map and the F-3 guard is the only auth pivot that reads it
 * (AC-F-09). Views never decide access themselves.
 *
 * TICKET-028 installed vue-router; `router/routes.js` now builds its records
 * from this table (path → screen + access), so this stays the single source of
 * truth for access semantics. `resolveRoute` / `resolveNavigation` are kept
 * until 029/030 finish migrating the views.
 */

import { resolveAccess } from './guard.js'

export const ROUTE_TABLE = [
  { path: '/login', screen: 'login', requiresAuth: false },
  { path: '/register', screen: 'register', requiresAuth: false },
  { path: '/portal/home', screen: 'home', requiresAuth: true, roles: ['user'] },
  { path: '/portal/chat', screen: 'chat', requiresAuth: true, roles: ['user'] },
  { path: '/portal/symptom', screen: 'symptom', requiresAuth: true, roles: ['user'] },
  {
    path: '/portal/appointment',
    screen: 'appointment',
    requiresAuth: true,
    roles: ['user'],
  },
  { path: '/portal/records', screen: 'records', requiresAuth: true, roles: ['user'] },
  { path: '/portal/consult', screen: 'consult', requiresAuth: true, roles: ['user'] },
  { path: '/portal/articles', screen: 'articles', requiresAuth: true, roles: ['user'] },
  { path: '/portal/profile', screen: 'profile', requiresAuth: true, roles: ['user'] },
  { path: '/doctor/dashboard', screen: 'home', requiresAuth: true, roles: ['doctor'] },
  {
    path: '/doctor/appointments',
    screen: 'doctor-appointments',
    requiresAuth: true,
    roles: ['doctor'],
  },
  {
    path: '/doctor/patients',
    screen: 'doctor-patients',
    requiresAuth: true,
    roles: ['doctor'],
  },
  {
    path: '/doctor/consults',
    screen: 'doctor-consults',
    requiresAuth: true,
    roles: ['doctor'],
  },
  { path: '/doctor/profile', screen: 'profile', requiresAuth: true, roles: ['doctor'] },
  { path: '/admin/dashboard', screen: 'home', requiresAuth: true, roles: ['admin'] },
  { path: '/admin/users', screen: 'admin-users', requiresAuth: true, roles: ['admin'] },
  {
    path: '/admin/doctors',
    screen: 'admin-doctors',
    requiresAuth: true,
    roles: ['admin'],
  },
  {
    path: '/admin/departments',
    screen: 'admin-departments',
    requiresAuth: true,
    roles: ['admin'],
  },
  { path: '/admin/knowledge', screen: 'knowledge', requiresAuth: true, roles: ['admin'] },
  { path: '/admin/graph', screen: 'graph', requiresAuth: true, roles: ['admin'] },
  {
    path: '/admin/appointments',
    screen: 'admin-appointments',
    requiresAuth: true,
    roles: ['admin'],
  },
  {
    path: '/admin/consults',
    screen: 'admin-consults',
    requiresAuth: true,
    roles: ['admin'],
  },
  {
    path: '/admin/articles',
    screen: 'admin-articles',
    requiresAuth: true,
    roles: ['admin'],
  },
  {
    path: '/admin/notices',
    screen: 'admin-notices',
    requiresAuth: true,
    roles: ['admin'],
  },
  { path: '/admin/profile', screen: 'profile', requiresAuth: true, roles: ['admin'] },
]

const ROLE_PREFIXES = [
  ['/portal', 'user'],
  ['/doctor', 'doctor'],
  ['/admin', 'admin'],
]

export function roleForPath(path) {
  const entry = ROLE_PREFIXES.find(([prefix]) => path.startsWith(prefix))
  return entry ? entry[1] : null
}

/**
 * The route a navigation target resolves to. A shell route that is not built
 * yet (tickets 15-22) still belongs to its role and lands on the shell home, so
 * the guard can keep deciding access for every path.
 */
export function resolveRoute(path) {
  const exact = ROUTE_TABLE.find((route) => route.path === path)
  if (exact) return exact
  const role = roleForPath(path)
  return {
    path,
    screen: 'home',
    requiresAuth: true,
    roles: role ? [role] : [],
  }
}

/**
 * The one navigation decision the app shell needs: `{role, path} → {action, screen}`.
 * `App.vue` only applies the outcome; all policy stays in the route table + guard.
 */
export function resolveNavigation({ role, path }) {
  const target = resolveRoute(path)
  const outcome = resolveAccess({ role, target })
  if (outcome.action === 'redirect') {
    return {
      action: 'redirect',
      screen: resolveRoute(outcome.to).screen,
      to: outcome.to,
    }
  }
  if (outcome.action === 'login') {
    return { action: 'login', clearSession: Boolean(outcome.clearSession) }
  }
  return { action: 'allow', screen: target.screen }
}
