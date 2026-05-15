from __future__ import annotations

import re
from dataclasses import dataclass

from app.models.admin import SkillKnowDocument, SkillKnowDocumentLine, SkillKnowDocumentSection
from app.services.skill_know.document_text import normalize_document_text
from app.services.skill_know.reader_agent.whoosh_search import skill_know_whoosh_search
from app.services.skill_know.utils import new_uuid, preview_text


@dataclass
class ParsedSection:
    section_key: str
    heading: str | None
    heading_path: str | None
    level: int
    start_line: int
    end_line: int
    text: str
    keywords: list[str]


class SkillKnowSectionIndexer:
    AUTO_SECTION_LINES = 80
    KEYWORD_PATTERN = re.compile(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9_@.-]{2,}")

    async def rebuild(self, document: SkillKnowDocument) -> dict:
        await self.delete(document.id)
        lines = normalize_document_text(document.content or "").splitlines()
        if not lines:
            return {"line_count": 0, "section_count": 0}
        await SkillKnowDocumentLine.bulk_create(
            [SkillKnowDocumentLine(document_id=document.id, line_no=index + 1, content=line) for index, line in enumerate(lines)],
            batch_size=500,
        )
        sections = self.parse_sections(lines)
        section_rows = [
            SkillKnowDocumentSection(
                uuid=new_uuid(),
                document_id=document.id,
                section_key=section.section_key,
                heading=section.heading,
                heading_path=section.heading_path,
                level=section.level,
                start_line=section.start_line,
                end_line=section.end_line,
                text=section.text,
                text_preview=preview_text(section.text, 300),
                keywords=section.keywords,
                token_count=max(1, len(section.text) // 2),
                extra_metadata={"title": document.title, "filename": document.filename},
            )
            for section in sections
        ]
        await SkillKnowDocumentSection.bulk_create(section_rows, batch_size=200)
        stored_sections = await SkillKnowDocumentSection.filter(document_id=document.id).order_by("start_line")
        search_rows = [
            {
                "section_id": row.id,
                "title": document.title,
                "filename": document.filename,
                "heading": row.heading,
                "heading_path": row.heading_path,
                "keywords": row.keywords or [],
                "text": row.text,
                "start_line": row.start_line,
                "end_line": row.end_line,
            }
            for row in stored_sections
        ]
        await skill_know_whoosh_search.rebuild_document(document.id, search_rows)
        return {"line_count": len(lines), "section_count": len(sections)}

    async def delete(self, document_id: int) -> None:
        await SkillKnowDocumentSection.filter(document_id=document_id).delete()
        await SkillKnowDocumentLine.filter(document_id=document_id).delete()
        await skill_know_whoosh_search.delete_document(document_id)

    def parse_sections(self, lines: list[str]) -> list[ParsedSection]:
        heading_matches: list[tuple[int, int, str]] = []
        for index, line in enumerate(lines, start=1):
            match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
            if match:
                heading_matches.append((index, len(match.group(1)), match.group(2).strip()))
        if not heading_matches:
            return self._auto_sections(lines)

        sections: list[ParsedSection] = []
        heading_stack: list[str] = []
        for idx, (start_line, level, heading) in enumerate(heading_matches):
            end_line = heading_matches[idx + 1][0] - 1 if idx + 1 < len(heading_matches) else len(lines)
            heading_stack = heading_stack[: level - 1]
            heading_stack.append(heading)
            text = "\n".join(lines[start_line - 1 : end_line]).strip()
            if not text:
                continue
            sections.append(
                ParsedSection(
                    section_key=f"heading-{len(sections)}",
                    heading=heading[:300],
                    heading_path=" / ".join(heading_stack),
                    level=level,
                    start_line=start_line,
                    end_line=end_line,
                    text=text,
                    keywords=self.extract_keywords(" ".join([heading, *heading_stack, text])),
                )
            )
        return sections or self._auto_sections(lines)

    def _auto_sections(self, lines: list[str]) -> list[ParsedSection]:
        sections: list[ParsedSection] = []
        for start in range(1, len(lines) + 1, self.AUTO_SECTION_LINES):
            end = min(len(lines), start + self.AUTO_SECTION_LINES - 1)
            text = "\n".join(lines[start - 1 : end]).strip()
            if not text:
                continue
            sections.append(
                ParsedSection(
                    section_key=f"auto-{len(sections)}",
                    heading=f"文档片段 {len(sections) + 1}",
                    heading_path=f"文档片段 {len(sections) + 1}",
                    level=0,
                    start_line=start,
                    end_line=end,
                    text=text,
                    keywords=self.extract_keywords(text),
                )
            )
        return sections

    def extract_keywords(self, text: str, limit: int = 40) -> list[str]:
        candidates = []
        seen = set()
        for item in self.KEYWORD_PATTERN.findall(str(text or "")):
            value = item.lower() if re.search(r"[A-Za-z]", item) else item
            if len(value) < 2 or value in seen:
                continue
            seen.add(value)
            candidates.append(value)
            if len(candidates) >= limit:
                break
        return candidates


skill_know_section_indexer = SkillKnowSectionIndexer()
