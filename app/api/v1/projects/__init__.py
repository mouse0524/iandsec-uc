from fastapi import APIRouter

from .projects import router

projects_router = APIRouter(tags=["项目管理"])
projects_router.include_router(router)
