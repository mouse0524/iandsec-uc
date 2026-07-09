# iandsec-uc

安得和众用户服务中心 / Iandsec User Service Center.

`iandsec-uc` is a FastAPI + Vue 3 service center system with RBAC, ticket workflows, registration review, WebDAV sharing, system settings, and Skill-Know knowledge base capabilities.

## Tech Stack

- Backend: Python 3.11, FastAPI, Tortoise ORM, Aerich, Uvicorn
- Frontend: Vue 3, Vite, Naive UI, Pinia, pnpm
- Database: MySQL 8
- Cache: Redis 7
- Knowledge Base: Markdown, MarkItDown, ChromaDB, OpenAI-compatible LLM API
- Deployment: Docker, docker-compose

## Development With Docker

The development container mounts the source code into the container. Frontend runs with `pnpm run dev`, backend runs with `python run.py`, and code changes are reflected quickly.

```sh
docker-compose -f docker-compose.dev.yml up -d --build
```

View logs:

```sh
docker-compose -f docker-compose.dev.yml logs -f app
```

Enter the app container:

```sh
docker-compose -f docker-compose.dev.yml exec app sh
```

Stop development services:

```sh
docker-compose -f docker-compose.dev.yml down
```

## Production

```sh
docker build -f Dockerfile.base --target web-base -t iandsec-uc-web-base:latest .
docker build -f Dockerfile.base --target app-base -t iandsec-uc-app-base:latest .
docker-compose -f docker-compose.yml up -d --build
```

## Common Commands

```sh
python -m pytest
cd web && pnpm run build
```
