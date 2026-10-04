import { describe, expect, it } from 'vitest'

import ConsoleShell from '../src/layouts/ConsoleShell.vue'
import PortalShell from '../src/layouts/PortalShell.vue'
import { mountWithPlugins, settle } from './helpers/mount.js'

describe('ConsoleShell (F-3, AC-F-10)', () => {
  it('renders the ten admin side-menu items', () => {
    const wrapper = mountWithPlugins(ConsoleShell, { props: { role: 'admin' } })

    expect(wrapper.findAll('[data-menu-item]')).toHaveLength(10)
  })

  it('renders the four doctor side-menu items', () => {
    const wrapper = mountWithPlugins(ConsoleShell, { props: { role: 'doctor' } })

    expect(wrapper.findAll('[data-menu-item]')).toHaveLength(4)
  })

  it('keeps the personal center out of the side menu, reachable from the dropdown', async () => {
    const wrapper = mountWithPlugins(ConsoleShell, { props: { role: 'admin' } })

    expect(wrapper.find('[data-menu-item="个人中心"]').exists()).toBe(false)
    expect(wrapper.find('[data-personal-center]').exists()).toBe(false)

    await wrapper.find('[data-user-menu]').trigger('click')
    await settle()

    expect(wrapper.find('[data-personal-center]').text()).toBe('个人中心')
  })

  it('emits logout from the dropdown', async () => {
    const wrapper = mountWithPlugins(ConsoleShell, { props: { role: 'doctor' } })

    await wrapper.find('[data-user-menu]').trigger('click')
    await settle()
    await wrapper.find('[data-logout]').trigger('click')

    expect(wrapper.emitted('logout')).toHaveLength(1)
  })
})

describe('PortalShell (F-3, AC-F-10)', () => {
  it('renders the seven-item top navigation and the personal center in the dropdown', async () => {
    const wrapper = mountWithPlugins(PortalShell)

    expect(wrapper.findAll('[data-nav-item]')).toHaveLength(7)
    await wrapper.find('[data-user-menu]').trigger('click')
    await settle()
    expect(wrapper.find('[data-personal-center]').text()).toBe('个人中心')
  })
})
