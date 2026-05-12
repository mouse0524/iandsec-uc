from __future__ import annotations

from fastapi import HTTPException

from app.services.skill_know.retriever import skill_know_retriever
from app.settings import settings


class SkillKnowSearchService:
    async def unified(self, query: str, *, limit: int = 20) -> dict:
        items = await skill_know_retriever.retrieve_document_chunks(query, limit=limit)
        return {"query": query, "items": items, "total": len(items)}

    async def sql(self, query: str) -> list[dict]:
        if not settings.SKILL_KNOW_SQL_SEARCH_ENABLED:
            raise HTTPException(status_code=403, detail="SQL search is disabled")
        raise HTTPException(status_code=403, detail="SQL search is not available")


skill_know_search_service = SkillKnowSearchService()
