import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import GraphView from '../src/views/GraphView.vue'

const OVERVIEW = {
  nodes: [
    { id: 'Disease:高血压', name: '高血压', label: 'Disease' },
    { id: 'Symptom:头痛', name: '头痛', label: 'Symptom' },
    { id: 'Department:心血管内科', name: '心血管内科', label: 'Department' },
  ],
  edges: [
    { source: 'Disease:高血压', target: 'Symptom:头痛', type: 'HAS_SYMPTOM' },
  ],
}

const SUBGRAPH = {
  nodes: [
    { id: 'Disease:高血压', name: '高血压', label: 'Disease' },
    { id: 'Drug:氨氯地平', name: '氨氯地平', label: 'Drug' },
  ],
  edges: [
    { source: 'Disease:高血压', target: 'Drug:氨氯地平', type: 'RECOMMEND_DRUG' },
  ],
}

const DETAIL = {
  disease: '高血压',
  department: '心血管内科',
  nodes: SUBGRAPH.nodes,
  edges: SUBGRAPH.edges,
}

function fakeClient({ fail } = {}) {
  return {
    graphOverview: vi.fn(async () => {
      if (fail) throw fail
      return OVERVIEW
    }),
    graphSearch: vi.fn(async () => [
      { id: 'Disease:高血压', name: '高血压', label: 'Disease' },
    ]),
    graphNeighbors: vi.fn(async () => SUBGRAPH),
    graphDisease: vi.fn(async () => DETAIL),
    graphStats: vi.fn(async () => ({ Disease: 3 })),
  }
}

async function search(wrapper, keyword) {
  await wrapper.find('[data-search-keyword]').setValue(keyword)
  await wrapper.find('[data-search]').trigger('submit.prevent')
  await flushPromises()
}

describe('GraphView (TICKET-016)', () => {
  it('renders the full graph with coloured node groups and mapped relations', async () => {
    const client = fakeClient()
    const wrapper = mount(GraphView, { props: { client } })
    await flushPromises()

    expect(client.graphOverview).toHaveBeenCalledTimes(1)
    expect(wrapper.findAll('[data-node]')).toHaveLength(3)
    expect(wrapper.find('[data-node="高血压"]').attributes('data-node-group')).toBe('disease')
    expect(wrapper.find('[data-node="头痛"]').attributes('data-node-group')).toBe('symptom')
    expect(wrapper.find('[data-node="心血管内科"]').attributes('data-node-group')).toBe('other')
    expect(wrapper.find('[data-edge]').text()).toContain('有症状')
  })

  it('searches entities and loads the neighbourhood of a selected result', async () => {
    const client = fakeClient()
    const wrapper = mount(GraphView, { props: { client } })
    await flushPromises()

    await search(wrapper, '高')
    expect(client.graphSearch).toHaveBeenCalledWith('高')
    await wrapper.find('[data-search-result]').trigger('click')
    await flushPromises()

    expect(client.graphNeighbors).toHaveBeenCalledWith('高血压', 1)
    const nodes = wrapper.findAll('[data-node]')
    expect(nodes.map((node) => node.attributes('data-node'))).toEqual(['高血压', '氨氯地平'])
    expect(wrapper.find('[data-edge]').text()).toContain('推荐药物')
  })

  it('loads the disease detail when the selected entity is a disease', async () => {
    const client = fakeClient()
    const wrapper = mount(GraphView, { props: { client } })
    await flushPromises()

    await search(wrapper, '高')
    await wrapper.find('[data-search-result]').trigger('click')
    await flushPromises()

    expect(client.graphDisease).toHaveBeenCalledWith('高血压')
    expect(wrapper.find('[data-disease-detail]').text()).toContain('心血管内科')
  })

  it('re-queries the neighbourhood when the depth changes', async () => {
    const client = fakeClient()
    const wrapper = mount(GraphView, { props: { client } })
    await flushPromises()
    await search(wrapper, '高')
    await wrapper.find('[data-search-result]').trigger('click')
    await flushPromises()

    await wrapper.find('[data-depth]').setValue('3')
    await flushPromises()

    expect(client.graphNeighbors).toHaveBeenLastCalledWith('高血压', 3)
  })

  it('shows an understandable error when the graph is unavailable', async () => {
    const failure = Object.assign(new Error('图谱服务不可用'), { status: 503 })
    const wrapper = mount(GraphView, { props: { client: fakeClient({ fail: failure }) } })
    await flushPromises()

    expect(wrapper.find('[data-error]').text()).toContain('图谱服务不可用')
    expect(wrapper.emitted('error')).toHaveLength(1)
  })
})
