from fastapi import APIRouter

from .monitor import router

monitor_router = APIRouter()
monitor_router.include_router(router, tags=["系统监控模块"])

__all__ = ["monitor_router"]
