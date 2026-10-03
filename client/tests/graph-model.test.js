import { describe, expect, it } from 'vitest'

import { coveragePercent, sortedCandidates } from '../src/graph/candidates.js'
import { nodeColor, nodeGroup, nodeGroupLabel } from '../src/graph/nodes.js'
import { relationLabel } from '../src/graph/relations.js'

// FUNCTIONAL_SPEC.md 5.20「前端状态展示映射规则」: node types collapse to the
// three legend groups 疾病 / 症状 / 其他, and unknown relationship names fall
// back to the raw value.
describe('node colouring (AC-F-11)', () => {
  it('keeps only Disease and Symptom in their own group', () => {
    expect(nodeGroup('Disease')).toBe('disease')
    expect(nodeGroup('Symptom')).toBe('symptom')
    for (const label of ['Department', 'Drug', 'Check', 'Food', 'Unknown']) {
      expect(nodeGroup(label)).toBe('other')
    }
  })

  it('gives the three legend groups a label and distinct colours', () => {
    expect(nodeGroupLabel('Disease')).toBe('疾病')
    expect(nodeGroupLabel('Symptom')).toBe('症状')
    expect(nodeGroupLabel('Drug')).toBe('其他')

    const colours = new Set([nodeColor('Disease'), nodeColor('Symptom'), nodeColor('Drug')])
    expect(colours.size).toBe(3)
  })
})

describe('relationship display (AC-F-11)', () => {
  it('maps the seven ontology relations to their display names', () => {
    expect(relationLabel('HAS_SYMPTOM')).toBe('有症状')
    expect(relationLabel('BELONGS_TO')).toBe('所属科室')
    expect(relationLabel('RECOMMEND_DRUG')).toBe('推荐药物')
    expect(relationLabel('NEED_CHECK')).toBe('需检查')
    expect(relationLabel('ACCOMPANY_WITH')).toBe('并发症')
    expect(relationLabel('SHOULD_EAT')).toBe('宜吃')
    expect(relationLabel('AVOID_EAT')).toBe('忌吃')
  })

  it('falls back to the raw relation name when it is unknown', () => {
    expect(relationLabel('NEW_RELATION')).toBe('NEW_RELATION')
  })
})

describe('candidate coverage (AC-F-14)', () => {
  it('orders candidates by coverage descending and missing coverage last', () => {
    const ordered = sortedCandidates([
      { disease: 'a', coverage: 0.2 },
      { disease: 'b', coverage: null },
      { disease: 'c', coverage: 0.8 },
    ]).map((candidate) => candidate.disease)

    expect(ordered).toEqual(['c', 'a', 'b'])
  })

  it('produces no percentage when coverage is missing', () => {
    expect(coveragePercent(0.5)).toBe(50)
    expect(coveragePercent(0)).toBe(0)
    expect(coveragePercent(undefined)).toBeNull()
    expect(coveragePercent(null)).toBeNull()
  })
})
