from __future__ import annotations

from typing import Any

from app.models.admin import SkillKnowDocument, SkillKnowDocumentSection
from app.services.skill_know.config_service import skill_know_config_service
from app.services.skill_know.reader_agent.domain_terms import skill_know_domain_terms
from app.services.skill_know.reader_agent.whoosh_search import skill_know_whoosh_search


class SkillKnowIndexHealthService:
    async def detail(self) -> dict[str, Any]:
        whoosh_stats = await skill_know_whoosh_search.stats()
        document_count = await SkillKnowDocument.all().count()
        section_count = await SkillKnowDocumentSection.all().count()
        index_doc_count = int(whoosh_stats.get("doc_count") or 0)
        reader_status = "ok" if whoosh_stats.get("available") and whoosh_stats.get("exists") and index_doc_count > 0 else "needs_reindex"
        return {
            "status": "healthy" if reader_status == "ok" else "degraded",
            "components": {
                "database": "ok",
                "chat_model": "configured" if await skill_know_config_service.is_configured() else "missing_api_key",
                "reader_index": reader_status,
            },
            "reader_index": {
                "backend": "whoosh",
                "document_count": document_count,
                "section_count": section_count,
                "domain_terms_version": skill_know_domain_terms.version,
                **whoosh_stats,
            },
        }


skill_know_index_health_service = SkillKnowIndexHealthService()
