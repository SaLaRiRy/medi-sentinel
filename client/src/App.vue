<script setup>
import { computed, ref } from 'vue'

import { createApiClient } from './api/client.js'
import ProfilePanel from './components/ProfilePanel.vue'
import ConsoleShell from './layouts/ConsoleShell.vue'
import PortalShell from './layouts/PortalShell.vue'
import { createSessionStore } from './session/store.js'
import { applyApiError } from './session/guard.js'
import { layoutFor } from './session/navigation.js'
import { resolveNavigation } from './session/routes.js'
import AdminAppointmentsView from './views/AdminAppointmentsView.vue'
import AppointmentView from './views/AppointmentView.vue'
import ChatView from './views/ChatView.vue'
import DoctorAppointmentsView from './views/DoctorAppointmentsView.vue'
import DoctorPatientsView from './views/DoctorPatientsView.vue'
import GraphView from './views/GraphView.vue'
import LoginView from './views/LoginView.vue'
import RegisterView from './views/RegisterView.vue'
import HealthView from './views/HealthView.vue'
import KnowledgeView from './views/KnowledgeView.vue'
import RecordsView from './views/RecordsView.vue'
import SymptomView from './views/SymptomView.vue'

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

// Navigation is decided in one place: the route table says which screen a path
// maps to, and the F-3 guard is the only auth pivot that reads it (AC-F-09).
function onNavigate(to) {
  notice.value = null
  const outcome = resolveNavigation({ role: auth.value.role, path: String(to) })
  if (outcome.action === 'login') {
    if (outcome.clearSession) {
      client.logout()
      auth.value = session.get()
    }
    screen.value = 'login'
    return
  }
  screen.value = outcome.screen
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
        <ChatView v-if="screen === 'chat'" :client="client" @error="handleError" />
        <SymptomView
          v-else-if="screen === 'symptom'"
          :client="client"
          @error="handleError"
        />
        <AppointmentView
          v-else-if="screen === 'appointment'"
          :client="client"
          @error="handleError"
        />
        <RecordsView
          v-else-if="screen === 'records'"
          :client="client"
          @error="handleError"
        />
        <p v-else>患者门户已就位</p>
      </PortalShell>
      <ConsoleShell v-else :role="auth.role" @logout="logout" @navigate="onNavigate">
        <KnowledgeView
          v-if="screen === 'knowledge'"
          :client="client"
          @error="handleError"
        />
        <GraphView
          v-else-if="screen === 'graph'"
          :client="client"
          @error="handleError"
        />
        <DoctorAppointmentsView
          v-else-if="screen === 'doctor-appointments'"
          :client="client"
          @error="handleError"
        />
        <AdminAppointmentsView
          v-else-if="screen === 'admin-appointments'"
          :client="client"
          @error="handleError"
        />
        <DoctorPatientsView
          v-else-if="screen === 'doctor-patients'"
          :client="client"
          @error="handleError"
        />
        <p v-else>管理台已就位</p>
      </ConsoleShell>
    </template>
  </div>
</template>
