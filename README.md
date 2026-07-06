# iandsec-uc

安得和众用户服务中心。


## 技术栈

- 后端：Python 3.11、FastAPI、Tortoise ORM、Aerich、Uvicorn
- 前端：Vue 3、Vite、Naive UI、Pinia、pnpm
- 数据库：MySQL 8
- 缓存：Redis 7
- 部署：Docker、docker-compose

## 核心功能

### 系统管理

- 用户管理：新增、编辑、删除、重置密码、角色分配。
- 角色管理：菜单授权、接口授权、按钮级权限控制。
- 菜单管理：后端动态菜单、前端动态路由。
- API 管理：接口列表维护与刷新。
- 部门管理：部门树与层级维护。
- 审计日志：记录请求、响应摘要、耗时和用户信息。
- 系统设置：站点、工单、SMTP 邮件模板、WebDAV、LLM 等配置。

### 工单中心

- 登录用户提交工单。
- 游客免登录提交工单。
- 验证码校验。
- 附件上传与受控下载。
- 我的工单列表、筛选和详情。
- 客服审核通过/驳回。
- 技术处理完成/驳回。
- 工单流转时间线、问题根因、审核人、处理人、完成时间展示。

### 代理商与注册审核

- 支持渠道商/用户注册申请。
- 支持客服或管理员审核通过/驳回。
- 支持验证码邮件和审核通知邮件模板化发送。

### WebDAV 外发管理

- WebDAV 目录和文件只读浏览。
- 支持目录层级跳转和面包屑导航。
- 支持文件分享链接创建、复用、复制和删除。
- 管理员可查看所有分享记录，普通用户仅查看自己的分享。
- WebDAV 列表结果缓存到 Redis，上传/创建目录/删除后自动失效。


- 支持上传 PDF、PowerPoint、Word、Excel、HTML、CSV、JSON、XML、TXT、MD。
- 不支持旧版 Office 格式：`.doc`、`.ppt`、`.xls`。

## 目录结构

```text
.
├── app/                    # FastAPI 后端
│   ├── api/                # API 路由
│   ├── controllers/        # 控制器
│   ├── models/             # Tortoise ORM 模型
│   ├── schemas/            # Pydantic Schema
│   ├── services/           # 业务服务
│   └── settings/           # 配置
├── web/                    # Vue 3 前端
├── migrations/             # Aerich 数据库迁移
├── deploy/                 # 部署脚本和 Nginx 配置
├── tests/                  # 测试
├── Dockerfile              # 生产镜像
├── Dockerfile.dev          # 开发镜像
├── docker-compose.yml      # 生产编排
├── docker-compose.dev.yml  # 开发编排
└── run.py                  # 后端启动入口
```

## 开发环境：Docker 热更新模式

推荐使用开发容器运行。开发镜像内置 Python、Node.js、pnpm 和项目依赖，源码通过 bind mount 挂载到容器中。

容器内运行方式：

- 前端：`pnpm run dev`
- 后端：`python run.py`
- 前端访问：`http://localhost:3100`
- 后端访问：`http://localhost:9999`

宿主机代码修改后：

- 前端 Vite 热更新。
- 后端通过 `UVICORN_RELOAD=1` 自动重载。
- `web/node_modules` 和 pnpm store 使用 Docker volume，避免污染宿主机并加快依赖安装。

### 启动开发环境

```sh
docker-compose -f docker-compose.dev.yml up -d --build
```

首次构建后，日常启动可使用：

```sh
docker-compose -f docker-compose.dev.yml up -d
```

### 查看日志

```sh
docker-compose -f docker-compose.dev.yml logs -f app
```

### 进入 app 容器

```sh
docker-compose -f docker-compose.dev.yml exec app sh
```

### 停止开发环境

```sh
docker-compose -f docker-compose.dev.yml down
```

### 清理开发环境数据

会删除 MySQL、Redis、storage、logs、node_modules、pnpm store 等 Docker volume。

```sh
docker-compose -f docker-compose.dev.yml down -v
```

## 本地开发

### 后端

1. 创建虚拟环境。

```sh
python -m venv .venv
```

2. 激活虚拟环境。

Windows：

```sh
.venv\Scripts\activate
```

Linux / macOS：

```sh
source .venv/bin/activate
```

3. 安装依赖。

```sh
pip install -r requirements.txt
```

4. 启动后端。

```sh
python run.py
```

### 前端

```sh
cd web
pnpm install
pnpm run dev
```

## 数据库迁移

项目使用 Aerich 管理数据库迁移。

```sh
aerich upgrade
```

如果新增模型或字段，生成迁移：

```sh
aerich migrate --name your_migration_name
```

注意：当前 `.gitignore` 忽略了 `migrations/` 目录。如果新增迁移文件需要提交，请使用 `git add -f migrations/models/<file>.py`，或调整 `.gitignore`。

## 生产部署

### 使用 docker-compose

```sh
docker-compose -f docker-compose.yml up -d --build
```

查看日志：

```sh
docker-compose -f docker-compose.yml logs -f
```

停止服务：

```sh
docker-compose -f docker-compose.yml down
```

### 使用 Dockerfile 构建镜像

```sh
docker build -t iandsec-uc .
docker run -d --restart=always --name iandsec-uc -p 9999:80 iandsec-uc
```

## 常用命令

### 后端测试

```sh
python -m pytest
```

### Python 编译检查

```sh
python -m compileall app
```

### 前端构建

```sh
cd web
pnpm run build
```

### 前端 lint

```sh
cd web
pnpm run lint
```

## 默认访问

开发环境：

- 前端：`http://localhost:3100`
- 后端：`http://localhost:9999`
- MySQL：`localhost:33060`
- Redis：`localhost:6379`

首次部署必须通过 `INITIAL_ADMIN_PASSWORD` 设置高强度初始管理员密码；首次登录后请立即修改并妥善保存。

## 说明

- 开发环境推荐使用 `docker-compose.dev.yml`，它会把当前代码目录挂载到容器中，适合快速调试。
- 如果修改了 Python 或 Node 依赖文件，建议重新构建开发镜像：`docker-compose -f docker-compose.dev.yml up -d --build`。
- 如果只是修改业务代码，不需要重建镜像。
