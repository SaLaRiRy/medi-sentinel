# 28: 前端基础设施——vue-router + pinia + element-plus

**What to build:** 014–022 期间前端是 framework-free（无 router/pinia/UI 库），
用纯函数路由 `session/routes.js` + F-3 守卫 + 手写 HTML。本票引入标准生态，
但**只做基础设施**，不改视图内部结构（那是 029/030）。

**Blocked by:** 27

**Status:** done
Completed: 2b055f160a6bcc1727a65db6a397bd7caf2d6608

**背景：** 014–022 期间前端是 framework-free（无 router/pinia/UI 库），
用纯函数路由 `session/routes.js` + F-3 守卫 + 手写 HTML。本票引入标准生态，
但**只做基础设施**，不改视图内部结构（那是 029/030）。

**范围：**

1. 安装依赖（`client/`）
   - `npm install vue-router@^4.6.4 pinia@^3.0.4 element-plus@^2.14.6`
   - `npm install -D unplugin-vue-components@32.1.0 unplugin-auto-import@21.1.0`
   - 在 `package.json` 显式写大版本区间（`^`），不要用 latest/next
   - lockfile 钉实际版本
2. 配置按需引入（`client/vite.config.js`）
   - `AutoImport({ imports: ['vue', 'vue-router', 'pinia'], resolvers: [ElementPlusResolver()] })`
   - `Components({ resolvers: [ElementPlusResolver()] })`
   - 不要全局 `import 'element-plus/dist/index.css'`
   - 生成的 `auto-imports.d.ts` / `components.d.ts` 加进 `.gitignore`
     （避免每次构建脏工作区）
3. 创建 vue-router（`client/src/router/`）
   - `routes.js`：路由表，覆盖现有全部视图（患者/医生/管理员三端）
   - `index.js`：`createRouter` + `createWebHistory`
   - 守卫：`beforeEach` 接 F-3 既有逻辑
     - 未登录 → 跳 `/login`
     - 角色不符 → 跳该角色首页（或 `/403` 提示页）
     - 401 响应 → 清鉴权 + 跳 `/login`
     - 403 响应 → 仅提示，不跳转
   - **保留 `session/routes.js` 不删**——029/030 迁移视图时逐步淘汰，
     现在作为「菜单/导航计算」的辅助仍在用（或明确报告要怎么处理）
4. 创建 pinia（`client/src/stores/`）
   - `auth.js`：`user` / `role` / `token` / `isAuthenticated`
   - 把 `App.vue` 现在的会话状态（`ref`）搬进 store
   - `App.vue` 变成「应用 outcome」：只挂 `router-view` + 全局错误分派
5. 布局外壳接 element-plus（`client/src/layouts/`）
   - `ConsoleShell.vue` / `PortalShell.vue` 改用 `el-container` / `el-header` /
     `el-aside` / `el-menu` / `el-dropdown`
   - 菜单项沿用现有 `navigation.js` 的数据源（不改菜单结构）
   - `UserMenu.vue` 用 `el-dropdown` 重做（它已经被抽出来了）
   - **不改视图内部**——视图还是原来的 HTML，只是外壳换了
6. App.vue 收敛
   - 移除 `v-else-if` 派发链（改用 `router-view`）
   - 401/403 逻辑接 pinia + router
   - 保留 `api/client.js` 作为唯一出口（架构测试要求，不要破坏）
7. 测试适配
   - 276 个前端测试现在无框架直挂组件
   - 引入 router/pinia 后，涉及挂载的测试需要注入 `createRouter` / `createPinia`
   - 建一个共享 helper（如 `client/tests/helpers/mount.js`）统一注入
   - 逐个测试适配，**不得降低断言强度**（不许为绿而删断言）
   - 报告：改了多少测试、哪些是「不得不改」，哪些是「顺手改」

**验收清单：**

- [x] 三个库装上，`package.json` 用 `^` 大版本
- [x] 按需引入配置生效（element-plus 组件无需手动 import；构建产物不应包含完整 element-plus）
- [x] 路由表覆盖现有全部视图，角色守卫语义与 F-3 一致
- [x] 401 清鉴权跳登录、403 仅提示不跳转——有测试
- [x] pinia auth store 承载用户/角色/令牌
- [x] ConsoleShell / PortalShell 用 element-plus 外壳
- [x] App.vue 不再有 `v-else-if` 派发链
- [x] `api/client.js` 仍是唯一出口（架构测试通过）
- [x] 全部前端测试绿
- [x] `npm run build` 成功
- [x] ticket Comments 记录：三个库的实际版本、`.gitignore` 新增项、测试改动统计、`session/routes.js` 的处置

**边界：**

- 不改后端（`server/`）
- 不重写视图内部结构（029/030 再做美化）
- 不删 `session/routes.js`（除非有强理由，写进报告）
- 不破坏 F-1 架构测试（`api/client.js` 唯一出口）
- 不改 001–027 的行为

