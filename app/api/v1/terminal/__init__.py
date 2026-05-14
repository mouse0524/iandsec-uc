from fastapi import APIRouter

from .terminal import public_router, router

terminal_router = APIRouter()
terminal_public_router = APIRouter()

terminal_router.include_router(router, tags=["终端管理模块"])
terminal_public_router.include_router(public_router, tags=["终端公开接口"])

__all__ = ["terminal_router", "terminal_public_router"]
