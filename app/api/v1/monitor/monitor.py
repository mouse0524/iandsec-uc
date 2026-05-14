from fastapi import APIRouter, Query

from app.schemas.base import Success
from app.services.system_monitor_service import system_monitor_service

router = APIRouter()


@router.get("/overview", summary="系统监控总览")
async def monitor_overview():
    return Success(data=await system_monitor_service.overview())


@router.get("/resources", summary="系统资源")
async def monitor_resources():
    return Success(data=await system_monitor_service.system_resources())


@router.get("/mysql", summary="MySQL状态")
async def monitor_mysql():
    return Success(data=await system_monitor_service.mysql_status())


@router.get("/redis", summary="Redis缓存状态")
async def monitor_redis():
    return Success(data=await system_monitor_service.redis_status())


@router.post("/redis/clear", summary="清空当前Redis DB")
async def clear_redis(confirm: bool = Query(False)):
    return Success(data=await system_monitor_service.clear_redis(confirm=confirm), msg="Redis缓存已清空")


@router.get("/chroma", summary="Chroma向量库状态")
async def monitor_chroma():
    return Success(data=await system_monitor_service.chroma_status())
