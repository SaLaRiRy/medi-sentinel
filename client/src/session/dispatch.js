/**
 * TICKET-028: the 401/403 split, wired to the pinia store and the router.
 *
 * The policy still lives in `session/guard.js` `applyApiError` (AC-F-07 /
 * AC-F-08): 401 clears the session and returns to login, 403 only surfaces a
 * notice. This adapter is the one place that also knows about navigation.
 */

import { applyApiError } from './guard.js'

export function createErrorDispatcher({ session, router }) {
  return function dispatch(error) {
    const outcome = applyApiError(error, session)
    if (outcome.action === 'login') router.push('/login')
    return outcome
  }
}
