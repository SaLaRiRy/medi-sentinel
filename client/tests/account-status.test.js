import { describe, expect, it } from 'vitest'

import {
  accountStatusAction,
  accountStatusColor,
  accountStatusLabel,
} from '../src/account/status.js'

// FUNCTIONAL_SPEC 5.20 / AC-F-11: 1 正常 / 其余 禁用；按钮文案随当前状态取反。
describe('account status mapping (TICKET-020)', () => {
  it('maps 1 to 正常 and every other value to 禁用', () => {
    expect(accountStatusLabel(1)).toBe('正常')
    expect(accountStatusLabel(0)).toBe('禁用')
    expect(accountStatusLabel(5)).toBe('禁用')
    expect(accountStatusLabel(undefined)).toBe('禁用')
    expect(accountStatusLabel(null)).toBe('禁用')
  })

  it('colors 1 success and every other value danger', () => {
    expect(accountStatusColor(1)).toBe('success')
    expect(accountStatusColor(0)).toBe('danger')
    expect(accountStatusColor(9)).toBe('danger')
  })

  it('flips the action label against the current state', () => {
    expect(accountStatusAction(1)).toBe('禁用')
    expect(accountStatusAction(0)).toBe('启用')
    expect(accountStatusAction(9)).toBe('启用')
  })
})
