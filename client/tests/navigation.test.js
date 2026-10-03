import { describe, expect, it } from 'vitest'

import {
  homeFor,
  layoutFor,
  menuFor,
  personalCenterFor,
  portalNav,
} from '../src/session/navigation.js'

describe('navigation (F-3)', () => {
  it('maps each role to its home and shell', () => {
    expect(homeFor('user')).toBe('/portal/home')
    expect(homeFor('doctor')).toBe('/doctor/dashboard')
    expect(homeFor('admin')).toBe('/admin/dashboard')
    expect(layoutFor('user')).toBe('portal')
    expect(layoutFor('doctor')).toBe('console')
    expect(layoutFor('admin')).toBe('console')
  })

  it('has no home for an unknown role', () => {
    expect(homeFor('ghost')).toBeNull()
    expect(layoutFor('ghost')).toBeNull()
  })

  it('generates the admin side menu with ten items', () => {
    const menu = menuFor('admin')

    expect(menu).toHaveLength(10)
    expect(menu.map((item) => item.to)).toEqual([
      '/admin/dashboard',
      '/admin/users',
      '/admin/doctors',
      '/admin/departments',
      '/admin/knowledge',
      '/admin/graph',
      '/admin/consults',
      '/admin/appointments',
      '/admin/articles',
      '/admin/notices',
    ])
  })

  it('generates the doctor side menu with four items', () => {
    const menu = menuFor('doctor')

    expect(menu).toHaveLength(4)
    expect(menu.map((item) => item.to)).toEqual([
      '/doctor/dashboard',
      '/doctor/consults',
      '/doctor/appointments',
      '/doctor/patients',
    ])
  })

  it('has no side menu for a patient', () => {
    expect(menuFor('user')).toEqual([])
  })

  it('keeps the personal center out of the side menu, reachable only from the dropdown', () => {
    const adminMenu = menuFor('admin')
    const doctorMenu = menuFor('doctor')

    expect(adminMenu.some((item) => item.to.endsWith('/profile'))).toBe(false)
    expect(doctorMenu.some((item) => item.to.endsWith('/profile'))).toBe(false)
    expect(personalCenterFor('admin')).toEqual({ label: '个人中心', to: '/admin/profile' })
    expect(personalCenterFor('doctor')).toEqual({ label: '个人中心', to: '/doctor/profile' })
    expect(personalCenterFor('user')).toEqual({ label: '个人中心', to: '/portal/profile' })
  })

  it('gives the patient portal a seven-item top navigation', () => {
    expect(portalNav()).toHaveLength(7)
  })
})
