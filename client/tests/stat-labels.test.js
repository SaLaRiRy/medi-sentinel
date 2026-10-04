import { describe, expect, it } from 'vitest'

import {
  UNKNOWN_KNOWLEDGE_TYPE_LABEL,
  knowledgeTypeLabel,
} from '../src/stat/labels.js'

describe('stat display labels (AC-F-11)', () => {
  it('labels the known knowledge types', () => {
    expect(knowledgeTypeLabel('txt')).toBe('文本')
    expect(knowledgeTypeLabel('markdown')).toBe('Markdown')
    expect(knowledgeTypeLabel('pdf')).toBe('PDF')
    expect(knowledgeTypeLabel('doc')).toBe('Word')
    expect(knowledgeTypeLabel('unknown')).toBe(UNKNOWN_KNOWLEDGE_TYPE_LABEL)
  })

  it('falls back to the established default for an unknown value', () => {
    expect(knowledgeTypeLabel('medical-imaging')).toBe(
      UNKNOWN_KNOWLEDGE_TYPE_LABEL
    )
    expect(knowledgeTypeLabel(undefined)).toBe(UNKNOWN_KNOWLEDGE_TYPE_LABEL)
  })
})
