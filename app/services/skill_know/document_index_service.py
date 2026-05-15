from __future__ import annotations

from app.models.admin import SkillKnowDocument, SkillKnowDocumentChunk
from app.services.skill_know.markdown_chunker import skill_know_markdown_chunker
from app.services.skill_know.reader_agent.section_indexer import skill_know_section_indexer
from app.services.skill_know.utils import new_uuid, preview_text, sha256_text


class SkillKnowDocumentIndexService:
    async def rebuild(self, document: SkillKnowDocument) -> dict:
        await self.delete(document)
        section_result = await skill_know_section_indexer.rebuild(document)
        chunk_size = 1400
        chunk_overlap = 150
        chunks = skill_know_markdown_chunker.chunk(
            document.content or "",
            target_chars=chunk_size,
            max_chars=max(chunk_size + chunk_overlap * 2, chunk_size),
            overlap_chars=chunk_overlap,
        )
        indexed_count = 0
        chunk_rows: list[dict] = []
        for chunk in chunks:
            chunk_uri = f"{document.uri}#chunk-{chunk.index}"
            safe_heading = (chunk.heading or "")[:300] or None
            safe_title = (document.title or "")[:200]
            safe_filename = (document.filename or "")[:255]
            metadata = {
                "source_type": "document",
                "document_id": document.id,
                "document_uri": document.uri,
                "title": safe_title,
                "filename": safe_filename,
                "chunk_index": chunk.index,
                "heading": safe_heading,
                "file_type": document.file_type,
            }
            chunk_rows.append(
                {
                    "uuid": new_uuid(),
                    "document_id": document.id,
                    "uri": chunk_uri,
                    "chunk_index": chunk.index,
                    "heading": safe_heading,
                    "content": chunk.content,
                    "content_hash": sha256_text(chunk.content),
                    "token_count": chunk.token_count,
                    "extra_metadata": {**metadata, "index_mode": "document_reader_agent"},
                }
            )
            indexed_count += 1
        await SkillKnowDocumentChunk.bulk_create(
            [SkillKnowDocumentChunk(**row) for row in chunk_rows],
            batch_size=200,
        )
        return {
            "chunk_count": indexed_count,
            "section_count": int(section_result.get("section_count") or 0),
            "line_count": int(section_result.get("line_count") or 0),
            "index_status": "completed",
            "index_mode": "document_reader_agent",
            "chunk_preview": preview_text(chunks[0].content if chunks else "", 120),
        }

    async def delete(self, document: SkillKnowDocument) -> None:
        await SkillKnowDocumentChunk.filter(document_id=document.id).delete()
        await skill_know_section_indexer.delete(document.id)


skill_know_document_index_service = SkillKnowDocumentIndexService()
