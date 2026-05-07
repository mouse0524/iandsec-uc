from __future__ import annotations

from app.models.admin import SkillKnowDocument, SkillKnowDocumentChunk
from app.services.skill_know.chroma_store import skill_know_chroma_store
from app.services.skill_know.config_service import skill_know_config_service
from app.services.skill_know.markdown_chunker import skill_know_markdown_chunker
from app.services.skill_know.utils import new_uuid, sha256_text


class SkillKnowDocumentIndexService:
    async def rebuild(self, document: SkillKnowDocument) -> dict:
        await self.delete(document)
        chunk_size = int(await skill_know_config_service.get("chunk_size", 1400) or 1400)
        chunk_overlap = int(await skill_know_config_service.get("chunk_overlap", 150) or 150)
        chunks = skill_know_markdown_chunker.chunk(
            document.content or "",
            target_chars=chunk_size,
            max_chars=max(chunk_size + chunk_overlap * 2, chunk_size),
            overlap_chars=chunk_overlap,
        )
        indexed_count = 0
        for chunk in chunks:
            chunk_uri = f"{document.uri}#chunk-{chunk.index}"
            metadata = {
                "source_type": "document",
                "document_id": document.id,
                "document_uri": document.uri,
                "title": document.title,
                "filename": document.filename,
                "chunk_index": chunk.index,
                "heading": chunk.heading,
                "file_type": document.file_type,
            }
            vector_id = await skill_know_chroma_store.upsert_document_chunk(chunk_uri=chunk_uri, text=chunk.content, metadata=metadata)
            await SkillKnowDocumentChunk.create(
                uuid=new_uuid(),
                document_id=document.id,
                uri=chunk_uri,
                chunk_index=chunk.index,
                heading=chunk.heading,
                content=chunk.content,
                content_hash=sha256_text(chunk.content),
                token_count=chunk.token_count,
                vector_id=vector_id or chunk_uri,
                extra_metadata=metadata,
            )
            indexed_count += 1
        return {"chunk_count": indexed_count, "index_status": "completed"}

    async def delete(self, document: SkillKnowDocument) -> None:
        rows = await SkillKnowDocumentChunk.filter(document_id=document.id)
        await skill_know_chroma_store.delete_document_chunks([row.uri for row in rows])
        await SkillKnowDocumentChunk.filter(document_id=document.id).delete()


skill_know_document_index_service = SkillKnowDocumentIndexService()
