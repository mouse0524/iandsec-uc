from __future__ import annotations

from app.services.skill_know.retriever import skill_know_retriever


class SkillKnowSearchService:
    async def unified(self, query: str, *, limit: int = 20) -> dict:
        items = await skill_know_retriever.retrieve_document_chunks(query, limit=limit)
        return {"query": query, "items": items, "total": len(items)}


skill_know_search_service = SkillKnowSearchService()
