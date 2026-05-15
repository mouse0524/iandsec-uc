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
        items = await self._results_to_items(results)
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

    async def _results_to_items(self, results: list[dict]) -> list[dict]:
        if not results:
            return []

        vector_ids = [str(result.get("vector_id") or "") for result in results if result.get("vector_id")]
        chunks_by_uri: dict[str, SkillKnowDocumentChunk] = {}
        if vector_ids:
            rows = await SkillKnowDocumentChunk.filter(uri__in=vector_ids)
            chunks_by_uri = {row.uri: row for row in rows}

        pair_keys = {
            (int(metadata["document_id"]), int(metadata["chunk_index"]))
            for metadata in (result.get("metadata") or {} for result in results)
            if metadata.get("document_id") is not None and metadata.get("chunk_index") is not None
        }
        chunks_by_pair: dict[tuple[int, int], SkillKnowDocumentChunk] = {}
        if pair_keys:
            doc_ids = sorted({doc_id for doc_id, _ in pair_keys})
            chunk_indexes = sorted({chunk_index for _, chunk_index in pair_keys})
            rows = await SkillKnowDocumentChunk.filter(document_id__in=doc_ids, chunk_index__in=chunk_indexes)
            chunks_by_pair = {(row.document_id, row.chunk_index): row for row in rows}

        items: list[dict] = []
        for result in results:
            metadata = result.get("metadata") or {}
            chunk = None
            vector_id = result.get("vector_id")
            if vector_id:
                chunk = chunks_by_uri.get(str(vector_id))
            if not chunk and metadata.get("document_id") is not None and metadata.get("chunk_index") is not None:
                try:
                    chunk = chunks_by_pair.get((int(metadata["document_id"]), int(metadata["chunk_index"])))
                except Exception:
                    chunk = None
            if chunk:
                items.append(
                    self._chunk_to_item(
                        chunk,
                        score=round(float(result.get("score") or 0), 4),
                        matched_by=result.get("matched_by") or "vector",
                        metadata={**(chunk.extra_metadata or {}), **metadata},
                    )
                )
                continue
            content = result.get("text") or ""
            if not content:
                continue
            items.append(
                {
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
            )
        return items

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
        if not items:
            return []

        lookup_pairs = {
            (int(item.get("document_id")), int((item.get("metadata") or {}).get("chunk_index")))
            for item in items
            if item.get("document_id") is not None and (item.get("metadata") or {}).get("chunk_index") is not None
        }
        neighbor_rows: dict[tuple[int, int], SkillKnowDocumentChunk] = {}
        if lookup_pairs:
            doc_ids = sorted({doc_id for doc_id, _ in lookup_pairs})
            neighbor_indexes = sorted({index for _, index in lookup_pairs})
            rows = await SkillKnowDocumentChunk.filter(
                document_id__in=doc_ids,
                chunk_index__in=[index - 1 for index in neighbor_indexes] + [index + 1 for index in neighbor_indexes],
            )
            neighbor_rows = {(row.document_id, row.chunk_index): row for row in rows}

        expanded: list[dict] = []
        for item in items:
            document_id = item.get("document_id")
            chunk_index = (item.get("metadata") or {}).get("chunk_index")
            if document_id is None or chunk_index is None:
                expanded.append(item)
                continue
            try:
                index = int(chunk_index)
            except Exception:
                expanded.append(item)
                continue
            before = neighbor_rows.get((int(document_id), index - 1))
            after = neighbor_rows.get((int(document_id), index + 1))
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
                    "neighbor_chunk_indexes": [row.chunk_index for row in (before, after) if row],
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
