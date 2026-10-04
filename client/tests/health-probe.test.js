import { flushPromises } from '@vue/test-utils'
import { createMemoryHistory } from 'vue-router'
import { afterEach, describe, expect, it } from 'vitest'

import { bootstrap } from '../src/bootstrap.js'

/**
 * Regression for the TICKET-028 start-up race: the app mounted before the
 * router's first navigation resolved, so App rendered a layout without its
 * `client` prop and HealthView's probe threw without ever sending a request.
 *
 * This drives the real main.js start-up order through `bootstrap()` and mounts
 * exactly as main.js does, so it goes red if the race comes back.
 */

const originalFetch = globalThis.fetch

afterEach(() => {
  globalThis.fetch = originalFetch
})

function stubFetch() {
  const calls = []
  globalThis.fetch = async (url) => {
    calls.push(String(url))
    return {
      status: 200,
      json: async () => ({
        code: 200,
        message: 'ok',
        data: { status: 'ok', database: 'ok', version: '1.0.0' },
      }),
    }
  }
  return calls
}

async function settle() {
  await new Promise((resolve) => setTimeout(resolve, 0))
  await flushPromises()
}

describe('start-up health probe (TICKET-028)', () => {
  it('sends GET /api/v1/health and does not show 后端不可用', async () => {
    const calls = stubFetch()
    const { app } = await bootstrap({ history: createMemoryHistory() })

    const el = document.createElement('div')
    document.body.appendChild(el)
    app.mount(el)
    await settle()

    expect(calls).toContain('/api/v1/health')
    expect(el.textContent).not.toContain('后端不可用')

    app.unmount()
    el.remove()
  })
})
