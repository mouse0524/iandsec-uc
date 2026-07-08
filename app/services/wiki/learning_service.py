from app.models.admin import WikiLearningCandidate, WikiPage
from app.services.wiki.wiki_builder import content_hash, normalize_page_path, slugify, wiki_builder


class WikiLearningService:
    async def create_candidate(self, *, question: str, answer: str | None, evidence_page_ids: list[int], reason: str) -> WikiLearningCandidate:
        path = normalize_page_path(f"concepts/{slugify(question, 'learning')}")
        content = f"# {question.strip()}\n\n请在这里整理需要写入知识库的内容，确认无误后点击“学习入库”。"
        candidate = await WikiLearningCandidate.filter(question=question.strip(), reason=reason, status="pending").first()
        if candidate:
            candidate.answer = answer
            candidate.evidence_page_ids = evidence_page_ids
            await candidate.save()
            return candidate
        return await WikiLearningCandidate.create(
            question=question.strip(),
            answer=answer,
            evidence_page_ids=evidence_page_ids,
            reason=reason,
            proposed_page_path=path,
            proposed_content=content,
        )

    async def approve(self, *, candidate_id: int, reviewer_id: int, content: str | None = None) -> WikiLearningCandidate:
        candidate = await WikiLearningCandidate.get(id=candidate_id)
        body = (content or candidate.proposed_content or "").strip()
        path = normalize_page_path(candidate.proposed_page_path or f"concepts/{slugify(candidate.question, 'learning')}")
        page_hash = content_hash(body)
        page, _ = await WikiPage.get_or_create(
            path=path,
            defaults={
                "title": candidate.question[:200],
                "page_type": "concept",
                "content": body,
                "summary": body[:500],
                "content_hash": page_hash,
            },
        )
        if page.content_hash != page_hash:
            page.content = body
            page.summary = body[:500]
            page.content_hash = page_hash
            await page.save()
        wiki_builder._ensure_layout()
        wiki_builder._write_page(path, body)
        candidate.status = "approved"
        candidate.reviewed_by = reviewer_id
        candidate.proposed_content = body
        await candidate.save()
        return candidate

    async def reject(self, *, candidate_id: int, reviewer_id: int) -> WikiLearningCandidate:
        candidate = await WikiLearningCandidate.get(id=candidate_id)
        candidate.status = "rejected"
        candidate.reviewed_by = reviewer_id
        await candidate.save()
        return candidate


wiki_learning_service = WikiLearningService()
