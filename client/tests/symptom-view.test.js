import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import SymptomView from '../src/views/SymptomView.vue'

function candidate(overrides = {}) {
  return {
    disease: '感冒',
    match_count: 2,
    coverage: 0.67,
    department: '呼吸内科',
    matched_symptoms: ['头痛', '发热'],
    ...overrides,
  }
}

function fakeClient({ candidates = [], fail } = {}) {
  return {
    inferGraph: vi.fn(async () => {
      if (fail) throw fail
      return candidates
    }),
  }
}

async function addSymptom(wrapper, text) {
  await wrapper.find('[data-symptom-input]').setValue(text)
  await wrapper.find('[data-add-symptom]').trigger('click')
}

describe('SymptomView (TICKET-016)', () => {
  it('adds symptoms, ignores duplicates and sends the standard list', async () => {
    const client = fakeClient({ candidates: [candidate()] })
    const wrapper = mount(SymptomView, { props: { client } })

    await addSymptom(wrapper, '头疼')
    await addSymptom(wrapper, '头疼')
    await addSymptom(wrapper, '发烧')
    await wrapper.find('[data-infer]').trigger('click')
    await flushPromises()

    expect(wrapper.findAll('[data-symptom-tag]')).toHaveLength(2)
    expect(client.inferGraph).toHaveBeenCalledWith(['头疼', '发烧'])
  })

  it('renders the candidates ordered by coverage with their department', async () => {
    const client = fakeClient({
      candidates: [
        candidate({ disease: '偏头痛', coverage: 0.33, department: null }),
        candidate({ disease: '感冒', coverage: 0.67 }),
      ],
    })
    const wrapper = mount(SymptomView, { props: { client } })

    await addSymptom(wrapper, '头痛')
    await addSymptom(wrapper, '发热')
    await wrapper.find('[data-infer]').trigger('click')
    await flushPromises()

    const rows = wrapper.findAll('[data-candidate]')
    expect(rows.map((row) => row.attributes('data-disease'))).toEqual(['感冒', '偏头痛'])
    expect(rows[0].text()).toContain('呼吸内科')
    expect(rows[1].text()).toContain('-')
  })

  it('shows a progress bar only when coverage is present (AC-F-14)', async () => {
    const client = fakeClient({
      candidates: [
        candidate({ disease: '有覆盖率', coverage: 0.5 }),
        candidate({ disease: '无覆盖率', coverage: null }),
      ],
    })
    const wrapper = mount(SymptomView, { props: { client } })

    await addSymptom(wrapper, '头痛')
    await wrapper.find('[data-infer]').trigger('click')
    await flushPromises()

    const without = wrapper.find('[data-disease="无覆盖率"]')
    expect(without.find('[data-coverage-bar]').exists()).toBe(false)
    expect(wrapper.find('[data-disease="有覆盖率"] [data-coverage-bar]').exists()).toBe(true)
  })

  it('shows an empty state when the graph returns no candidate', async () => {
    const client = fakeClient({ candidates: [] })
    const wrapper = mount(SymptomView, { props: { client } })

    await addSymptom(wrapper, '头痛')
    await wrapper.find('[data-infer]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-empty]').text()).toContain('未匹配')
  })

  it('shows an understandable error when the graph is unavailable', async () => {
    const failure = Object.assign(new Error('图谱服务不可用'), { status: 503 })
    const wrapper = mount(SymptomView, { props: { client: fakeClient({ fail: failure }) } })

    await addSymptom(wrapper, '头痛')
    await wrapper.find('[data-infer]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-error]').text()).toContain('图谱服务不可用')
    expect(wrapper.emitted('error')).toHaveLength(1)
  })

  it('cannot infer without any symptom', async () => {
    const client = fakeClient()
    const wrapper = mount(SymptomView, { props: { client } })

    expect(wrapper.find('[data-infer]').attributes('disabled')).toBeDefined()
    expect(client.inferGraph).not.toHaveBeenCalled()
  })
})
