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

  it('falls back to the shell home for routes not built yet', () => {
    expect(resolveRoute('/portal/appointment')).toMatchObject({
      screen: 'home',
      roles: ['user'],
    })
    expect(resolveRoute('/admin/users')).toMatchObject({
      screen: 'home',
      roles: ['admin'],
    })
    expect(resolveRoute('/doctor/consults')).toMatchObject({
      screen: 'home',
      roles: ['doctor'],
    })
  })

  it('keeps the login and register paths public', () => {
    expect(resolveRoute('/login').requiresAuth).toBe(false)
    expect(resolveRoute('/register').requiresAuth).toBe(false)
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
