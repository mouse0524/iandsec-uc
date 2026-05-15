from __future__ import annotations

from app.services.skill_know.reader_agent.domain_terms import skill_know_domain_terms
from app.services.skill_know.reader_agent.reader_tools import skill_know_reader_tools


class SkillKnowRetrievalDebugService:
    async def debug(self, query: str, *, top_k: int = 8) -> dict:
        result = await skill_know_reader_tools.debug_search(query, limit=top_k)
        result["domain_terms_version"] = skill_know_domain_terms.version
        return result


skill_know_retrieval_debug_service = SkillKnowRetrievalDebugService()
