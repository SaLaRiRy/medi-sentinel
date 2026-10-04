import { describe, expect, it, vi } from 'vitest'

import { createErrorDispatcher } from '../src/session/dispatch.js'
import { createSessionStore } from '../src/session/store.js'

function authedSession() {
  const session = createSessionStore()
  session.set({ token: 't', role: 'user', user: { id: 1 } })
  return session
}

describe('401 / 403 split (TICKET-028, AC-F-07 / AC-F-08)', () => {
  it('clears the session and navigates to login on 401', () => {
    const session = authedSession()
    const router = { push: vi.fn() }
    const dispatch = createErrorDispatcher({ session, router })

    const outcome = dispatch({ status: 401, message: '未登录' })

    expect(outcome).toEqual({ action: 'login', message: '未登录' })
    expect(session.get().token).toBeNull()
    expect(router.push).toHaveBeenCalledWith('/login')
  })

  it('only notifies on 403: keeps the session and does not navigate', () => {
    const session = authedSession()
    const router = { push: vi.fn() }
    const dispatch = createErrorDispatcher({ session, router })

    const outcome = dispatch({ status: 403, message: '权限不足' })

    expect(outcome).toEqual({ action: 'notify', message: '权限不足' })
    expect(session.get().token).toBe('t')
    expect(router.push).not.toHaveBeenCalled()
  })
})
