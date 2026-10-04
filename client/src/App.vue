<script setup>
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { createApiClient } from './api/client.js'
import ConsoleShell from './layouts/ConsoleShell.vue'
import PortalShell from './layouts/PortalShell.vue'
import PublicShell from './layouts/PublicShell.vue'
import { createErrorDispatcher } from './session/dispatch.js'
import { homeFor } from './session/navigation.js'
import { useAuthStore } from './stores/auth.js'

// TICKET-028: App is now the "outcome" layer. The route table + guard decide
// which view renders; App only picks the layout, keeps F-1 (api/client.js) as
// the single exit, and splits 401 (clear + login) from 403 (notice only).
const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

// F-1 stays the only exit: the client is built once over an adapter that reads
// and writes the pinia auth store.
const session = {
  get: () => ({ token: auth.token, role: auth.role, user: auth.user }),
  set: ({ token, role, user }) => auth.setSession({ token, role, user }),
  clear: () => auth.clear(),
}
const client = createApiClient({ session })

const notice = ref(null)
const dispatchError = createErrorDispatcher({ session, router })

const LAYOUTS = { portal: PortalShell, console: ConsoleShell, public: PublicShell }
const layout = computed(() => LAYOUTS[route.meta.layout] ?? PublicShell)
const layoutProps = computed(() => {
  if (route.meta.layout === 'console') return { role: auth.role }
  if (route.meta.layout === 'public') return { client }
  return {}
})

function onAuthenticated() {
  notice.value = null
  router.push(homeFor(auth.role) ?? '/login')
}

function logout() {
  client.logout()
  router.push('/login')
}

function navigate(to) {
  notice.value = null
  router.push(String(to))
}

function goRegister() {
  notice.value = null
  router.push('/register')
}

function goLogin() {
  notice.value = null
  router.push('/login')
}

function handleError(error) {
  notice.value = dispatchError(error).message
}
</script>

<template>
  <div class="app">
    <p v-if="notice && auth.isAuthenticated" data-notice class="app__notice">{{ notice }}</p>

    <component :is="layout" v-bind="layoutProps" @navigate="navigate" @logout="logout">
      <router-view v-slot="{ Component }">
        <component
          :is="Component"
          :client="client"
          @error="handleError"
          @authenticated="onAuthenticated"
          @register="goRegister"
          @login="goLogin"
        />
      </router-view>
    </component>
  </div>
</template>
