import os
from typing import Any

from app.log import logger
from app.models.admin import SkillKnowDocumentChunk, SkillKnowVectorIndex
from app.settings import settings
from app.services.skill_know.config_service import skill_know_config_service
from app.services.skill_know.openai_client import skill_know_openai_client


class SkillKnowChromaStore:
    def __init__(self):
        self.persist_dir = os.path.join(settings.BASE_DIR, "storage", "skill_know", "chroma")

    def _client(self):
        import chromadb

        os.makedirs(self.persist_dir, exist_ok=True)
        return chromadb.PersistentClient(path=self.persist_dir)

    def _collection(self, level: int):
        name = "skill_know_l0" if level == 0 else "skill_know_l1"
        return self._client().get_or_create_collection(name=name, metadata={"hnsw:space": "cosine"})

    def _document_collection(self):
        return self._client().get_or_create_collection(name="skill_know_documents", metadata={"hnsw:space": "cosine"})

    async def upsert(self, *, uri: str, level: int, text: str, metadata: dict[str, Any]) -> None:
        if not text:
            return
        vector_id = f"{uri}#L{level}"
        if await skill_know_config_service.is_configured():
            embeddings = await skill_know_openai_client.embeddings([text])
            embedding = embeddings[0] if embeddings else None
            if embedding:
                self._collection(level).upsert(
                    ids=[vector_id],
                    documents=[text],
                    embeddings=[embedding],
                    metadatas=[{k: v for k, v in metadata.items() if v is not None}],
                )
        item = await SkillKnowVectorIndex.filter(uri=uri, level=level).first()
        if item:
            item.text = text
            item.vector_id = vector_id
            item.extra_metadata = metadata
            await item.save()
        else:
            await SkillKnowVectorIndex.create(uri=uri, level=level, text=text, vector_id=vector_id, extra_metadata=metadata)

    async def delete(self, uri: str) -> None:
        for level in [0, 1]:
            try:
                self._collection(level).delete(ids=[f"{uri}#L{level}"])
            except Exception:
                pass
        await SkillKnowVectorIndex.filter(uri=uri).delete()

    async def search(self, query: str, *, level: int = 0, limit: int = 20) -> list[dict]:
        if await skill_know_config_service.is_configured():
            try:
                embeddings = await skill_know_openai_client.embeddings([query])
                embedding = embeddings[0] if embeddings else None
                if embedding:
                    result = self._collection(level).query(query_embeddings=[embedding], n_results=limit)
                    ids = result.get("ids", [[]])[0]
                    docs = result.get("documents", [[]])[0]
                    metadatas = result.get("metadatas", [[]])[0]
                    distances = result.get("distances", [[]])[0]
                    return [
                        {
                            "vector_id": ids[idx],
                            "text": docs[idx],
                            "metadata": metadatas[idx] or {},
                            "score": max(0.0, 1.0 - float(distances[idx] or 0)),
                            "matched_by": f"L{level}",
                        }
                        for idx in range(len(ids))
                    ]
            except Exception:
                pass
        rows = await SkillKnowVectorIndex.filter(level=level, text__contains=query).limit(limit)
        return [
            {
                "vector_id": row.vector_id,
                "text": row.text,
                "metadata": row.extra_metadata or {},
                "score": 0.5,
                "matched_by": "text",
            }
            for row in rows
        ]

    async def upsert_document_chunk(self, *, chunk_uri: str, text: str, metadata: dict[str, Any]) -> str | None:
        if not text:
            return None
        if await skill_know_config_service.is_configured():
            try:
                embeddings = await skill_know_openai_client.embeddings([text])
                embedding = embeddings[0] if embeddings else None
                if embedding:
                    clean_metadata = {k: v for k, v in metadata.items() if v is not None}
                    self._document_collection().upsert(ids=[chunk_uri], documents=[text], embeddings=[embedding], metadatas=[clean_metadata])
                    return chunk_uri
            except Exception as exc:
                logger.exception(
                    "[skill_know.chroma.upsert_document_chunk.failed] chunk_uri={} document_id={} chunk_index={} title={} heading={} embedding_base_url={} error={}",
                    chunk_uri,
                    metadata.get("document_id"),
                    metadata.get("chunk_index"),
                    metadata.get("title"),
                    metadata.get("heading"),
                    await skill_know_config_service.get("llm_embedding_base_url", await skill_know_config_service.get("llm_base_url")),
                    str(exc),
                )
                return None
        return None

    async def delete_document_chunks(self, chunk_uris: list[str]) -> None:
        if not chunk_uris:
            return
        try:
            self._document_collection().delete(ids=chunk_uris)
        except Exception:
            pass

    async def search_document_chunks(self, query: str, *, limit: int = 20) -> list[dict]:
        if await skill_know_config_service.is_configured():
            try:
                embeddings = await skill_know_openai_client.embeddings([query])
                embedding = embeddings[0] if embeddings else None
                if embedding:
                    result = self._document_collection().query(query_embeddings=[embedding], n_results=limit)
                    ids = result.get("ids", [[]])[0]
                    docs = result.get("documents", [[]])[0]
                    metadatas = result.get("metadatas", [[]])[0]
                    distances = result.get("distances", [[]])[0]
                    return [
                        {
                            "vector_id": ids[idx],
                            "text": docs[idx],
                            "metadata": metadatas[idx] or {},
                            "score": max(0.0, 1.0 - float(distances[idx] or 0)),
                            "matched_by": "document_vector",
                        }
                        for idx in range(len(ids))
                    ]
            except Exception:
                pass
        rows = await SkillKnowDocumentChunk.filter(content__contains=query).limit(limit)
        return [
            {
                "vector_id": row.vector_id or row.uri,
                "text": row.content,
                "metadata": row.extra_metadata or {},
                "score": 0.5,
                "matched_by": "document_text",
            }
            for row in rows
        ]


skill_know_chroma_store = SkillKnowChromaStore()
