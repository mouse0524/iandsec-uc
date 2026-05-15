from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.skill_know.document_text import normalize_document_text


@dataclass
class MarkdownChunk:
    index: int
    heading: str | None
    content: str
    token_count: int


class SkillKnowMarkdownChunker:
    def chunk(self, markdown: str, *, target_chars: int = 1400, max_chars: int = 2200, overlap_chars: int = 150) -> list[MarkdownChunk]:
        text = normalize_document_text(markdown)
        if not text:
            return []
        sections = self._sections(text)
        chunks: list[MarkdownChunk] = []
        for heading, content in sections:
            for part in self._split_section(content, target_chars=target_chars, max_chars=max_chars, overlap_chars=overlap_chars):
                part = part.strip()
                if not part:
                    continue
                chunks.append(MarkdownChunk(index=len(chunks), heading=heading, content=part, token_count=self._rough_tokens(part)))
        return chunks or [MarkdownChunk(index=0, heading=None, content=text[:max_chars], token_count=self._rough_tokens(text[:max_chars]))]

    def _sections(self, markdown: str) -> list[tuple[str | None, str]]:
        sections: list[tuple[str | None, list[str]]] = []
        heading_stack: list[str] = []
        current_heading: str | None = None
        current_lines: list[str] = []
        for line in markdown.split("\n"):
            match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
            if match:
                if current_lines:
                    sections.append((current_heading, current_lines))
                    current_lines = []
                level = len(match.group(1))
                title = match.group(2).strip()
                heading_stack = heading_stack[: level - 1]
                heading_stack.append(title)
                current_heading = " / ".join(heading_stack)
            current_lines.append(line)
        if current_lines:
            sections.append((current_heading, current_lines))
        return [(heading, "\n".join(lines).strip()) for heading, lines in sections if "\n".join(lines).strip()]

    def _split_section(self, content: str, *, target_chars: int, max_chars: int, overlap_chars: int) -> list[str]:
        if len(content) <= max_chars:
            return [content]
        paragraphs = re.split(r"\n\s*\n", content)
        parts: list[str] = []
        buffer = ""
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            if len(paragraph) > max_chars:
                if buffer:
                    parts.append(buffer.strip())
                    buffer = ""
                parts.extend(self._split_long_text(paragraph, max_chars=max_chars, overlap_chars=overlap_chars))
                continue
            candidate = f"{buffer}\n\n{paragraph}".strip() if buffer else paragraph
            if len(candidate) > target_chars and buffer:
                parts.append(buffer.strip())
                overlap = buffer[-overlap_chars:].strip() if overlap_chars else ""
                buffer = f"{overlap}\n\n{paragraph}".strip() if overlap else paragraph
            else:
                buffer = candidate
        if buffer:
            parts.append(buffer.strip())
        return parts

    def _split_long_text(self, text: str, *, max_chars: int, overlap_chars: int) -> list[str]:
        parts = []
        start = 0
        while start < len(text):
            end = min(len(text), start + max_chars)
            parts.append(text[start:end].strip())
            if end >= len(text):
                break
            start = max(0, end - overlap_chars)
        return [part for part in parts if part]

    def _rough_tokens(self, text: str) -> int:
        return max(1, len(text) // 2)


skill_know_markdown_chunker = SkillKnowMarkdownChunker()
