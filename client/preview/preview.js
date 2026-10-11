/**
 * 文档截图脚手架 —— **不是应用的一部分**，只在本地生成 `docs/images/` 的截图时使用。
 *
 * 用法（Vite dev server）：
 *   /preview/preview.html?role=admin&path=/admin/dashboard
 *   /preview/preview.html?role=doctor&path=/doctor/consults&action=ai-context
 *   /preview/preview.html?role=none&path=/login          ← 不登录，拍公开页
 *
 * 它刻意**复用应用的启动路径**（`bootstrap()` + F-1 的 `createApiClient`），
 * 因此截出来的就是应用本身的界面与真实接口数据，而不是另做一套假界面。
 * 放在 `client/preview/`（`src/` 之外）所以不会被架构测试扫到，也不进构建产物。
 *
 * 前置：后端要跑在 8000（Vite 的 `/api` 代理指向它），并已灌演示数据。
 * 「医生端 AI 上下文」那张还需要**一张关联到 AI 会话的待分配工单**，否则弹窗只会显示
 * "未关联 AI 会话"。演示库里用下面这句造（session 2 有真实的候选疾病与引用）：
 *
 *   INSERT INTO t_doctor_consult (user_id, doctor_id, session_id, chief_complaint, status)
 *   SELECT user_id, NULL, 2, '反复头痛伴血压升高：AI 问诊后想请医生确认用药', 0
 *   FROM t_consult_session WHERE id = 2;
 */

import '../src/styles/index.css'

import { createApiClient } from '../src/api/client.js'
import { bootstrap } from '../src/bootstrap.js'
import { useAuthStore } from '../src/stores/auth.js'

const ACCOUNTS = { admin: 'admin1', doctor: 'doctor1', user: 'patient1' }
const PASSWORD = '123456'

const params = new URLSearchParams(location.search)
const role = params.get('role') ?? 'user'
const path = params.get('path') ?? '/'
const action = params.get('action')
const row = Number(params.get('row') ?? 1)

const wait = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds))

async function waitForCount(selector, count, timeout = 4000) {
  const deadline = Date.now() + timeout
  while (Date.now() < deadline) {
    const found = document.querySelectorAll(selector)
    if (found.length >= count) return found
    await wait(100)
  }
  return document.querySelectorAll(selector)
}

async function runAction(name) {
  if (name === 'open-session') {
    // 点击处理器在内层 button 上（`<li data-session-item><button …>`）。
    const items = await waitForCount('[data-session-item] button', 1)
    items[0]?.click()
    await wait(1500)
    return
  }
  if (name === 'ai-context') {
    const buttons = await waitForCount('[data-ai-context]', row)
    buttons[row - 1]?.click()
    await wait(1500)
  }
}

const { app, pinia, router } = await bootstrap()
const auth = useAuthStore(pinia)
const session = {
  get: () => ({ token: auth.token, role: auth.role, user: auth.user }),
  set: ({ token, role: nextRole, user }) =>
    auth.setSession({ token, role: nextRole, user }),
  clear: () => auth.clear(),
}
const client = createApiClient({ session })

if (role !== 'none') {
  // 走 F-1 出口登录（不裸用 fetch），登录成功后 resume 会把会话写进 pinia store。
  await client.login({ username: ACCOUNTS[role], password: PASSWORD, role })
}

await router.push(path)
app.mount('#app')
await wait(700)
if (action) await runAction(action)
await wait(300)

// 给 Edge 的 --virtual-time-budget 一个明确的"可以拍了"信号。
document.body.dataset.previewReady = 'true'
