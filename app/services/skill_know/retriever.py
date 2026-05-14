from __future__ import annotations

from app.models.admin import SkillKnowDocumentChunk
from app.services.skill_know.chroma_store import skill_know_chroma_store
from app.services.skill_know.config_service import skill_know_config_service
from app.services.skill_know.utils import preview_text


class SkillKnowRetriever:
    async def retrieve_document_chunks(self, query: str, *, limit: int | None = None) -> list[dict]:
        top_k = int(limit or await skill_know_config_service.get("retrieval_top_k", 8) or 8)
        threshold = float(await skill_know_config_service.get("retrieval_score_threshold", 0.25) or 0.25)
        results = await skill_know_chroma_store.search_document_chunks(query, limit=top_k)
        items = [await self._result_to_item(result) for result in results]
        items = [item for item in items if item and float(item.get("score") or 0) >= threshold]

        if len(items) < top_k:
            fallback = await self.text_search_document_chunks(query, limit=top_k)
            seen = {str(item.get("chunk_uri") or item.get("chunk_id")) for item in items}
            for item in fallback:
                key = str(item.get("chunk_uri") or item.get("chunk_id"))
                if key not in seen:
                    items.append(item)
                    seen.add(key)
                if len(items) >= top_k:
                    break

        items.sort(key=lambda x: (-float(x.get("score") or 0), x.get("chunk_id") or 0))
        return await self._expand_with_neighbor_context(items[:top_k])

    async def text_search_document_chunks(self, query: str, *, limit: int = 20) -> list[dict]:
        rows = await SkillKnowDocumentChunk.filter(content__contains=query).limit(limit)
        return [self._chunk_to_item(row, score=0.5, matched_by="text") for row in rows]

    async def _result_to_item(self, result: dict) -> dict | None:
        metadata = result.get("metadata") or {}
        chunk = None
        vector_id = result.get("vector_id")
        if vector_id:
            chunk = await SkillKnowDocumentChunk.filter(uri=vector_id).first()
        if not chunk and metadata.get("document_id") is not None and metadata.get("chunk_index") is not None:
            chunk = await SkillKnowDocumentChunk.filter(
                document_id=int(metadata["document_id"]),
                chunk_index=int(metadata["chunk_index"]),
            ).first()
        if chunk:
            return self._chunk_to_item(
                chunk,
                score=round(float(result.get("score") or 0), 4),
                matched_by=result.get("matched_by") or "vector",
                metadata={**(chunk.extra_metadata or {}), **metadata},
            )
        content = result.get("text") or ""
        if not content:
            return None
        return {
            "source_type": "document_chunk",
            "document_id": metadata.get("document_id"),
            "chunk_id": None,
            "chunk_uri": vector_id,
            "title": metadata.get("title") or "文档片段",
            "filename": metadata.get("filename"),
            "heading": metadata.get("heading"),
            "content": content,
            "abstract": preview_text(content, 180),
            "score": round(float(result.get("score") or 0), 4),
            "matched_by": result.get("matched_by") or "vector",
            "metadata": metadata,
        }

    def _chunk_to_item(self, chunk: SkillKnowDocumentChunk, *, score: float, matched_by: str, metadata: dict | None = None) -> dict:
        data = metadata or chunk.extra_metadata or {}
        return {
            "source_type": "document_chunk",
            "document_id": chunk.document_id,
            "chunk_id": chunk.id,
            "chunk_uri": chunk.uri,
            "title": data.get("title") or "文档片段",
            "filename": data.get("filename"),
            "heading": chunk.heading or data.get("heading"),
            "content": chunk.content,
            "abstract": preview_text(chunk.content, 180),
            "score": score,
            "matched_by": matched_by,
            "metadata": data,
        }

    async def _expand_with_neighbor_context(self, items: list[dict]) -> list[dict]:
        expanded: list[dict] = []
        for item in items:
            document_id = item.get("document_id")
            chunk_index = (item.get("metadata") or {}).get("chunk_index")
            if document_id is None or chunk_index is None:
                expanded.append(item)
                continue
            try:
                index = int(chunk_index)
                rows = await SkillKnowDocumentChunk.filter(document_id=int(document_id), chunk_index__in=[index - 1, index + 1])
            except Exception:
                expanded.append(item)
                continue
            before = next((row for row in rows if row.chunk_index == index - 1), None)
            after = next((row for row in rows if row.chunk_index == index + 1), None)
            context_parts = []
            if before:
                context_parts.append(f"[上一片段]\n{before.content}")
            context_parts.append(f"[命中片段]\n{item.get('content') or ''}")
            if after:
                context_parts.append(f"[下一片段]\n{after.content}")
            metadata = dict(item.get("metadata") or {})
            metadata.update(
                {
                    "context_expanded": bool(before or after),
                    "neighbor_chunk_indexes": [
                        row.chunk_index
                        for row in (before, after)
                        if row
                    ],
                }
            )
            expanded.append(
                {
                    **item,
                    "content": "\n\n".join(context_parts),
                    "abstract": preview_text(item.get("content") or "", 180),
                    "metadata": metadata,
                }
            )
        return expanded


skill_know_retriever = SkillKnowRetriever()
