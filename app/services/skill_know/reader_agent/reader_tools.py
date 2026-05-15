from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.log import logger
from app.models.admin import SkillKnowDocument, SkillKnowDocumentSection
from app.services.skill_know.reader_agent.domain_terms import skill_know_domain_terms
from app.services.skill_know.reader_agent.whoosh_search import WhooshSearchHit, skill_know_whoosh_search
from app.services.skill_know.utils import preview_text


@dataclass
class Evidence:
    evidence_id: str
    document_id: int
    section_id: int | None
    title: str
    heading_path: str | None
    start_line: int
    end_line: int
    text: str

    def to_context_block(self) -> str:
        return "\n".join(
            [
                f"文档：{self.title}",
                f"章节：{self.heading_path or '-'}",
                f"行号：{self.start_line}-{self.end_line}",
                "```markdown",
                self.text,
                "```",
            ]
        )


@dataclass
class SectionCandidate:
    section: SkillKnowDocumentSection
    whoosh_score: float
    stage: str


class SkillKnowReaderTools:
    KEYWORD_PATTERN = re.compile(r"[\u4e00-\u9fff]+|[A-Za-z0-9_@.-]{2,}")

    @property
    def STOPWORDS(self) -> set[str]:
        return set(skill_know_domain_terms.list_value("stopwords"))

    @property
    def FOLLOWUP_NOISE(self) -> list[str]:
        return skill_know_domain_terms.list_value("followup_noise")

    @property
    def CONFIG_HINTS(self) -> list[str]:
        return skill_know_domain_terms.list_value("config_hints")

    @property
    def PASSWORD_HINTS(self) -> list[str]:
        return skill_know_domain_terms.list_value("password_hints")

    @property
    def TROUBLE_HINTS(self) -> list[str]:
        return skill_know_domain_terms.list_value("trouble_hints")

    @property
    def WEAK_TERMS(self) -> set[str]:
        return set(skill_know_domain_terms.list_value("weak_terms"))

    @property
    def DOMAIN_SYNONYMS(self) -> dict[str, list[str]]:
        return skill_know_domain_terms.synonyms

    def terms(self, query: str) -> list[str]:
        text = self._clean_query(query)
        terms: list[str] = []
        pinned_terms = self._domain_terms(text)
        terms.extend(pinned_terms)
        for raw in self.KEYWORD_PATTERN.findall(text):
            value = raw.strip()
            for stop in sorted(self.STOPWORDS, key=len, reverse=True):
                value = value.replace(stop, "")
            if len(value) >= 2 and value not in terms:
                terms.append(value)
            self._append_unique(terms, self._domain_terms(value))
            if re.fullmatch(r"[\u4e00-\u9fff]{4,}", value):
                for size in range(min(8, len(value)), 1, -1):
                    for start in range(0, len(value) - size + 1):
                        gram = value[start : start + size]
                        if gram not in self.WEAK_TERMS and gram not in terms:
                            terms.append(gram)
                        self._append_unique(terms, self._domain_terms(gram))
            for hint in [*self.CONFIG_HINTS, *self.PASSWORD_HINTS, *self.TROUBLE_HINTS]:
                if hint.lower() in raw.lower() and hint not in terms:
                    terms.append(hint)
        pinned = [term for term in pinned_terms if term in terms]
        rest = [term for term in terms if term not in pinned]
        rest.sort(key=lambda item: (item in self.WEAK_TERMS, -len(item), item))
        return [*pinned, *rest][:24]

    def strong_terms(self, terms: list[str]) -> list[str]:
        strong = [term for term in terms if term not in self.WEAK_TERMS and len(term) >= 2]
        strong.sort(key=lambda item: (-len(item), item))
        return strong[:10]

    def _clean_query(self, query: str) -> str:
        text = str(query or "")
        for item in self.FOLLOWUP_NOISE:
            text = text.replace(item, "")
        return text

    def _domain_terms(self, text: str) -> list[str]:
        terms: list[str] = []
        for trigger, expansions in self.DOMAIN_SYNONYMS.items():
            if trigger.lower() not in text.lower():
                continue
            self._append_unique(terms, [trigger, *expansions])
        return terms

    def _append_unique(self, target: list[str], items: list[str]) -> None:
        for item in items:
            if item not in target:
                target.append(item)

    async def search_sections(self, query: str, *, limit: int = 8) -> list[dict]:
        debug = await self.debug_search(query, limit=limit)
        return debug["items"]

    async def debug_search(self, query: str, *, limit: int = 8) -> dict[str, Any]:
        terms = self.terms(query)
        strong_terms = self.strong_terms(terms)
        if not terms:
            return {"query": query, "terms": [], "strong_terms": [], "items": [], "candidates": [], "stages": []}

        hits, stages = await self._whoosh_hits(terms, strong_terms, limit=max(limit * 10, 80))
        candidates = await self._candidate_sections(hits)
        documents = await self._documents_by_id([candidate.section.document_id for candidate in candidates])
        scored = []
        for candidate in candidates:
            row = candidate.section
            score, matched_terms, detail = self._score_section(
                query,
                row,
                terms,
                whoosh_score=candidate.whoosh_score,
                stage=candidate.stage,
                explain=True,
            )
            if score <= 0:
                continue
            scored.append((score, row, matched_terms, detail, candidate))
        scored.sort(key=lambda item: (-item[0], item[1].document_id, item[1].start_line))

        items = []
        debug_candidates = []
        for rank, (score, row, matched_terms, detail, candidate) in enumerate(scored, start=1):
            document = documents.get(row.document_id)
            item = {
                "rank": rank,
                "section_id": row.id,
                "document_id": row.document_id,
                "title": document.title if document else "",
                "filename": document.filename if document else "",
                "heading": row.heading,
                "heading_path": row.heading_path,
                "start_line": row.start_line,
                "end_line": row.end_line,
                "score": round(score, 4),
                "whoosh_score": round(candidate.whoosh_score, 4),
                "matched_terms": matched_terms,
                "backend": "whoosh",
                "stage": candidate.stage,
                "score_detail": detail,
                "preview": preview_text(row.text, 220),
            }
            debug_candidates.append(item)
            if len(items) < limit:
                items.append(item)

        logger.info(
            "[skill_know.reader.retrieve] query_preview={} terms={} strong_terms={} backend=whoosh candidates={} returned={} top={}",
            preview_text(query, 80),
            terms[:12],
            strong_terms[:8],
            len(candidates),
            len(items),
            [
                {
                    "section_id": item["section_id"],
                    "document_id": item["document_id"],
                    "score": item["score"],
                    "matched_terms": item["matched_terms"][:5],
                    "stage": item["stage"],
                    "heading": item["heading_path"] or item["heading"],
                }
                for item in items[:3]
            ],
        )
        return {
            "query": query,
            "terms": terms,
            "strong_terms": strong_terms,
            "stages": stages,
            "items": items,
            "candidates": debug_candidates[: min(30, max(limit * 3, 12))],
        }

    async def _whoosh_hits(self, terms: list[str], strong_terms: list[str], *, limit: int) -> tuple[list[WhooshSearchHit], list[dict]]:
        stages = []
        merged: dict[int, WhooshSearchHit] = {}

        if strong_terms:
            strong_hits = await skill_know_whoosh_search.search(strong_terms, limit=limit, require_all=True)
            stages.append({"name": "strong_all", "terms": strong_terms, "count": len(strong_hits)})
            for hit in strong_hits:
                hit.stage = "strong_all"
                merged.setdefault(hit.section_id, hit)

        if len(merged) < max(10, limit // 4):
            strong_or_hits = await skill_know_whoosh_search.search(strong_terms or terms, limit=limit, require_all=False)
            stages.append({"name": "strong_or", "terms": strong_terms or terms, "count": len(strong_or_hits)})
            for hit in strong_or_hits:
                hit.stage = "strong_or"
                existing = merged.get(hit.section_id)
                if not existing or hit.score > existing.score:
                    merged[hit.section_id] = hit

        if len(merged) < limit // 2:
            broad_hits = await skill_know_whoosh_search.search(terms, limit=limit, require_all=False)
            stages.append({"name": "broad_or", "terms": terms[:24], "count": len(broad_hits)})
            for hit in broad_hits:
                hit.stage = "broad_or"
                existing = merged.get(hit.section_id)
                if not existing or hit.score > existing.score:
                    merged[hit.section_id] = hit

        hits = sorted(merged.values(), key=lambda item: (-item.score, item.document_id, item.section_id))
        return hits[:limit], stages

    async def _candidate_sections(self, hits: list[WhooshSearchHit]) -> list[SectionCandidate]:
        if not hits:
            return []
        sections = await SkillKnowDocumentSection.filter(id__in=[hit.section_id for hit in hits])
        section_by_id = {section.id: section for section in sections}
        return [
            SectionCandidate(section=section_by_id[hit.section_id], whoosh_score=hit.score, stage=getattr(hit, "stage", "whoosh"))
            for hit in hits
            if hit.section_id in section_by_id
        ]

    def _score_section(
        self,
        query: str,
        row: SkillKnowDocumentSection,
        terms: list[str],
        *,
        whoosh_score: float = 0.0,
        stage: str = "whoosh",
        explain: bool = False,
    ) -> tuple[float, list[str]] | tuple[float, list[str], dict]:
        heading_blob = " ".join([row.heading or "", row.heading_path or ""])
        text_blob = " ".join([row.text_preview or "", row.text or ""])
        full_blob = " ".join([heading_blob, text_blob])
        matched_terms = []
        score = 0.0
        strong_matches = 0
        detail = {"heading": 0.0, "keyword": 0.0, "text": 0.0, "hint": 0.0, "domain": 0.0, "whoosh": 0.0, "penalty": 0.0}
        for term in terms:
            if term in heading_blob:
                add = self._term_weight(term, heading=True)
                score += add
                detail["heading"] += add
                matched_terms.append(term)
                if term not in self.WEAK_TERMS:
                    strong_matches += 1
            elif term in (row.keywords or []):
                add = self._term_weight(term) * 0.7
                score += add
                detail["keyword"] += add
                matched_terms.append(term)
                if term not in self.WEAK_TERMS:
                    strong_matches += 1
            elif term in text_blob:
                add = self._term_weight(term)
                score += add
                detail["text"] += add
                matched_terms.append(term)
                if term not in self.WEAK_TERMS:
                    strong_matches += 1

        if strong_matches == 0:
            penalty = score * 0.75
            score *= 0.25
            detail["penalty"] -= penalty
        else:
            add = min(float(whoosh_score), 80.0) * (0.1 if stage == "strong_all" else 0.08)
            score += add
            detail["whoosh"] += add

        if any(word in query for word in ("配置", "怎么", "如何", "设置")):
            add = sum(0.8 for hint in self.CONFIG_HINTS if hint in text_blob)
            score += add
            detail["hint"] += add
            if "策略配置" in heading_blob or "加解密类型" in heading_blob:
                score += 4.0
                detail["domain"] += 4.0
            if "保存" in text_blob and "推送" in text_blob:
                score += 2.5
                detail["domain"] += 2.5
        if "落地" in query and any(word in query for word in ("解密", "加密", "加解密")):
            if any(word in full_blob for word in ("落地加密", "落地解密", "加解密类型", "透明加解密")):
                score += 5.0
                detail["domain"] += 5.0
        if "wps" in query.lower() and "wps" in full_blob.lower():
            score += 5.0
            detail["domain"] += 5.0
        if any(word in query for word in ("密码", "账号", "多少")):
            add = sum(1.2 for hint in self.PASSWORD_HINTS if hint in text_blob)
            score += add
            detail["hint"] += add
        if any(word in query for word in ("报错", "失败", "无法", "异常")):
            add = sum(1.0 for hint in self.TROUBLE_HINTS if hint in text_blob)
            score += add
            detail["hint"] += add
        matched = sorted(set(matched_terms), key=lambda value: (-len(value), value))
        if explain:
            return score, matched, {key: round(value, 4) for key, value in detail.items()}
        return score, matched

    def _term_weight(self, term: str, *, heading: bool = False) -> float:
        if term in self.WEAK_TERMS:
            base = 0.25
        elif len(term) >= 6:
            base = 4.0
        elif len(term) >= 4:
            base = 2.6
        else:
            base = 1.0
        return base * (3.0 if heading else 1.0)

    async def read_section(self, section_id: int, *, evidence_id: str) -> Evidence | None:
        section = await SkillKnowDocumentSection.filter(id=section_id).first()
        if not section:
            return None
        document = await SkillKnowDocument.filter(id=section.document_id).first()
        return Evidence(
            evidence_id=evidence_id,
            document_id=section.document_id,
            section_id=section.id,
            title=document.title if document else "",
            heading_path=section.heading_path,
            start_line=section.start_line,
            end_line=section.end_line,
            text=section.text,
        )

    async def _documents_by_id(self, ids: list[int]) -> dict[int, SkillKnowDocument]:
        if not ids:
            return {}
        rows = await SkillKnowDocument.filter(id__in=sorted(set(ids)))
        return {row.id: row for row in rows}


skill_know_reader_tools = SkillKnowReaderTools()
