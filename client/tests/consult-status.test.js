import { describe, expect, it } from 'vitest'

import {
  consultStatusColor,
  consultStatusLabel,
} from '../src/consult/status.js'

// AC-F-11 / FUNCTIONAL_SPEC 5.10: 工单 0/1 映射，未知值回退到既定默认「待回复」。
describe('consult status mapping (TICKET-019)', () => {
  it('labels the two states', () => {
    expect([0, 1].map(consultStatusLabel)).toEqual(['待回复', '已回复'])
  })

  it('falls back to the pending label for an unknown value', () => {
    expect(consultStatusLabel(9)).toBe('待回复')
    expect(consultStatusLabel(undefined)).toBe('待回复')
  })

  it('colors each state and falls back to the pending color', () => {
    expect([0, 1].map(consultStatusColor)).toEqual(['warning', 'success'])
    expect(consultStatusColor(9)).toBe('warning')
  })

})
