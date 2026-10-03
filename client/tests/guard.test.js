import { describe, expect, it } from 'vitest'

import { applyApiError, resolveAccess } from '../src/session/guard.js'
import { createSessionStore } from '../src/session/store.js'

describe('resolveAccess (F-3)', () => {
  it('lets a visitor reach a public route', () => {
    expect(
      resolveAccess({ role: null, target: { requiresAuth: false } })
    ).toEqual({ action: 'allow' })
  })

  it('sends an unauthenticated visitor to the login page', () => {
    expect(
      resolveAccess({ role: null, target: { requiresAuth: true, roles: ['doctor'] } })
    ).toEqual({ action: 'login' })
  })

  it('redirects a signed-in role away from a route it may not open', () => {
    expect(
      resolveAccess({
        role: 'doctor',
        target: { requiresAuth: true, roles: ['admin'] },
      })
    ).toEqual({ action: 'redirect', to: '/doctor/dashboard' })
  })

  it('allows a role its own route', () => {
    expect(
      resolveAccess({
        role: 'admin',
        target: { requiresAuth: true, roles: ['admin'] },
      })
    ).toEqual({ action: 'allow' })
  })

  it('clears the session when the stored role is not one of the three', () => {
    expect(
      resolveAccess({ role: 'ghost', target: { requiresAuth: true } })
    ).toEqual({ action: 'login', clearSession: true })
  })
})

describe('applyApiError (F-3)', () => {
  it('clears the session and navigates to login on 401', () => {
    const session = createSessionStore()
    session.set({ token: 't', role: 'user', user: { name: 'x' } })

    const outcome = applyApiError({ status: 401, message: '未登录' }, session)

    expect(outcome).toEqual({ action: 'login', message: '未登录' })
    expect(session.get().token).toBeNull()
  })

  it('only notifies on 403 and keeps the session', () => {
    const session = createSessionStore()
    session.set({ token: 't', role: 'user', user: { name: 'x' } })

    const outcome = applyApiError({ status: 403, message: '权限不足' }, session)

    expect(outcome).toEqual({ action: 'notify', message: '权限不足' })
    expect(session.get().token).toBe('t')
  })
})
