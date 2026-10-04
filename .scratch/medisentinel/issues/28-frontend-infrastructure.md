# 28: 前端基础设施——vue-router + pinia + element-plus

**What to build:** 014–022 期间前端是 framework-free（无 router/pinia/UI 库），
用纯函数路由 `session/routes.js` + F-3 守卫 + 手写 HTML。本票引入标准生态，
但**只做基础设施**，不改视图内部结构（那是 029/030）。

**Blocked by:** 27

**Status:** ready-for-agent

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

- [ ] 三个库装上，`package.json` 用 `^` 大版本
- [ ] 按需引入配置生效（element-plus 组件无需手动 import；构建产物不应包含完整 element-plus）
- [ ] 路由表覆盖现有全部视图，角色守卫语义与 F-3 一致
- [ ] 401 清鉴权跳登录、403 仅提示不跳转——有测试
- [ ] pinia auth store 承载用户/角色/令牌
- [ ] ConsoleShell / PortalShell 用 element-plus 外壳
- [ ] App.vue 不再有 `v-else-if` 派发链
- [ ] `api/client.js` 仍是唯一出口（架构测试通过）
- [ ] 全部前端测试绿
- [ ] `npm run build` 成功
- [ ] ticket Comments 记录：三个库的实际版本、`.gitignore` 新增项、测试改动统计、`session/routes.js` 的处置

**边界：**

- 不改后端（`server/`）
- 不重写视图内部结构（029/030 再做美化）
- 不删 `session/routes.js`（除非有强理由，写进报告）
- 不破坏 F-1 架构测试（`api/client.js` 唯一出口）
- 不改 001–027 的行为

## Comments

