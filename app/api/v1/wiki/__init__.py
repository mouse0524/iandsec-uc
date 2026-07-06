from fastapi import APIRouter

from .wiki import router

wiki_router = APIRouter(tags=["Wiki"])
wiki_router.include_router(router)

__all__ = ["wiki_router"]

