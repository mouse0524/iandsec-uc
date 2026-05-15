from __future__ import annotations

import asyncio
import shutil
from dataclasses import dataclass
from pathlib import Path

from app.log import logger
from app.settings import settings

try:  # pragma: no cover - import availability is covered through behavior tests.
    import jieba
    from whoosh import index
    from whoosh.analysis import Token, Tokenizer
    from whoosh.fields import ID, NUMERIC, TEXT, Schema
    from whoosh.qparser import AndGroup, MultifieldParser, OrGroup, QueryParserError, syntax
except Exception:  # pragma: no cover
    jieba = None
    index = None
    Token = None
    Tokenizer = object
    ID = NUMERIC = TEXT = Schema = None
    AndGroup = MultifieldParser = OrGroup = QueryParserError = syntax = None


@dataclass
class WhooshSearchHit:
    section_id: int
    document_id: int
    score: float
    stage: str = "whoosh"


class JiebaSearchTokenizer(Tokenizer):
    def __call__(self, value, positions=False, chars=False, keeporiginal=False, removestops=True, mode="", **kwargs):
        token = Token(positions, chars, removestops=removestops, mode=mode, **kwargs)
        pos = 0
        for word, start, end in jieba.tokenize(str(value or ""), mode="search"):
            text = word.strip().lower()
            if not text:
                continue
            token.text = text
            if keeporiginal:
                token.original = word
            if positions:
                token.pos = pos
            if chars:
                token.startchar = start
                token.endchar = end
            pos += 1
            yield token


