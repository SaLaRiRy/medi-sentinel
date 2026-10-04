import { beforeEach, describe, expect, it } from 'vitest'

import { routes } from '../src/router/routes.js'
import { ROUTE_TABLE } from '../src/session/routes.js'
import { useAuthStore } from '../src/stores/auth.js'
import { createTestPinia, createTestRouter } from './helpers/mount.js'

function freshRouter() {
  return createTestRouter()
}

describe('vue-router route table (TICKET-028)', () => {
  it('covers every path of the F-3 route table with a component and matching access meta', () => {
    const byPath = new Map(routes.map((route) => [route.path, route]))

    for (const entry of ROUTE_TABLE) {
      const route = byPath.get(entry.path)
      expect(route, `missing route for ${entry.path}`).toBeTruthy()
      expect(typeof route.component, `missing component for ${entry.path}`).not.toBe('undefined')
      expect(route.meta.requiresAuth).toBe(entry.requiresAuth)
      expect(route.meta.roles).toEqual(entry.roles ?? [])
    }
  })

  it('gives the patient portal and the console their own layouts', () => {
    const byPath = new Map(routes.map((route) => [route.path, route]))

    expect(byPath.get('/portal/chat').meta.layout).toBe('portal')
    expect(byPath.get('/doctor/dashboard').meta.layout).toBe('console')
    expect(byPath.get('/admin/dashboard').meta.layout).toBe('console')
    expect(byPath.get('/login').meta.layout).toBe('public')
  })
})

describe('router guard (TICKET-028, F-3 / AC-F-09)', () => {
  beforeEach(() => {
    createTestPinia()
  })

  it('sends an unauthenticated visitor to the login page', async () => {
    const router = freshRouter()

    await router.push('/portal/chat')

    expect(router.currentRoute.value.path).toBe('/login')
  })

  it('lets a patient open the chat', async () => {
    const auth = useAuthStore()
    auth.setSession({ token: 't', role: 'user', user: { id: 1 } })
    const router = freshRouter()

    await router.push('/portal/chat')

    expect(router.currentRoute.value.path).toBe('/portal/chat')
  })

  it('redirects a doctor away from the patient chat to the doctor home', async () => {
    const auth = useAuthStore()
    auth.setSession({ token: 't', role: 'doctor', user: { id: 1 } })
    const router = freshRouter()

    await router.push('/portal/chat')

    expect(router.currentRoute.value.path).toBe('/doctor/dashboard')
  })

  it('clears an unknown role and returns to login', async () => {
    const auth = useAuthStore()
    auth.setSession({ token: 't', role: 'ghost', user: { id: 1 } })
    const router = freshRouter()

    await router.push('/portal/chat')

    expect(router.currentRoute.value.path).toBe('/login')
    expect(auth.token).toBeNull()
  })

  it('sends a signed-in role from the root path to its home', async () => {
    const auth = useAuthStore()
    auth.setSession({ token: 't', role: 'admin', user: { id: 1 } })
    const router = freshRouter()

    await router.push('/')

    expect(router.currentRoute.value.path).toBe('/admin/dashboard')
  })

  it('falls back to the shell home for an unbuilt path under a role', async () => {
    const auth = useAuthStore()
    auth.setSession({ token: 't', role: 'admin', user: { id: 1 } })
    const router = freshRouter()

    await router.push('/admin/unknown')

    expect(router.currentRoute.value.path).toBe('/admin/dashboard')
  })

  it('keeps a signed-in user off the login page', async () => {
    const auth = useAuthStore()
    auth.setSession({ token: 't', role: 'user', user: { id: 1 } })
    const router = freshRouter()

    await router.push('/login')

    expect(router.currentRoute.value.path).toBe('/portal/home')
  })
})
