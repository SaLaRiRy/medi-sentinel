import { describe, expect, it } from 'vitest'

import {
  decodeChiefComplaint,
  encodeChiefComplaint,
} from '../src/consult/complaint.js'

// AC-F-15: 提交时「标题：正文」（全角冒号）；医生端按第一个全角冒号拆回。
describe('chief complaint codec (TICKET-019)', () => {
  it('joins title and body with a full-width colon', () => {
    expect(encodeChiefComplaint('头痛', '三天，伴发热')).toBe('头痛：三天，伴发热')
  })

  it('splits on the first full-width colon', () => {
    expect(decodeChiefComplaint('头痛：三天：伴发热')).toEqual({
      title: '头痛',
      body: '三天：伴发热',
    })
  })

  it('treats a complaint without a colon as a title with an empty body', () => {
    expect(decodeChiefComplaint('头痛三天')).toEqual({
      title: '头痛三天',
      body: '',
    })
  })

  it('tolerates an empty complaint', () => {
    expect(decodeChiefComplaint('')).toEqual({ title: '', body: '' })
    expect(decodeChiefComplaint(undefined)).toEqual({ title: '', body: '' })
  })

  it('round-trips a title and body pair', () => {
    const encoded = encodeChiefComplaint('咳嗽', '一周，夜间加重')

    expect(decodeChiefComplaint(encoded)).toEqual({
      title: '咳嗽',
      body: '一周，夜间加重',
    })
  })
})
