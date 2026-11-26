# 模训平台前端工程（Vue 3 + TypeScript + Vite）

本目录是平台前端的工程化入口，采用 **Vue 3 + TypeScript + Vite**，与既有 `frontend/styles/` 和 `frontend/live/` 保持视觉与交互完全一致。

## 本地开发

确保后端在 `http://127.0.0.1:8000` 运行，然后启动 Vite 开发服务器（已配置 `/api`、`/healthz`、`/readyz` 反向代理）：

```bash
cd frontend/web
npm install
npm run dev
```

访问 `http://127.0.0.1:5173/`，修改 `.vue` / `.ts` / `.css` 即时热更新。

## 生产构建

```bash
cd frontend/web
npm run build
```

构建产物输出到 `frontend/web/dist/`（不提交到 Git）。后端 `backend/src/model_platform/web.py` 在检测到 `frontend/web/dist/index.html` 时会自动提供编译后的 Vue 应用与 `/assets/*` 静态资源；若未构建则自动回退到 `frontend/live/index.html`。

Docker 多阶段构建（`deploy/server/Dockerfile`）已内置 `node:22-alpine` 构建阶段，服务器镜像打包时会自动编译本目录。

## 目录结构与渐进式 SFC 迁移约定

- `src/main.ts`：按原始顺序加载 `frontend/styles/*` 与 `frontend/live/*.css`，保持全部 CSS Token 与布局不变。
- `src/api/client.ts`：强类型 HTTP 客户端（同源 Cookie + 内存 CSRF + `If-Match` 乐观锁）。
- `src/stores/app.ts`：Vue 3 `reactive` 全局状态、路由解析、5 秒静默轮询与数据拉取。
- `src/components/AppShell.vue`：顶栏 + 可折叠侧栏 + 面包屑外壳（Vue SFC）。
- `src/components/AuthView.vue` / `ModalHost.vue` / `ToastHost.vue`：登录/注册/初始化页、弹窗宿主、全局提示。
- `src/views/WorkspaceContent.vue`：页面分发层。当前复用了 `frontend/live/` 下全部已验证的 20+ 页面渲染器与 149 项单测；团队各成员可以按模块逐页替换为独立 `.vue` 单文件组件，互不阻塞。
