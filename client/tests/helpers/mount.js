/**
 * TICKET-028: one place that knows how to mount a component with the app's
 * plugins (pinia auth store + vue-router), so tests don't each rebuild them.
 *
 * Element Plus opens poppers (el-dropdown / el-tooltip) through a 0ms timer, so
 * `settle()` flushes both that timer and the pending promises.
 */

import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory } from 'vue-router'

import { createAppRouter } from '../../src/router/index.js'

export function createTestPinia() {
  const pinia = createPinia()
  setActivePinia(pinia)
  return pinia
}

export function createTestRouter({ pinia, history = createMemoryHistory() } = {}) {
  return createAppRouter({ history, pinia })
}

export function mountWithPlugins(component, { pinia, router, ...options } = {}) {
  const testPinia = pinia ?? createTestPinia()
  const testRouter = router ?? createTestRouter({ pinia: testPinia })

  return mount(component, {
    ...options,
    global: {
      ...options.global,
      plugins: [testPinia, testRouter, ...(options.global?.plugins ?? [])],
    },
  })
}

export async function settle() {
  await new Promise((resolve) => setTimeout(resolve, 0))
  await flushPromises()
}
