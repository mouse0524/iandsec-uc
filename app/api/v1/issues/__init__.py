from fastapi import APIRouter

from .issues import router

issues_router = APIRouter()
issues_router.include_router(router, tags=["Issue"])

__all__ = ["issues_router"]
