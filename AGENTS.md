# AGENTS

## 项目边界
- 根目录是 FastAPI 后端，`web/` 是 Vue 3 + Vite 前端；没有 monorepo/workspace 工具链。
- 后端入口是 `run.py`，固定监听 `9999`；前端开发端口来自 `web/.env` 的 `VITE_PORT=3100`。
- API 实际前缀是 `/api/v1`，路由统一从 `app/api/v1/__init__.py` 挂载。
- 动态菜单和动态路由主要由后端 `app/core/init_app.py` 初始化；新增/改页面时同时核对前端 view、后端菜单 component、接口权限。

## 推荐启动
- 首选开发编排：`docker-compose -f docker-compose.dev.yml up -d --build`。
- 开发编排的同一个 app 容器同时跑后端 `9999` 和前端 `3100`，MySQL 暴露到 `127.0.0.1:33060`，Redis 暴露到 `127.0.0.1:6379`。
- 开发容器源码目录是 `/opt/iandsec-uc`；`web/node_modules` 和 pnpm store 是 Docker volume，宿主机不要假设依赖已安装。
- 开发入口脚本 `deploy/entrypoint-dev.sh` 会先在 `/opt/iandsec-uc/web` 执行 `CI=true pnpm install --prefer-offline`，再启动 `pnpm run dev --host 0.0.0.0 --no-open` 和 `python run.py`。

## 常用命令
- 后端安装：`pip install -r requirements.txt`。
- 后端启动：`python run.py`；只有设置 `UVICORN_RELOAD=1`/`true`/`yes`/`on` 才会热重载。
- 后端轻量验证：`python -m compileall app`。
- 后端测试：从仓库根目录运行 `python -m pytest`，不要优先用裸 `pytest tests/...`。
- 前端安装：在 `web/` 下运行 `pnpm install`。
- 前端开发：在 `web/` 下运行 `pnpm run dev`。
- 前端构建：在 `web/` 下运行 `pnpm run build`。
- 前端 lint：在 `web/` 下运行 `pnpm run lint`，自动修复用 `pnpm run lint:fix`。

## 配置坑点
- 后端配置在 `app/settings/config.py`，依赖环境变量；`SECRET_KEY` 空值会在导入配置时直接抛 `RuntimeError`。
- 首次初始化超级管理员还需要 `INITIAL_ADMIN_PASSWORD`；缺失会在 `init_superuser()` 中抛错。
- 本地裸跑后端默认连 `127.0.0.1:3306` MySQL 和 `127.0.0.1:6379` Redis；若使用开发 compose，宿主机 MySQL 端口是 `33060`，容器内 host 是 `mysql`。
- CORS 默认只放行 `http://localhost:3100` 和 `http://127.0.0.1:3100`。
- 前端请求根路径来自 `VITE_BASE_API`；开发代理由 `web/.env.development` 的 `VITE_USE_PROXY=true` 和 `VITE_BASE_API=/api/v1` 控制，不要在前端写死后端 host。
- 生产 compose 强制要求 `MYSQL_USER`、`MYSQL_PASSWORD`、`REDIS_PASSWORD`、`SECRET_KEY`、`INITIAL_ADMIN_PASSWORD`、`MYSQL_ROOT_PASSWORD` 等变量；`.env.example` 是最小参考。

## 数据库与初始化
- ORM 是 Tortoise，迁移工具是 Aerich；配置在 `pyproject.toml` 的 `[tool.aerich]`，迁移目录是 `./migrations`。
- 升级迁移：`aerich upgrade`；生成迁移：`aerich migrate --name <name>`。
- README 指出当前 `.gitignore` 忽略 `migrations/`，新增迁移文件如需提交通常要 `git add -f migrations/models/<file>.py`。
- `app/__init__.py` 的 lifespan 会执行 `init_data()`：建表、首个超级管理员、菜单、API 列表、角色权限、Skill-Know 默认配置都会在应用启动时发生。

## 前端约定
- 前端锁文件是 `web/pnpm-lock.yaml`，改依赖时优先保持 pnpm 生态。
- Prettier 配置在 `web/.prettierrc.json`：`printWidth: 100`、`singleQuote: true`、`semi: false`、`endOfLine: lf`。
- ESLint 配置不在独立 `.eslintrc`，而是在 `web/package.json` 的 `eslintConfig`。
- 静态基础路由在 `web/src/router/routes/index.js`；后端菜单的 `component` 字段要能匹配 `web/src/views/**/index.vue` 动态导入。

## 测试与验证
- `tests/conftest.py` 只兜底设置 `SECRET_KEY`，不会准备 MySQL、Redis 或业务数据。
- 改后端纯 Python 逻辑时，最低成本先跑 `python -m compileall app`；涉及数据库/接口行为再跑 `python -m pytest` 或启动 compose 验证。
- 改前端页面或路由后，最低成本验证通常是 `cd web && pnpm run build`；必要时再跑 `pnpm run lint`。

## Skill-Know 高风险点
- 智能对话页面：`web/src/views/skill-know/chat/index.vue`；流式接口：`app/api/v1/skill_know/chat.py`；核心服务：`app/services/skill_know/chat_service.py`。
- 对话链路有两层流式：后端 SSE 事件 `assistant.delta`/`final`，前端收到后再逐字 reveal；改流式体验时必须同时检查 `final` 是否覆盖 `rawAnswer`。
- SSE 响应已设置 `text/event-stream`、`Cache-Control: no-cache`、`X-Accel-Buffering: no`；若调试栏 `first chunk` 很晚，优先排查代理/压缩/上游模型缓冲，不要只改 Vue。
- 文档管理页：`web/src/views/skill-know/documents/index.vue`；文档接口：`app/api/v1/skill_know/documents.py`。
- 引用跳转依赖 `document_id` 和 `chunk_id` 查询参数；文档预览按 `chunks` 渲染并高亮片段，不能只改完整 Markdown 预览。
- 文档上传前端使用 2MB 分片、3 并发和 localStorage 续传 key；后端有 `/upload/init`、`/upload/chunk`、`/upload/status`、`/upload/complete` 配套接口。
