import { describe, expect, it } from 'vitest'

import { resolveAccess } from '../src/session/guard.js'
import { resolveNavigation, resolveRoute } from '../src/session/routes.js'

// No vue-router offline (TICKET-012 已确认): the front-end has a framework-free
// route table, and the F-3 guard is the single auth pivot that reads it.
describe('resolveRoute (TICKET-014)', () => {
  it('maps the patient chat path to its own screen for the patient role', () => {
    expect(resolveRoute('/portal/chat')).toEqual({
      path: '/portal/chat',
      screen: 'chat',
      requiresAuth: true,
      roles: ['user'],
    })
  })

  it('maps profile paths to the profile screen', () => {
    expect(resolveRoute('/portal/profile').screen).toBe('profile')
    expect(resolveRoute('/doctor/profile').screen).toBe('profile')
    expect(resolveRoute('/admin/profile').screen).toBe('profile')
  })

  it('maps the admin knowledge path to its own screen (TICKET-015)', () => {
    expect(resolveRoute('/admin/knowledge')).toEqual({
      path: '/admin/knowledge',
      screen: 'knowledge',
      requiresAuth: true,
      roles: ['admin'],
    })
  })

  it('maps the graph and symptom-inference paths to their own screens (TICKET-016)', () => {
    expect(resolveRoute('/admin/graph')).toEqual({
      path: '/admin/graph',
      screen: 'graph',
      requiresAuth: true,
      roles: ['admin'],
    })
    expect(resolveRoute('/portal/symptom')).toEqual({
      path: '/portal/symptom',
      screen: 'symptom',
      requiresAuth: true,
      roles: ['user'],
    })
  })

  it('falls back to the shell home for routes not built yet', () => {
    expect(resolveRoute('/admin/unknown')).toMatchObject({
      screen: 'home',
      roles: ['admin'],
    })
    expect(resolveRoute('/doctor/unknown')).toMatchObject({
      screen: 'home',
      roles: ['doctor'],
    })
  })

  it('maps the appointment paths to their own screens (TICKET-017)', () => {
    expect(resolveRoute('/portal/appointment')).toEqual({
      path: '/portal/appointment',
      screen: 'appointment',
      requiresAuth: true,
      roles: ['user'],
    })
    expect(resolveRoute('/doctor/appointments')).toEqual({
      path: '/doctor/appointments',
      screen: 'doctor-appointments',
      requiresAuth: true,
      roles: ['doctor'],
    })
    expect(resolveRoute('/admin/appointments')).toEqual({
      path: '/admin/appointments',
      screen: 'admin-appointments',
      requiresAuth: true,
      roles: ['admin'],
    })
  })

  it('maps the health record paths to their own screens (TICKET-018)', () => {
    expect(resolveRoute('/portal/records')).toEqual({
      path: '/portal/records',
      screen: 'records',
      requiresAuth: true,
      roles: ['user'],
    })
    expect(resolveRoute('/doctor/patients')).toEqual({
      path: '/doctor/patients',
      screen: 'doctor-patients',
      requiresAuth: true,
      roles: ['doctor'],
    })
  })

  it('maps the doctor-consult paths to their own screens (TICKET-019)', () => {
    expect(resolveRoute('/portal/consult')).toEqual({
      path: '/portal/consult',
      screen: 'consult',
      requiresAuth: true,
      roles: ['user'],
    })
    expect(resolveRoute('/doctor/consults')).toEqual({
      path: '/doctor/consults',
      screen: 'doctor-consults',
      requiresAuth: true,
      roles: ['doctor'],
    })
    expect(resolveRoute('/admin/consults')).toEqual({
      path: '/admin/consults',
      screen: 'admin-consults',
      requiresAuth: true,
      roles: ['admin'],
    })
  })

  it('keeps the login and register paths public', () => {
    expect(resolveRoute('/login').requiresAuth).toBe(false)
    expect(resolveRoute('/register').requiresAuth).toBe(false)
  })

  it('maps the master-data paths to their own screens (TICKET-020)', () => {
    expect(resolveRoute('/admin/users')).toEqual({
      path: '/admin/users',
      screen: 'admin-users',
      requiresAuth: true,
      roles: ['admin'],
    })
    expect(resolveRoute('/admin/doctors')).toEqual({
      path: '/admin/doctors',
      screen: 'admin-doctors',
      requiresAuth: true,
      roles: ['admin'],
    })
    expect(resolveRoute('/admin/departments')).toEqual({
      path: '/admin/departments',
      screen: 'admin-departments',
      requiresAuth: true,
      roles: ['admin'],
    })
  })
})

describe('route table + guard (AC-F-09)', () => {
  it('lets a patient open the chat', () => {
    expect(resolveAccess({ role: 'user', target: resolveRoute('/portal/chat') })).toEqual({
      action: 'allow',
    })
  })

  it('redirects a doctor away from the patient chat', () => {
    expect(resolveAccess({ role: 'doctor', target: resolveRoute('/portal/chat') })).toEqual({
      action: 'redirect',
      to: '/doctor/dashboard',
    })
  })

  it('sends an unauthenticated visitor to login', () => {
    expect(resolveAccess({ role: null, target: resolveRoute('/portal/chat') })).toEqual({
      action: 'login',
    })
  })

  it('clears and returns to login when the stored role is unknown', () => {
    expect(resolveAccess({ role: 'ghost', target: resolveRoute('/portal/chat') })).toEqual({
      action: 'login',
      clearSession: true,
    })
  })
})

describe('resolveNavigation (AC-F-09, App.vue 的唯一导航入口)', () => {
  it('resolves a patient chat navigation to the chat screen', () => {
    expect(resolveNavigation({ role: 'user', path: '/portal/chat' })).toEqual({
      action: 'allow',
      screen: 'chat',
    })
  })

  it('redirects a doctor to the doctor home screen', () => {
    expect(resolveNavigation({ role: 'doctor', path: '/portal/chat' })).toEqual({
      action: 'redirect',
      screen: 'home',
      to: '/doctor/dashboard',
    })
  })

  it('sends a visitor to the login screen', () => {
    expect(resolveNavigation({ role: null, path: '/portal/chat' })).toEqual({
      action: 'login',
      clearSession: false,
    })
  })

  it('clears an unknown role before showing login', () => {
    expect(resolveNavigation({ role: 'ghost', path: '/portal/chat' })).toEqual({
      action: 'login',
      clearSession: true,
    })
  })
})
