import os
import logging
import contextlib
from typing import Any

from app.log import logger
from app.models.admin import SkillKnowDocumentChunk, SkillKnowVectorIndex
from app.settings import settings
from app.services.skill_know.config_service import skill_know_config_service
from app.services.skill_know.openai_client import skill_know_openai_client


class SkillKnowChromaStore:
    def __init__(self):
        self.persist_dir = os.path.join(settings.BASE_DIR, "storage", "skill_know", "chroma")
        self._chromadb_available: bool | None = None
        self._chroma_client = None
        self._collections: dict[str, Any] = {}

    def _client(self):
        os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
        logging.getLogger("chromadb.telemetry").disabled = True
        logging.getLogger("chromadb.telemetry.product").disabled = True
        logging.getLogger("chromadb.telemetry.product.posthog").disabled = True

        import chromadb
        from chromadb.config import Settings

        os.makedirs(self.persist_dir, exist_ok=True)
        if self._chroma_client is None:
            self._chroma_client = chromadb.PersistentClient(
                path=self.persist_dir,
                settings=Settings(
                    anonymized_telemetry=False,
                    chroma_telemetry_impl="chromadb.telemetry.product.posthog.Posthog",
                    chroma_product_telemetry_impl="chromadb.telemetry.product.posthog.Posthog",
                ),
            )
        return self._chroma_client

    def _is_chromadb_available(self) -> bool:
        if self._chromadb_available is not None:
            return self._chromadb_available
        try:
            import chromadb  # noqa: F401
        except ModuleNotFoundError:
            logger.warning("[skill_know.chroma.disabled] chromadb is not installed; falling back to database text search")
            self._chromadb_available = False
        else:
            self._chromadb_available = True
        return self._chromadb_available

    def _collection(self, level: int):
        name = "skill_know_l0" if level == 0 else "skill_know_l1"
        if name not in self._collections:
            self._collections[name] = self._client().get_or_create_collection(name=name, metadata={"hnsw:space": "cosine"})
        return self._collections[name]

    def _document_collection(self):
        name = "skill_know_documents"
        if name not in self._collections:
            self._collections[name] = self._client().get_or_create_collection(name=name, metadata={"hnsw:space": "cosine"})
        return self._collections[name]

    @staticmethod
    @contextlib.contextmanager
    def _quiet_chroma_output():
        with open(os.devnull, "w") as devnull:
            with contextlib.redirect_stdout(devnull), contextlib.redirect_stderr(devnull):
                yield

    async def upsert(self, *, uri: str, level: int, text: str, metadata: dict[str, Any]) -> None:
        if not text:
            return
        vector_id = f"{uri}#L{level}"
        if await skill_know_config_service.is_configured() and self._is_chromadb_available():
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
        if self._is_chromadb_available():
            for level in [0, 1]:
                try:
                    collection = self._collection(level)
                    with self._quiet_chroma_output():
                        collection.delete(ids=[f"{uri}#L{level}"])
                except Exception:
                    pass
        await SkillKnowVectorIndex.filter(uri=uri).delete()

    async def search(self, query: str, *, level: int = 0, limit: int = 20) -> list[dict]:
        if await skill_know_config_service.is_configured() and self._is_chromadb_available():
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
        if await skill_know_config_service.is_configured() and self._is_chromadb_available():
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

    async def upsert_document_chunks(self, items: list[dict[str, Any]]) -> dict[str, str]:
        if not items:
            return {}
        if not (await skill_know_config_service.is_configured() and self._is_chromadb_available()):
            return {}
        texts = [str(item.get("text") or "") for item in items]
        try:
            embeddings = await skill_know_openai_client.embeddings(texts)
        except Exception as exc:
            first = items[0]
            logger.exception(
                "[skill_know.chroma.upsert_document_chunks.failed] chunk_uri={} document_id={} chunk_index={} title={} heading={} embedding_base_url={} error={}",
                first.get("chunk_uri"),
                first.get("metadata", {}).get("document_id"),
                first.get("metadata", {}).get("chunk_index"),
                first.get("metadata", {}).get("title"),
                first.get("metadata", {}).get("heading"),
                await skill_know_config_service.get("llm_embedding_base_url", await skill_know_config_service.get("llm_base_url")),
                str(exc),
            )
            return {}

        collection = self._document_collection()
        rows: list[tuple[str, str, list[float], dict[str, Any]]] = []
        for idx, item in enumerate(items):
            embedding = embeddings[idx] if idx < len(embeddings) else []
            if not embedding:
                continue
            chunk_uri = str(item.get("chunk_uri") or "")
            text = str(item.get("text") or "")
            metadata = {k: v for k, v in dict(item.get("metadata") or {}).items() if v is not None}
            if not chunk_uri or not text:
                continue
            rows.append((chunk_uri, text, embedding, metadata))
        vector_ids: dict[str, str] = {}
        if not rows:
            return vector_ids
        try:
            collection.upsert(
                ids=[row[0] for row in rows],
                documents=[row[1] for row in rows],
                embeddings=[row[2] for row in rows],
                metadatas=[row[3] for row in rows],
            )
            return {row[0]: row[0] for row in rows}
        except Exception as exc:
            logger.warning(
                "[skill_know.chroma.upsert_document_chunks.batch_failed] count={} error={} action=fallback_single",
                len(rows),
                str(exc),
            )
        for chunk_uri, text, embedding, metadata in rows:
            try:
                collection.upsert(ids=[chunk_uri], documents=[text], embeddings=[embedding], metadatas=[metadata])
                vector_ids[chunk_uri] = chunk_uri
            except Exception as exc:
                logger.warning(
                    "[skill_know.chroma.upsert_document_chunk.single_failed] chunk_uri={} document_id={} chunk_index={} title={} heading={} error={}",
                    chunk_uri,
                    metadata.get("document_id"),
                    metadata.get("chunk_index"),
                    metadata.get("title"),
                    metadata.get("heading"),
                    str(exc),
                )
        return vector_ids

    async def diagnose(self, *, test_embedding: bool = False) -> dict[str, Any]:
        config = await skill_know_config_service.llm_config(masked=True)
        result: dict[str, Any] = {
            "persist_dir": self.persist_dir,
            "chromadb_available": self._is_chromadb_available(),
            "embedding_configured": await skill_know_config_service.is_configured(),
            "embedding_provider": config.get("llm_embedding_provider"),
            "embedding_base_url": config.get("llm_embedding_base_url") or config.get("llm_base_url"),
            "embedding_model": config.get("llm_embedding_model"),
            "collections": {},
        }
        if result["chromadb_available"]:
            try:
                collection = self._document_collection()
                result["collections"]["skill_know_documents"] = {
                    "count": collection.count(),
                }
            except Exception as exc:
                result["collections"]["skill_know_documents"] = {
                    "error": str(exc),
                }
        if test_embedding:
            try:
                vectors = await skill_know_openai_client.embeddings(["health check"])
                embedding = vectors[0] if vectors else []
                result["embedding_test"] = {
                    "success": bool(embedding),
                    "dimension": len(embedding or []),
                }
            except Exception as exc:
                result["embedding_test"] = {
                    "success": False,
                    "error": str(exc),
                }
        return result

    async def delete_document_chunks(self, chunk_uris: list[str]) -> None:
        if not chunk_uris:
            return
        if self._is_chromadb_available():
            try:
                collection = self._document_collection()
                with self._quiet_chroma_output():
                    collection.delete(ids=chunk_uris)
            except Exception:
                pass

    async def search_document_chunks(self, query: str, *, limit: int = 20) -> list[dict]:
        if await skill_know_config_service.is_configured() and self._is_chromadb_available():
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
            except Exception as exc:
                logger.warning(
                    "[skill_know.chroma.search_document_chunks.failed] query_preview={} embedding_provider={} embedding_model={} error={}",
                    str(query or "")[:120],
                    await skill_know_config_service.get("llm_embedding_provider"),
                    await skill_know_config_service.get("llm_embedding_model"),
                    str(exc),
                )
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

