/**
 * TICKET-028: vue-router with the F-3 guard wired in.
 *
 * The guard is the only auth pivot: it reuses `session/guard.js` resolveAccess
 * verbatim, so the role / unknown-role / public semantics match the framework-free
 * route table that 014–022 were built and tested against (AC-F-09).
 */

import { createRouter, createWebHistory } from 'vue-router'

import { resolveAccess } from '../session/guard.js'
import { homeFor } from '../session/navigation.js'
import { useAuthStore } from '../stores/auth.js'
import { routes } from './routes.js'

export function installAuthGuard(router, pinia) {
  router.beforeEach((to) => {
    const auth = useAuthStore(pinia)

    // `/` and any unbuilt path under a role land on that role's home.
    if (to.meta.redirectToHome) {
      const home = homeFor(auth.role)
      return home ? { path: home } : { path: '/login' }
    }

    const outcome = resolveAccess({ role: auth.role, target: to.meta })
    if (outcome.action === 'login') {
      if (outcome.clearSession) auth.clear()
      return { path: '/login' }
    }
    if (outcome.action === 'redirect') {
      return { path: outcome.to }
    }
    if (to.meta.guestOnly && auth.isAuthenticated) {
      return { path: homeFor(auth.role) ?? '/login' }
    }
    return true
  })

  return router
}

export function createAppRouter({ history = createWebHistory(), pinia } = {}) {
  const router = createRouter({ history, routes })
  return installAuthGuard(router, pinia)
}
