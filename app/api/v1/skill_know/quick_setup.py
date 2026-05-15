from fastapi import APIRouter

from app.schemas.base import Success
from app.schemas.skill_know import SkillKnowQuickSetupIn, SkillKnowTestConnectionIn
from app.services.skill_know.quick_setup_service import skill_know_quick_setup_service

router = APIRouter()


@router.get("/state", summary="快速设置状态")
async def get_state():
    return Success(data=await skill_know_quick_setup_service.state())


@router.get("/checklist", summary="配置检查清单")
async def get_checklist():
    return Success(data={"items": await skill_know_quick_setup_service.checklist()})


@router.post("/essential", summary="保存核心配置")
async def complete_setup(payload: SkillKnowQuickSetupIn):
    return Success(data=await skill_know_quick_setup_service.complete(payload))


@router.post("/test-connection", summary="测试OpenAI连接")
async def test_connection(payload: SkillKnowTestConnectionIn):
    return Success(data=await skill_know_quick_setup_service.test_connection(payload))


@router.post("/reset", summary="重置快速设置")
async def reset_setup():
    return Success(data=await skill_know_quick_setup_service.reset())


@router.get("/providers", summary="模型提供商")
async def providers():
    return Success(data={"providers": [
        {"id": "openai", "name": "OpenAI Compatible", "base_url": "https://api.openai.com/v1"},
        {"id": "ollama", "name": "Ollama 模型", "base_url": "http://127.0.0.1:11434"},
    ]})


@router.get("/providers/{provider_id}/models", summary="提供商模型列表")
async def provider_models(provider_id: str):
    if provider_id == "ollama":
        return Success(data={
            "provider_id": provider_id,
            "base_url": "http://127.0.0.1:11434",
            "models": [
                {"id": "llama3.1", "name": "llama3.1", "type": "chat"},
                {"id": "qwen2.5", "name": "qwen2.5", "type": "chat"},
                {"id": "deepseek-r1", "name": "deepseek-r1", "type": "chat"},
            ],
        })
    return Success(data={
        "provider_id": provider_id,
        "base_url": "https://api.openai.com/v1",
        "models": [
            {"id": "gpt-4o-mini", "name": "gpt-4o-mini", "tool_calling": True},
            {"id": "gpt-4o", "name": "gpt-4o", "tool_calling": True},
        ],
    })
