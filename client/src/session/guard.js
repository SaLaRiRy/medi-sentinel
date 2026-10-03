/** F-3: route access and the 401/403 split — the only place either is decided. */

import { ROLE_HOME } from './navigation.js'

const KNOWN_ROLES = new Set(Object.keys(ROLE_HOME))

export function resolveAccess({ role, target }) {
  if (role !== null && role !== undefined && !KNOWN_ROLES.has(role)) {
    return { action: 'login', clearSession: true }
  }
  if (!target.requiresAuth) return { action: 'allow' }
  if (!role) return { action: 'login' }
  const allowed = target.roles ?? []
  if (allowed.length === 0 || allowed.includes(role)) return { action: 'allow' }
  return { action: 'redirect', to: ROLE_HOME[role] }
}

export function applyApiError(error, session) {
  if (error.status === 401) {
    session.clear()
    return { action: 'login', message: error.message }
  }
  return { action: 'notify', message: error.message }
}
