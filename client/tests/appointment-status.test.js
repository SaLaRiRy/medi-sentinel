import { describe, expect, it } from 'vitest'

import {
  appointmentStatusColor,
  appointmentStatusLabel,
} from '../src/appointment/status.js'

// AC-F-11 / FUNCTIONAL_SPEC 5.20: 预约 0–3 映射，未知值回退到既定默认「待确认」。
describe('appointment status mapping (TICKET-017)', () => {
  it('labels the four states', () => {
    expect([0, 1, 2, 3].map(appointmentStatusLabel)).toEqual([
      '待确认',
      '已确认',
      '已完成',
      '已取消',
    ])
  })

  it('falls back to the pending label for an unknown value', () => {
    expect(appointmentStatusLabel(9)).toBe('待确认')
    expect(appointmentStatusLabel(undefined)).toBe('待确认')
  })

  it('colors each state and falls back to the pending color', () => {
    expect([0, 1, 2, 3].map(appointmentStatusColor)).toEqual([
      'warning',
      'success',
      'info',
      'danger',
    ])
    expect(appointmentStatusColor(9)).toBe('warning')
  })
})
