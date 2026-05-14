from __future__ import annotations

from typing import Any

from app.services.skill_know.chroma_store import skill_know_chroma_store
from app.services.skill_know.config_service import skill_know_config_service


class SkillKnowIndexHealthService:
    async def detail(self) -> dict[str, Any]:
        chroma = await skill_know_chroma_store.diagnose()
        return {
            "status": "healthy",
            "components": {
                "database": "ok",
                "chroma": "ok" if chroma.get("chromadb_available") else "missing",
                "openai": "configured" if await skill_know_config_service.is_configured() else "missing_api_key",
            },
            "chroma": chroma,
        }

    async def diagnose(self, *, test_embedding: bool = False) -> dict[str, Any]:
        return await skill_know_chroma_store.diagnose(test_embedding=test_embedding)


skill_know_index_health_service = SkillKnowIndexHealthService()
