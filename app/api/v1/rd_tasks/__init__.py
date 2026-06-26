from fastapi import APIRouter

from .rd_tasks import router

rd_tasks_router = APIRouter()
rd_tasks_router.include_router(router, tags=["产研任务"])

__all__ = ["rd_tasks_router"]
