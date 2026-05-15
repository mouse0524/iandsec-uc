from fastapi import APIRouter

from .chat import router as chat_router
from .documents import router as documents_router
from .eval import router as eval_router
from .folders import router as folders_router
from .health import router as health_router
from .quick_setup import router as quick_setup_router

skill_know_router = APIRouter()
skill_know_router.include_router(folders_router, prefix="/folders", tags=["Skill-Know 文件夹"])
skill_know_router.include_router(documents_router, prefix="/documents", tags=["Skill-Know 文档"])
skill_know_router.include_router(chat_router, prefix="/chat", tags=["Skill-Know 对话"])
skill_know_router.include_router(eval_router, prefix="/eval", tags=["Skill-Know 评测"])
skill_know_router.include_router(quick_setup_router, prefix="/llm-settings", tags=["Skill-Know LLM设置"])
skill_know_router.include_router(health_router, prefix="/health", tags=["Skill-Know 健康检查"])

__all__ = ["skill_know_router"]
