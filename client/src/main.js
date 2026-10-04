import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import { createAppRouter } from './router/index.js'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(createAppRouter({ pinia }))
app.mount('#app')