class SkillKnowWhooshSearch:
    def __init__(self, index_dir: str | Path | None = None) -> None:
        self.index_dir = Path(index_dir or Path(settings.UPLOAD_DIR) / "skill_know" / "reader_whoosh")
        self._lock = asyncio.Lock()
        logger.info(
            "[skill_know.whoosh.index_path] index_dir={} upload_dir={} available={}",
            str(self.index_dir),
            str(settings.UPLOAD_DIR),
            self.available,
        )

    @property
    def available(self) -> bool:
        return bool(jieba and index and Schema)

    async def rebuild_document(self, document_id: int, rows: list[dict]) -> None:
        if not self.available:
            logger.warning(
                "[skill_know.whoosh.unavailable] document_id={} index_dir={} jieba={} whoosh_index={} schema={}",
                document_id,
                str(self.index_dir),
                bool(jieba),
                bool(index),
                bool(Schema),
            )
            return
        logger.info(
            "[skill_know.whoosh.rebuild_start] document_id={} rows={} index_dir={} exists={}",
            document_id,
            len(rows),
            str(self.index_dir),
            self.index_dir.exists(),
        )
        async with self._lock:
            await asyncio.to_thread(self._rebuild_document_sync, document_id, rows)

    async def delete_document(self, document_id: int) -> None:
        if not self.available:
            return
        async with self._lock:
            await asyncio.to_thread(self._delete_document_sync, document_id)

    async def search(self, terms: list[str], *, limit: int = 40, require_all: bool = False) -> list[WhooshSearchHit]:
        if not self.available or not terms:
            return []
        return await asyncio.to_thread(self._search_sync, terms, limit, require_all)

    async def stats(self) -> dict:
        if not self.available:
            return {"available": False, "index_dir": str(self.index_dir), "exists": self.index_dir.exists(), "doc_count": 0}
        async with self._lock:
            return await asyncio.to_thread(self._stats_sync)

    def reset(self) -> None:
        if self.index_dir.exists():
            shutil.rmtree(self.index_dir)

    def _schema(self):
        analyzer = JiebaSearchTokenizer()
        return Schema(
            section_id=ID(stored=True, unique=True),
            document_id=ID(stored=True),
            start_line=NUMERIC(stored=True),
            end_line=NUMERIC(stored=True),
            title=TEXT(stored=False, analyzer=analyzer, field_boost=2.0),
            filename=TEXT(stored=False, analyzer=analyzer, field_boost=1.2),
            heading=TEXT(stored=False, analyzer=analyzer, field_boost=5.0),
            heading_path=TEXT(stored=False, analyzer=analyzer, field_boost=4.0),
            keywords=TEXT(stored=False, analyzer=analyzer, field_boost=3.0),
            content=TEXT(stored=False, analyzer=analyzer),
        )

    def _open_or_create(self):
        self.index_dir.mkdir(parents=True, exist_ok=True)
        if index.exists_in(str(self.index_dir)):
            return index.open_dir(str(self.index_dir))
        return index.create_in(str(self.index_dir), self._schema())

    def _rebuild_document_sync(self, document_id: int, rows: list[dict]) -> None:
        try:
            ix = self._open_or_create()
            writer = ix.writer()
            writer.delete_by_term("document_id", str(document_id))
            indexed_count = 0
            for row in rows:
                section_id = int(row.get("section_id") or 0)
                if section_id <= 0:
                    continue
                writer.update_document(
                    section_id=str(section_id),
                    document_id=str(document_id),
                    start_line=int(row.get("start_line") or 0),
                    end_line=int(row.get("end_line") or 0),
                    title=row.get("title") or "",
                    filename=row.get("filename") or "",
                    heading=row.get("heading") or "",
                    heading_path=row.get("heading_path") or "",
                    keywords=" ".join(row.get("keywords") or []),
                    content=row.get("text") or "",
                )
                indexed_count += 1
            writer.commit()
            logger.info(
                "[skill_know.whoosh.rebuild_done] document_id={} indexed={} index_dir={} exists={}",
                document_id,
                indexed_count,
                str(self.index_dir),
                self.index_dir.exists(),
            )
        except Exception as exc:
            logger.warning(
                "[skill_know.whoosh.rebuild_failed] document_id={} index_dir={} error={}",
                document_id,
                str(self.index_dir),
                str(exc),
            )

    def _delete_document_sync(self, document_id: int) -> None:
        try:
            if not self.index_dir.exists() or not index.exists_in(str(self.index_dir)):
                return
            ix = index.open_dir(str(self.index_dir))
            writer = ix.writer()
            writer.delete_by_term("document_id", str(document_id))
            writer.commit()
        except Exception as exc:
            logger.warning("[skill_know.whoosh.delete_failed] document_id={} error={}", document_id, str(exc))

    def _search_sync(self, terms: list[str], limit: int, require_all: bool = False) -> list[WhooshSearchHit]:
        try:
            if not self.index_dir.exists() or not index.exists_in(str(self.index_dir)):
                return []
            ix = index.open_dir(str(self.index_dir))
            parser = MultifieldParser(
                ["heading", "heading_path", "keywords", "title", "filename", "content"],
                schema=ix.schema,
                group=AndGroup if require_all else OrGroup.factory(0.9),
            )
            operator = " AND " if require_all else " OR "
            query_text = operator.join(self._quote_term(term) for term in terms[:32] if len(str(term).strip()) >= 2)
            if not query_text:
                return []
            query = parser.parse(query_text)
            with ix.searcher() as searcher:
                results = searcher.search(query, limit=int(limit))
                return [
                    WhooshSearchHit(
                        section_id=int(hit["section_id"]),
                        document_id=int(hit["document_id"]),
                        score=float(hit.score or 0.0),
                    )
                    for hit in results
                ]
        except (QueryParserError, syntax.QueryParserError):
            return []
        except Exception as exc:
            logger.warning("[skill_know.whoosh.search_failed] error={}", str(exc))
            return []

    def _stats_sync(self) -> dict:
        try:
            exists = self.index_dir.exists() and index.exists_in(str(self.index_dir))
            if not exists:
                return {"available": True, "index_dir": str(self.index_dir), "exists": False, "doc_count": 0}
            ix = index.open_dir(str(self.index_dir))
            with ix.searcher() as searcher:
                return {
                    "available": True,
                    "index_dir": str(self.index_dir),
                    "exists": True,
                    "doc_count": searcher.doc_count(),
                    "doc_count_all": searcher.doc_count_all(),
                    "schema_fields": list(ix.schema.names()),
                }
        except Exception as exc:
            logger.warning("[skill_know.whoosh.stats_failed] index_dir={} error={}", str(self.index_dir), str(exc))
            return {"available": True, "index_dir": str(self.index_dir), "exists": self.index_dir.exists(), "error": str(exc)}

    def _quote_term(self, term: str) -> str:
        value = str(term or "").strip().replace('"', " ")
        return f'"{value}"'


skill_know_whoosh_search = SkillKnowWhooshSearch()
