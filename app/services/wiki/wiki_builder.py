import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.models.admin import WikiLink, WikiPage, WikiSource
from app.services.llm import LLMOpenAIClient, llm_openai_client
from app.settings import settings


def slugify(value: str, fallback: str = "page") -> str:
    text = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "-", str(value or "").strip().lower()).strip("-")
    return text[:80] or fallback


def content_hash(value: str | bytes) -> str:
    data = value if isinstance(value, bytes) else value.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def normalize_page_path(path: str) -> str:
    rel_path = str(path or "").strip().replace("\\", "/").strip("/")
    if rel_path and not rel_path.endswith(".md"):
        rel_path = f"{rel_path}.md"
    return rel_path


class WikiBuilder:
    def __init__(self):
        self.root = Path(settings.UPLOAD_DIR) / "wiki"
        self.wiki_dir = self.root / "wiki"

    def _ensure_layout(self) -> None:
        for name in ("sources", "concepts", "entities", "practices", "visual", "queries", "assets", "syntheses"):
            (self.wiki_dir / name).mkdir(parents=True, exist_ok=True)
        defaults = {
            "index.md": "# Wiki Index\n\n",
            "overview.md": "# Overview\n\n",
            "log.md": "# Wiki Log\n\n",
            "glossary.md": "# Glossary\n\n",
        }
        for name, content in defaults.items():
            path = self.wiki_dir / name
            if not path.exists():
                path.write_text(content, encoding="utf-8")
        schema = self.root / "AGENTS.md"
        if not schema.exists():
            schema.write_text(
                "\n".join(
                    [
                        "# Enterprise LLM Wiki",
                        "",
                        "- raw/ is immutable source material.",
                        "- wiki/ is generated and maintained by the LLM.",
                        "- Use Markdown pages with YAML frontmatter and [[wikilinks]].",
                        "- Update wiki/index.md, wiki/overview.md, and wiki/log.md on every ingest.",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

    def normalize_llm_payload(self, raw: str, *, title: str, markdown: str) -> dict[str, Any]:
        try:
            data = json.loads(self._json_text(raw))
            if isinstance(data, dict) and isinstance(data.get("source_page"), dict):
                return data
        except json.JSONDecodeError:
            pass
        return {
            "source_page": {
                "title": title,
                "summary": markdown[:500],
                "content": self._source_content(title=title, summary=markdown[:500], body=markdown),
            },
            "concepts": [],
            "entities": [],
            "links": [],
        }

    @staticmethod
    def _json_text(raw: str) -> str:
        text = raw.strip()
        fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
        return fenced.group(1).strip() if fenced else text

    async def build(self, source: WikiSource, markdown: str) -> list[WikiPage]:
        messages = [
            {
                "role": "system",
                "content": (
                    "Return JSON only. Build an enterprise llm-wiki from the source Markdown. "
                    "The raw source is immutable. Generate and maintain wiki Markdown pages with YAML frontmatter, "
                    "[[wikilinks]], summaries, entities, concepts, contradictions, and cross-references."
                ),
            },
            {
                "role": "user",
                "content": (
                    "JSON shape: {\"source_page\":{\"title\":\"\",\"summary\":\"\",\"content\":\"\"},"
                    "\"concepts\":[{\"title\":\"\",\"summary\":\"\",\"content\":\"\"}],"
                    "\"entities\":[{\"title\":\"\",\"summary\":\"\",\"content\":\"\"}],"
                    "\"practices\":[{\"title\":\"\",\"summary\":\"\",\"content\":\"\"}],"
                    "\"syntheses\":[{\"title\":\"\",\"summary\":\"\",\"content\":\"\"}],"
                    "\"links\":[{\"from\":\"\",\"to\":\"\",\"text\":\"\"}]}.\n\n"
                    f"Current index:\n{self._read_wiki_file('index.md')[:8000]}\n\n"
                    f"Current overview:\n{self._read_wiki_file('overview.md')[:8000]}\n\n"
                    f"Source title: {source.title}\n\n{markdown[:30000]}"
                ),
            },
        ]
        try:
            result = await llm_openai_client.chat(messages)
            raw = LLMOpenAIClient._message_content(result)
        except Exception:
            raw = ""
        payload = self.normalize_llm_payload(raw, title=source.title, markdown=markdown)
        return await self.merge(source, payload)

    async def merge(self, source: WikiSource, payload: dict[str, Any]) -> list[WikiPage]:
        self._ensure_layout()
        pages: list[WikiPage] = []
        specs = [("source", payload.get("source_page") or {})]
        specs += [("concept", item) for item in payload.get("concepts") or [] if isinstance(item, dict)]
        specs += [("entity", item) for item in payload.get("entities") or [] if isinstance(item, dict)]
        specs += [("practice", item) for item in payload.get("practices") or [] if isinstance(item, dict)]
        specs += [("synthesis", item) for item in payload.get("syntheses") or [] if isinstance(item, dict)]
        touched_ids: list[int] = []
        for page_type, item in specs:
            title = str(item.get("title") or source.title).strip()
            body = str(item.get("content") or item.get("summary") or "").strip()
            if not title or not body:
                continue
            prefix = {
                "source": "sources",
                "concept": "concepts",
                "entity": "entities",
                "practice": "practices",
                "synthesis": "syntheses",
            }.get(page_type, f"{page_type}s")
            path = normalize_page_path(f"{prefix}/{slugify(title, str(source.id))}")
            if page_type == "source" and not body.lstrip().startswith("---"):
                body = self._source_content(title=title, summary=str(item.get("summary") or ""), body=body)
            page_hash = content_hash(body)
            page, _ = await WikiPage.get_or_create(
                path=path,
                defaults={
                    "title": title,
                    "page_type": page_type,
                    "content": body,
                    "source_id": source.id,
                    "summary": str(item.get("summary") or "")[:2000],
                    "content_hash": page_hash,
                },
            )
            if page.content_hash != page_hash:
                page.title = title
                page.page_type = page_type
                page.content = body
                page.source_id = source.id
                page.summary = str(item.get("summary") or "")[:2000]
                page.content_hash = page_hash
                await page.save()
            touched_ids.append(page.id)
            pages.append(page)
            self._write_page(path, body)

        if touched_ids:
            await WikiLink.filter(from_page_id__in=touched_ids).delete()
            await self._merge_links(payload.get("links") or [])
        await self._refresh_index_and_overview(source)
        self._append_log(source)
        return pages

    async def archive_query(self, *, question: str, answer: str, citations: list[dict[str, Any]]) -> str:
        self._ensure_layout()
        now = datetime.now(timezone.utc)
        rel_path = f"queries/{now.strftime('%Y%m%d-%H%M%S-%f')}-{slugify(question, 'query')}.md"
        body = self._query_content(question=question, answer=answer, citations=citations, created_at=now)
        page = await WikiPage.create(
            path=rel_path,
            title=question.strip()[:200],
            page_type="query",
            content=body,
            summary=answer.strip()[:500],
            content_hash=content_hash(body),
        )
        self._write_page(page.path, body)
        return page.path

    async def repair_page_files(self) -> list[str]:
        self._ensure_layout()
        repaired: list[str] = []
        for page in await WikiPage.all():
            path = normalize_page_path(page.path)
            if not path:
                continue
            if path != page.path:
                page.path = path
                await page.save()
            target = self.wiki_dir / path
            if not target.exists() and page.content:
                self._write_page(path, page.content)
                repaired.append(path)
        return repaired

    @staticmethod
    def _source_content(*, title: str, summary: str, body: str) -> str:
        today = datetime.now(timezone.utc).date().isoformat()
        return "\n".join(
            [
                "---",
                f'title: "{title}"',
                "type: source",
                "tags: []",
                f"date: {today}",
                "---",
                "",
                "## Summary",
                summary.strip() or body[:500].strip(),
                "",
                "## Key Claims",
                "- 待LLM维护",
                "",
                "## Connections",
                "- 待LLM维护",
                "",
                "## Source Notes",
                body.strip(),
                "",
            ]
        )

    @staticmethod
    def _query_content(
        *,
        question: str,
        answer: str,
        citations: list[dict[str, Any]],
        created_at: datetime,
    ) -> str:
        title = question.strip()[:120] or "Wiki Query"
        safe_title = title.replace('"', '\\"')
        lines = [
            "---",
            f'title: "{safe_title}"',
            "type: query",
            f"date: {created_at.date().isoformat()}",
            "---",
            "",
            "## Question",
            question.strip(),
            "",
            "## Answer",
            answer.strip(),
            "",
            "## Citations",
        ]
        if citations:
            lines += [
                f"- [{item.get('title') or item.get('path')}]({item.get('path')})"
                for item in citations
                if item.get("path")
            ]
        else:
            lines.append("- 无")
        lines.append("")
        return "\n".join(lines)

    def _write_page(self, rel_path: str, content: str) -> None:
        path = (self.wiki_dir / rel_path).resolve()
        try:
            path.relative_to(self.wiki_dir.resolve())
        except ValueError:
            raise ValueError("invalid wiki path")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content.strip() + "\n", encoding="utf-8")

    def _read_wiki_file(self, rel_path: str) -> str:
        path = self.wiki_dir / rel_path
        return path.read_text(encoding="utf-8") if path.exists() else ""

    async def _refresh_index_and_overview(self, source: WikiSource) -> None:
        rows = await WikiPage.all().order_by("page_type", "title")
        sections = {
            "source": "Sources",
            "entity": "Entities",
            "concept": "Concepts",
            "practice": "Practices",
            "synthesis": "Syntheses",
        }
        lines = ["# Wiki Index", "", "## Overview", "- [Overview](overview.md) — living synthesis", ""]
        for page_type, heading in sections.items():
            items = [row for row in rows if row.page_type == page_type]
            if not items:
                continue
            lines += [f"## {heading}"]
            lines += [f"- [{row.title}]({row.path}) — {(row.summary or '').replace(os.linesep, ' ')[:160]}" for row in items]
            lines.append("")
        self._write_page("index.md", "\n".join(lines))

        source_pages = [row for row in rows if row.page_type == "source"]
        overview = ["# Overview", "", f"Last updated: {datetime.now(timezone.utc).date().isoformat()}", ""]
        overview.append("## Sources")
        overview += [f"- [[{row.title}]] — {(row.summary or '').replace(os.linesep, ' ')[:200]}" for row in source_pages[-20:]]
        overview.append("")
        overview.append("## Current Focus")
        overview.append(f"- Latest ingest: [[{source.title}]]")
        self._write_page("overview.md", "\n".join(overview))

    def _append_log(self, source: WikiSource) -> None:
        log_path = self.wiki_dir / "log.md"
        if not log_path.exists():
            log_path.write_text("# Wiki Log\n\n", encoding="utf-8")
        rel_source = source.file_path.replace("\\", "/")
        entry = f"## [{datetime.now(timezone.utc).date().isoformat()}] ingest | {source.title}\n- Source: `{rel_source}`\n\n"
        with log_path.open("a", encoding="utf-8") as f:
            f.write(entry)

    async def _merge_links(self, links: list[dict[str, Any]]) -> None:
        for item in links:
            if not isinstance(item, dict):
                continue
            from_page = await WikiPage.filter(path=str(item.get("from") or "")).first()
            to_page = await WikiPage.filter(path=str(item.get("to") or "")).first()
            if from_page and to_page:
                await WikiLink.create(
                    from_page_id=from_page.id,
                    to_page_id=to_page.id,
                    link_text=str(item.get("text") or "")[:200],
                )


wiki_builder = WikiBuilder()
