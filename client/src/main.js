import { bootstrap } from './bootstrap.js'

const { app } = await bootstrap()

app.mount('#app')
