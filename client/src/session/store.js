/** F-3: the auth state the guard reads. Deliberately framework-free. */

const EMPTY = { token: null, role: null, user: null }

export function createSessionStore() {
  let state = { ...EMPTY }
  return {
    get: () => ({ ...state }),
    set({ token, role, user }) {
      state = { token, role, user }
    },
    clear() {
      state = { ...EMPTY }
    },
  }
}
