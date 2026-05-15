from __future__ import annotations

from app.log import logger
from app.models.admin import SkillKnowDocument, SkillKnowDocumentChunk
from app.services.skill_know.chroma_store import skill_know_chroma_store
from app.services.skill_know.config_service import skill_know_config_service
from app.services.skill_know.markdown_chunker import skill_know_markdown_chunker
from app.services.skill_know.utils import new_uuid, preview_text, sha256_text


class SkillKnowDocumentIndexService:
    async def rebuild(self, document: SkillKnowDocument) -> dict:
        await self.delete(document)
        config = await skill_know_config_service.llm_config()
        legacy_key = config.get("llm_api_key")
        configured = (
            (str(config.get("llm_chat_provider") or "openai").lower() == "ollama" or bool(config.get("llm_chat_api_key") or legacy_key))
            and (
                str(config.get("llm_embedding_provider") or "openai").lower() == "ollama"
                or bool(config.get("llm_embedding_api_key") or legacy_key)
            )
        )
        chunk_size = int(config.get("chunk_size", 1400) or 1400)
        chunk_overlap = int(config.get("chunk_overlap", 150) or 150)
        chunks = skill_know_markdown_chunker.chunk(
            document.content or "",
            target_chars=chunk_size,
            max_chars=max(chunk_size + chunk_overlap * 2, chunk_size),
            overlap_chars=chunk_overlap,
        )
        indexed_count = 0
        vector_count = 0
        vector_items: list[dict] = []
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
            vector_items.append({"chunk_uri": chunk_uri, "text": chunk.content, "metadata": metadata})
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
                    "vector_id": chunk_uri,
                    "extra_metadata": {**metadata, "vector_indexed": False},
                }
            )
            indexed_count += 1
        vector_ids = await skill_know_chroma_store.upsert_document_chunks(vector_items)
        if vector_ids:
            vector_count = len(vector_ids)
        if configured:
            for row in chunk_rows:
                chunk_uri = row["uri"]
                vector_id = vector_ids.get(chunk_uri)
                if vector_id:
                    row["vector_id"] = vector_id
                    row["extra_metadata"]["vector_indexed"] = True
                else:
                    logger.warning(
                        "[skill_know.index.chunk.vector_missing] document_id={} chunk_index={} heading={} title={} preview={}",
                        document.id,
                        row["chunk_index"],
                        row["heading"],
                        safe_title,
                        preview_text(row["content"], 160),
                    )
        await SkillKnowDocumentChunk.bulk_create(
            [SkillKnowDocumentChunk(**row) for row in chunk_rows],
            batch_size=200,
        )
        return {
            "chunk_count": indexed_count,
            "vector_count": vector_count,
            "index_status": "completed" if vector_count == indexed_count or not configured else "partial",
            "chunk_preview": preview_text(chunks[0].content if chunks else "", 120),
        }

    async def delete(self, document: SkillKnowDocument) -> None:
        rows = await SkillKnowDocumentChunk.filter(document_id=document.id)
        await skill_know_chroma_store.delete_document_chunks([row.uri for row in rows])
        await SkillKnowDocumentChunk.filter(document_id=document.id).delete()


skill_know_document_index_service = SkillKnowDocumentIndexService()
