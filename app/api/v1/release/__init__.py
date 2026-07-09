from fastapi import APIRouter

from .release import router

release_router = APIRouter()
release_router.include_router(router, tags=["版本发布模块"])

__all__ = ["release_router"]
