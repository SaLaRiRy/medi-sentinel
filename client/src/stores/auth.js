/**
 * F-3: the reactive auth state the router guard and the API client read.
 *
 * TICKET-028 moves the session state that used to live in `App.vue`'s `ref`
 * into one pinia store. `session/store.js` stays as the framework-free
 * adapter the API client is tested against; this store is the app-level state.
 */

import { defineStore } from 'pinia'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null,
    role: null,
    token: null,
  }),

  getters: {
    isAuthenticated: (state) => Boolean(state.token),
  },

  actions: {
    setSession({ token, role, user }) {
      this.token = token ?? null
      this.role = role ?? null
      this.user = user ?? null
    },

    clear() {
      this.token = null
      this.role = null
      this.user = null
    },
  },
})
