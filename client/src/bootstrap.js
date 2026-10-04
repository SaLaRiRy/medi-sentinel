/**
 * TICKET-028: the app start-up order, shared by `main.js` and the health-probe
 * regression test so both drive the exact same sequence.
 *
 * The router's first navigation is asynchronous: if the app mounts before it
 * resolves, `route.meta` is still empty, App renders a layout without its
 * `client` prop, and HealthView's mount-time probe throws on `undefined`
 * without ever sending a request. Bootstrap therefore waits for the router
 * before anything mounts.
 */

import { createPinia } from 'pinia'
import { createApp } from 'vue'

import App from './App.vue'
import { createAppRouter } from './router/index.js'

export async function bootstrap({ history } = {}) {
  const app = createApp(App)
  const pinia = createPinia()
  const router = createAppRouter({ pinia, history })

  app.use(pinia)
  app.use(router)

  // Wait for the first navigation (including the guard's redirect to /login) so
  // the first render already sees the resolved route and its layout props.
  await router.isReady()

  return { app, pinia, router }
}
