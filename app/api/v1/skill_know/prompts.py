from fastapi import APIRouter, Query

from app.schemas.base import Success
from app.schemas.skill_know import SkillKnowPromptUpdate
from app.services.skill_know.prompt_service import skill_know_prompt_service

router = APIRouter()


@router.get("/list", summary="提示词列表")
async def list_prompts(category: str | None = Query(None), include_inactive: bool = Query(False)):
    rows = await skill_know_prompt_service.list(category=category, include_inactive=include_inactive)
    return Success(data={"items": rows, "total": len(rows)})


@router.get("/get", summary="提示词详情")
async def get_prompt(key: str = Query(...)):
    return Success(data=await skill_know_prompt_service.get(key))


@router.post("/update", summary="更新提示词")
async def update_prompt(key: str, payload: SkillKnowPromptUpdate):
    return Success(data=await skill_know_prompt_service.update(key, payload))


@router.post("/reset", summary="重置提示词")
async def reset_prompt(key: str):
    return Success(data=await skill_know_prompt_service.reset(key))


@router.post("/sync-defaults", summary="同步默认提示词")
async def sync_default_prompts():
    return Success(data=await skill_know_prompt_service.sync_defaults())
