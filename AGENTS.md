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

## 企业知识库高风险点
- 知识来源页面：`web/src/views/wiki/sources/index.vue`；知识库接口：`app/api/v1/wiki/wiki.py`；核心服务：`app/services/wiki/`。
- LLM 调用封装保留在 `app/services/llm/openai_client.py`，系统设置页维护 LLM 配置。
- 当前知识库方向是文件优先的 `llm-wiki`：原始资料在 `raw/`，LLM 维护 Markdown 在 `wiki/`，不要回退到旧 `skill-know` 路径。