## Comments

### 交付物

| 文件 | 说明 |
|---|---|
| `client/vite.config.js` | `AutoImport`（vue / vue-router / pinia + `ElementPlusResolver`）与 `Components`（`ElementPlusResolver`）；未全局引入 `element-plus/dist/index.css`；测试需 `test.server.deps.inline: ['element-plus']`（Node 不能直接加载 EP 的 CSS） |
| `client/src/router/routes.js` | 由 `session/routes.js` 的 `ROUTE_TABLE` 生成 vue-router 记录（component / name / layout / meta），角色与 requiresAuth 语义不复制 |
| `client/src/router/index.js` | `createRouter` + `createWebHistory`，`beforeEach` 复用 `session/guard.js` 的 `resolveAccess`（唯一鉴权枢轴） |
| `client/src/stores/auth.js` | pinia auth store：`user` / `role` / `token` / `isAuthenticated` + `setSession` / `clear` |
| `client/src/session/dispatch.js` | 401/403 分流适配器：策略仍来自 `guard.js` 的 `applyApiError`，此处只补导航 |
| `client/src/App.vue` | 变成 outcome 层：按 `route.meta.layout` 选外壳 + `router-view`，不再有 `v-else-if` 派发链；F-1（`api/client.js`）仍是唯一出口 |
| `client/src/layouts/ConsoleShell.vue` / `PortalShell.vue` | 改用 `el-container` / `el-aside` / `el-header` / `el-menu`，菜单数据仍来自 `session/navigation.js` |
| `client/src/components/UserMenu.vue` | 用 `el-dropdown` 重做，对外仍是 `navigate` / `logout` 事件 |
| `client/src/layouts/PublicShell.vue`、`client/src/views/ProfileView.vue` | 新增的最小胶水：未登录外壳（保留 TICKET-001 健康页脚）与 profile 路由包装（沿用 `ProfilePanel`，不改其内部） |
| `client/tests/helpers/mount.js` | 共享挂载 helper：`createTestPinia` / `createTestRouter` / `mountWithPlugins` / `settle` |
| `client/tests/setup.js` | jsdom 下的 `ResizeObserver` / `matchMedia` 兜底（el-dropdown / el-tooltip 需要） |

### 实际版本

| 包 | package.json | lockfile 实际 |
|---|---|---|
| vue | `^3.5.43` | 3.5.43（未变） |
| vue-router | `^4.6.4` | 4.6.4 |
| pinia | `^3.0.4` | 3.0.4 |
| element-plus | `^2.14.6` | **2.14.6**（`^` 默认会装 2.14.7，已显式降到 2.14.6） |
| unplugin-vue-components | `^32.1.0` | 32.1.0 |
| unplugin-auto-import | `^21.1.0` | 21.1.0 |

### `.gitignore` 新增

```
client/auto-imports.d.ts
client/components.d.ts
```

### 测试改动统计

- 基线：48 文件 / 276 测试全绿；完成后：**52 文件 / 294 测试全绿**（+4 文件 / +18 测试，无删减）。
- 新增：`auth-store.test.js`(3)、`router-guard.test.js`(9)、`error-dispatch.test.js`(2)、`app-shell.test.js`(4)。
- 「不得不改」：`shells.test.js`——`el-dropdown` 的浮层经 0ms 定时器打开，点击后需 `settle()`；同时 `mount` → `mountWithPlugins`。断言强度不变（仍是 10/4 菜单项、个人中心点击前不在 DOM、logout 事件）。
- 「顺手改」：无（其余 47 个测试文件零改动）。
- 关键发现：**视图测试不需要注入 `createRouter` / `createPinia`**——视图仍是 prop/emit 驱动、不碰 router/session，符合「只做基础设施、不改视图内部」的边界。因此 ticket 第 7 条「逐个测试适配」的实际结论是：只有外壳测试需要适配，视图测试保持原样。

### 按需引入验证

- `npm run build` 成功：css 50.50 kB、js 329.69 kB（gzip 107.54 kB）。
- 产物中不存在未使用组件：`el-table` / `el-date-picker` / `el-select` / `el-tabs` / `el-tree` / `el-upload` 计数均为 0；`.el-dropdown-menu` / `.el-menu-item` 存在。未引入完整 `element-plus/dist/index.css`。

### `session/routes.js` 的处置

- **保留**，且升级为更强的角色：`router/routes.js` 直接从 `ROUTE_TABLE` + `roleForPath` 生成 vue-router 记录，path → screen → access 仍只有一份来源，守卫语义不会与菜单模型漂移。
- `resolveRoute` / `resolveNavigation` 目前只被 `routes.test.js` 覆盖，029/030 迁移视图时再逐步淘汰（文件头注释已更新说明）。

### 分支与合并策略

- 前端大改在独立分支 `frontend-rework` 上进行（基线 `1250c68`）；**尚未合并 main**，待人工验收后再合。
