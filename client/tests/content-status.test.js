import { describe, expect, it } from 'vitest'

import {
  ARTICLE_CATEGORIES,
  contentStatusColor,
  contentStatusLabel,
} from '../src/content/status.js'

// FUNCTIONAL_SPEC 5.20: 文章 / 公告状态 1 → 已发布（success）；其余 → 已下架（info）。
describe('article/notice status mapping (TICKET-021)', () => {
  it('maps 1 to 已发布 and every other value to 已下架', () => {
    expect(contentStatusLabel(1)).toBe('已发布')
    expect(contentStatusLabel(0)).toBe('已下架')
    expect(contentStatusLabel(9)).toBe('已下架')
    expect(contentStatusLabel(undefined)).toBe('已下架')
  })

  it('colors 1 success and every other value info', () => {
    expect(contentStatusColor(1)).toBe('success')
    expect(contentStatusColor(0)).toBe('info')
    expect(contentStatusColor(null)).toBe('info')
  })

  it('offers the six suggested categories from the functional spec', () => {
    expect(ARTICLE_CATEGORIES).toEqual([
      '健康科普',
      '疾病预防',
      '用药指南',
      '营养饮食',
      '运动康复',
      '其他',
    ])
  })
})
