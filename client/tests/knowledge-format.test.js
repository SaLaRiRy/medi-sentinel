import { describe, expect, it } from 'vitest'

import { formatFileSize } from '../src/knowledge/format.js'

describe('formatFileSize (phase 2)', () => {
  it('renders bytes, KB and MB with a readable unit', () => {
    expect(formatFileSize(512)).toBe('512 B')
    expect(formatFileSize(3481)).toBe('3.4 KB')
    expect(formatFileSize(65433)).toBe('63.9 KB')
    expect(formatFileSize(2 * 1024 * 1024)).toBe('2.0 MB')
  })

  it('falls back to a dash for missing or invalid values', () => {
    expect(formatFileSize(undefined)).toBe('-')
    expect(formatFileSize(null)).toBe('-')
    expect(formatFileSize('not-a-number')).toBe('-')
    expect(formatFileSize(-1)).toBe('-')
  })
})
