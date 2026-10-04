import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import ProfilePanel from '../src/components/ProfilePanel.vue'
import LoginView from '../src/views/LoginView.vue'
import RegisterView from '../src/views/RegisterView.vue'

describe('LoginView (TICKET-012)', () => {
  it('submits the credentials through the API client and reports success', async () => {
    const client = {
      login: vi.fn(async () => ({ access_token: 't', role: 'doctor' })),
    }
    const wrapper = mount(LoginView, { props: { client } })

    // TICKET-029: role is now an el-select; drive its model.
    await wrapper.findComponent('[data-role]').setValue('doctor')
    await wrapper.find('[data-username]').setValue('shared')
    await wrapper.find('[data-password]').setValue('doctor-pass')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()

    expect(client.login).toHaveBeenCalledWith({
      username: 'shared',
      password: 'doctor-pass',
      role: 'doctor',
    })
    expect(wrapper.emitted('authenticated')).toHaveLength(1)
  })

  it('shows the server message when the login fails (401 stays on the form)', async () => {
    const client = {
      login: vi.fn(async () => {
        throw new Error('用户名或密码错误')
      }),
    }
    const wrapper = mount(LoginView, { props: { client } })

    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()

    expect(wrapper.find('[data-error]').text()).toContain('用户名或密码错误')
    expect(wrapper.emitted('authenticated')).toBeUndefined()
  })
})

describe('RegisterView (TICKET-012)', () => {
  it('registers a patient through the API client', async () => {
    const client = { register: vi.fn(async () => ({ access_token: 't', role: 'user' })) }
    const wrapper = mount(RegisterView, { props: { client } })

    await wrapper.find('[data-username]').setValue('newcomer')
    await wrapper.find('[data-password]').setValue('secret1')
    await wrapper.find('[data-confirm]').setValue('secret1')
    await wrapper.find('[data-real-name]').setValue('新患者')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()

    expect(client.register).toHaveBeenCalledWith({
      username: 'newcomer',
      password: 'secret1',
      confirm_password: 'secret1',
      real_name: '新患者',
      phone: '',
    })
    expect(wrapper.emitted('authenticated')).toHaveLength(1)
  })
})

describe('ProfilePanel (TICKET-012)', () => {
  it('loads the profile and saves the edited fields', async () => {
    const client = {
      profileInfo: vi.fn(async () => ({
        id: 1,
        username: 'shared',
        role: 'user',
        display_name: '张三',
        real_name: '张三',
        phone: '13800000000',
      })),
      profileUpdate: vi.fn(async () => null),
      changePassword: vi.fn(async () => null),
    }
    const wrapper = mount(ProfilePanel, { props: { client, role: 'user' } })
    await flushPromises()

    expect(wrapper.find('[data-display-name]').text()).toContain('张三')

    await wrapper.find('[data-field="real_name"]').setValue('张小三')
    await wrapper.find('[data-save]').trigger('click')
    await flushPromises()

    expect(client.profileUpdate).toHaveBeenCalledWith({ real_name: '张小三' })
  })

  it('changes the password through the API client', async () => {
    const client = {
      profileInfo: vi.fn(async () => ({ role: 'user', display_name: '张三' })),
      profileUpdate: vi.fn(async () => null),
      changePassword: vi.fn(async () => null),
    }
    const wrapper = mount(ProfilePanel, { props: { client, role: 'user' } })
    await flushPromises()

    await wrapper.find('[data-old-password]').setValue('old-pass')
    await wrapper.find('[data-new-password]').setValue('new-pass')
    await wrapper.find('[data-change-password]').trigger('click')
    await flushPromises()

    expect(client.changePassword).toHaveBeenCalledWith({
      old_password: 'old-pass',
      new_password: 'new-pass',
    })
  })
})
