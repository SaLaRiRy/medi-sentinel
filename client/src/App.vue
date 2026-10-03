<script setup>
import { computed, ref } from 'vue'

import { createApiClient } from './api/client.js'
import ProfilePanel from './components/ProfilePanel.vue'
import ConsoleShell from './layouts/ConsoleShell.vue'
import PortalShell from './layouts/PortalShell.vue'
import { createSessionStore } from './session/store.js'
import { applyApiError } from './session/guard.js'
import { layoutFor } from './session/navigation.js'
import LoginView from './views/LoginView.vue'
import RegisterView from './views/RegisterView.vue'
import HealthView from './views/HealthView.vue'

const session = createSessionStore()
const client = createApiClient({ session })

const auth = ref(session.get())
const screen = ref('login') // login | register | home | profile
const notice = ref(null)

const layout = computed(() => layoutFor(auth.value.role))

function onAuthenticated() {
  auth.value = session.get()
  screen.value = 'home'
  notice.value = null
}

function logout() {
  client.logout()
  auth.value = session.get()
  screen.value = 'login'
}

function onNavigate(to) {
  notice.value = null
  screen.value = String(to).endsWith('/profile') ? 'profile' : 'home'
}

// The guard is the single auth pivot: 401 clears and returns to login, 403 only
// surfaces a notice (SPEC.md 6.2 AC-F-07 / AC-F-08).
function handleError(error) {
  const outcome = applyApiError(error, session)
  notice.value = outcome.message
  if (outcome.action === 'login') {
    auth.value = session.get()
    screen.value = 'login'
  }
}
</script>

<template>
  <div class="app">
    <p v-if="notice && auth.token" data-notice class="app__notice">{{ notice }}</p>

    <template v-if="!auth.token">
      <LoginView
        v-if="screen === 'login'"
        :client="client"
        @authenticated="onAuthenticated"
        @error="handleError"
        @register="screen = 'register'"
      />
      <RegisterView
        v-else
        :client="client"
        @authenticated="onAuthenticated"
        @error="handleError"
        @login="screen = 'login'"
      />
      <!-- TICKET-001 的健康状态仍可见：未登录页脚展示后端可达性。 -->
      <HealthView :client="client" />
    </template>

    <template v-else>
      <ProfilePanel
        v-if="screen === 'profile'"
        :client="client"
        :role="auth.role"
        @error="handleError"
        @back="screen = 'home'"
      />
      <PortalShell
        v-else-if="layout === 'portal'"
        @logout="logout"
        @navigate="onNavigate"
      >
        <p>患者门户已就位</p>
      </PortalShell>
      <ConsoleShell v-else :role="auth.role" @logout="logout" @navigate="onNavigate">
        <p>管理台已就位</p>
      </ConsoleShell>
    </template>
  </div>
</template>
