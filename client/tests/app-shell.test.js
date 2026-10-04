import { describe, expect, it } from 'vitest'

import App from '../src/App.vue'
import ProfilePanel from '../src/components/ProfilePanel.vue'
import { useAuthStore } from '../src/stores/auth.js'
import { createTestPinia, createTestRouter, mountWithPlugins, settle } from './helpers/mount.js'

// App builds its own API client over global fetch (F-1 stays the only exit),
// so the integration test stubs the network at the transport boundary.
function stubFetch() {
  globalThis.fetch = async () => ({
    status: 200,
    json: async () => ({
      code: 200,
      message: 'ok',
      data: {
        id: 1,
        username: 'admin',
        role: 'admin',
        display_name: '管理员',
        real_name: '管理员',
        nickname: '管理员',
        phone: '',
        email: 'admin@example.com',
      },
    }),
  })
}

describe('App outcome layer (TICKET-028)', () => {
  it('renders the login view for an anonymous visitor routed to a private path', async () => {
    stubFetch()
    const pinia = createTestPinia()
    const router = createTestRouter({ pinia })
    await router.push('/portal/chat')

    const wrapper = mountWithPlugins(App, { pinia, router })
    await settle()

    expect(router.currentRoute.value.path).toBe('/login')
    expect(wrapper.find('[data-role]').exists()).toBe(true)
    expect(wrapper.findAll('[data-menu-item]')).toHaveLength(0)
  })

  it('renders the console shell for a signed-in admin instead of a screen dispatch chain', async () => {
    stubFetch()
    const pinia = createTestPinia()
    useAuthStore(pinia).setSession({ token: 't', role: 'admin', user: { id: 1 } })
    const router = createTestRouter({ pinia })
    await router.push('/admin/profile')

    const wrapper = mountWithPlugins(App, { pinia, router })
    await settle()

    expect(wrapper.findAll('[data-menu-item]')).toHaveLength(10)
    expect(wrapper.findComponent(ProfilePanel).exists()).toBe(true)
  })

  it('clears the session and returns to login when a view reports a 401', async () => {
    stubFetch()
    const pinia = createTestPinia()
    const auth = useAuthStore(pinia)
    auth.setSession({ token: 't', role: 'admin', user: { id: 1 } })
    const router = createTestRouter({ pinia })
    await router.push('/admin/profile')

    const wrapper = mountWithPlugins(App, { pinia, router })
    await settle()

    wrapper.findComponent(ProfilePanel).vm.$emit('error', { status: 401, message: '登录已过期' })
    await settle()

    expect(auth.token).toBeNull()
    expect(router.currentRoute.value.path).toBe('/login')
  })

  it('only surfaces a notice on 403: the session survives and the route stays put', async () => {
    stubFetch()
    const pinia = createTestPinia()
    const auth = useAuthStore(pinia)
    auth.setSession({ token: 't', role: 'admin', user: { id: 1 } })
    const router = createTestRouter({ pinia })
    await router.push('/admin/profile')

    const wrapper = mountWithPlugins(App, { pinia, router })
    await settle()

    wrapper.findComponent(ProfilePanel).vm.$emit('error', { status: 403, message: '权限不足' })
    await settle()

    expect(auth.token).toBe('t')
    expect(router.currentRoute.value.path).toBe('/admin/profile')
    expect(wrapper.find('[data-notice]').text()).toBe('权限不足')
  })
})
