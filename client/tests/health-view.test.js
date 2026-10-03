import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import HealthView from '../src/views/HealthView.vue'

describe('HealthView', () => {
  it('renders what it fetched through the API client', async () => {
    const client = {
      health: async () => ({ status: 'ok', database: 'ok', version: '0.1.0' }),
    }

    const wrapper = mount(HealthView, { props: { client } })
    await flushPromises()

    expect(wrapper.text()).toContain('ok')
    expect(wrapper.text()).toContain('0.1.0')
  })

  it('renders an error state instead of a blank page when the call fails', async () => {
    const client = {
      health: async () => {
        throw new Error('backend unreachable')
      },
    }

    const wrapper = mount(HealthView, { props: { client } })
    await flushPromises()

    expect(wrapper.text()).toContain('后端不可用')
  })
})
