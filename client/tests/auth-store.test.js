import { beforeEach, describe, expect, it } from 'vitest'

import { useAuthStore } from '../src/stores/auth.js'
import { createTestPinia } from './helpers/mount.js'

describe('auth store (TICKET-028, F-3)', () => {
  beforeEach(() => {
    createTestPinia()
  })

  it('starts anonymous', () => {
    const auth = useAuthStore()

    expect(auth.token).toBeNull()
    expect(auth.role).toBeNull()
    expect(auth.user).toBeNull()
    expect(auth.isAuthenticated).toBe(false)
  })

  it('carries the user / role / token a login returns', () => {
    const auth = useAuthStore()

    auth.setSession({
      token: 'token-doctor',
      role: 'doctor',
      user: { id: 1, display_name: '王医生' },
    })

    expect(auth.token).toBe('token-doctor')
    expect(auth.role).toBe('doctor')
    expect(auth.user.display_name).toBe('王医生')
    expect(auth.isAuthenticated).toBe(true)
  })

  it('clears back to anonymous on logout', () => {
    const auth = useAuthStore()
    auth.setSession({ token: 't', role: 'user', user: { id: 2 } })

    auth.clear()

    expect(auth.token).toBeNull()
    expect(auth.role).toBeNull()
    expect(auth.user).toBeNull()
    expect(auth.isAuthenticated).toBe(false)
  })
})
