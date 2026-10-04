import './styles/index.css'

import { bootstrap } from './bootstrap.js'

const { app } = await bootstrap()

app.mount('#app')
