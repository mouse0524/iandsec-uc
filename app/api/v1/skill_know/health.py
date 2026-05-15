from fastapi import APIRouter

from app.schemas.base import Success
from app.services.skill_know.config_service import skill_know_config_service
from app.services.skill_know.index_health_service import skill_know_index_health_service

router = APIRouter()


@router.get("", summary="Skill-Know健康检查")
async def health_check():
    return Success(data={"status": "healthy", "configured": await skill_know_config_service.is_configured()})


@router.get("/detail", summary="Skill-Know详细健康检查")
async def health_detail():
    return Success(data=await skill_know_index_health_service.detail())
