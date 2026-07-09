import logging
import re
import unicodedata
from dataclasses import dataclass

import jieba
from tortoise.expressions import Q

from app.models.admin import SystemSettingItem, WikiPage


DEFAULT_STOP_WORDS = {
    "怎么",
    "如何",
    "什么",
    "是否",
    "可以",
    "一下",
    "这个",
    "那个",
    "需要",
    "进行",
    "处理",
    "the",
    "a",
    "an",
    "is",
    "to",
    "of",
    "and",
}
MIN_TERM_COVERAGE = 0.5
MAX_BLOCK_CHARS = 1200
MAX_MATCHES_PER_SOURCE = 2
PAGE_TYPE_WEIGHTS = {"practice": 1.25, "synthesis": 1.2, "concept": 1.1, "entity": 1.0, "source": 0.75, "query": 0.6}

jieba.setLogLevel(logging.WARNING)


@dataclass
class WikiMatchScore:
    score: float
    hit_count: int
    coverage: float
    excerpt: str


def _clean_words(words: list[str] | set[str]) -> set[str]:
    return {str(item or "").strip().lower() for item in words if str(item or "").strip()}


def normalize_query_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).lower()
    text = re.sub(r"\bwindows[\s_-]*(\d+)\b", r"win\1", text)
    text = re.sub(r"\bwin[\s_-]+(\d+)\b", r"win\1", text)
    return re.sub(r"\s+", " ", text).strip()


def search_terms(
    keyword: str,
    *,
    stop_words: list[str] | set[str] | None = None,
) -> list[str]:
    text = normalize_query_text(keyword)
    stop_words = _clean_words(stop_words or DEFAULT_STOP_WORDS)
    return list(
        dict.fromkeys(
            item
            for item in (word.strip().lower() for word in jieba.cut_for_search(text))
            if item and item not in stop_words and not re.fullmatch(r"[\u4e00-\u9fff]", item)
        )
    )


def _markdown_blocks(content: str) -> list[str]:
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in str(content or "").splitlines():
        if re.match(r"#{1,6}\s+", line) and current:
            blocks.append(current)
            current = [line]
        else:
            current.append(line)
    if current:
        blocks.append(current)
    return [chunk for block in ("\n".join(lines).strip() for lines in blocks) for chunk in _split_block(block)]


def _split_block(block: str) -> list[str]:
    if len(block) <= MAX_BLOCK_CHARS:
        return [block] if block else []
    chunks: list[str] = []
    current: list[str] = []
    current_size = 0
    for paragraph in (item.strip() for item in re.split(r"\n\s*\n", block) if item.strip()):
        if current and current_size + len(paragraph) + 2 > MAX_BLOCK_CHARS:
            chunks.append("\n\n".join(current))
            current = [paragraph]
            current_size = len(paragraph)
            continue
        current.append(paragraph)
        current_size += len(paragraph) + 2
    if current:
        chunks.append("\n\n".join(current))
    return chunks


def _text_score(text: str, terms: list[str], weight: int) -> int:
    text = normalize_query_text(text)
    return sum(text.count(term) * weight for term in terms)


def score_wiki_page(page, terms: list[str], *, query_text: str = "") -> WikiMatchScore | None:
    terms = list(dict.fromkeys(normalize_query_text(term) for term in terms if term))
    if not terms:
        return None

    title = str(getattr(page, "title", "") or "")
    summary = str(getattr(page, "summary", "") or "")
    content = str(getattr(page, "content", "") or "")
    blocks = _markdown_blocks(content) or [content]
    title_lower = normalize_query_text(title)
    summary_lower = normalize_query_text(summary)
    query_text = normalize_query_text(query_text)
    required_hits = 1 if len(terms) == 1 else 2
    best: WikiMatchScore | None = None

    for block in blocks:
        block_lower = normalize_query_text(block)
        hit_terms = {term for term in terms if term in title_lower or term in summary_lower or term in block_lower}
        if len(hit_terms) < required_hits:
            continue
        coverage = len(hit_terms) / len(terms)
        if coverage < MIN_TERM_COVERAGE:
            continue
        score = (
            _text_score(title, terms, 6)
            + _text_score(summary, terms, 3)
            + _text_score(block, terms, 1)
            + len(hit_terms) * 2
            + coverage * 10
        )
        if query_text and (query_text in title_lower or query_text in summary_lower or query_text in block_lower):
            score += 20
        score *= PAGE_TYPE_WEIGHTS.get(str(getattr(page, "page_type", "") or "").lower(), 1)
        match = WikiMatchScore(score=score, hit_count=len(hit_terms), coverage=coverage, excerpt=block)
        if not best or match.score > best.score:
            best = match
    return best


def _updated_timestamp(page) -> float:
    value = getattr(page, "updated_at", None)
    return value.timestamp() if hasattr(value, "timestamp") else 0


def _candidate_filter(terms: list[str]) -> Q:
    rough_terms = [variant for term in terms for variant in _term_variants(term)]
    query = Q(title__icontains=rough_terms[0]) | Q(summary__icontains=rough_terms[0]) | Q(content__icontains=rough_terms[0])
    for term in rough_terms[1:]:
        query |= Q(title__icontains=term) | Q(summary__icontains=term) | Q(content__icontains=term)
    return query


def _term_variants(term: str) -> list[str]:
    term = normalize_query_text(term)
    match = re.fullmatch(r"win(\d+)", term)
    if match:
        version = match.group(1)
        return [term, f"windows{version}", f"windows {version}", f"win {version}"]
    return [term]


def _source_key(page) -> str:
    source_id = getattr(page, "source_id", None)
    return f"source:{source_id}" if source_id else f"page:{getattr(page, 'id', id(page))}"


class WikiSearchService:
    SETTING_SECTION = "wiki"

    async def dictionary(self) -> dict[str, list[str]]:
        setting = await SystemSettingItem.filter(section=self.SETTING_SECTION).first()
        data = setting.data if setting else {}
        stop_words = sorted(_clean_words(DEFAULT_STOP_WORDS | set(data.get("stop_words") or [])))
        return {"stop_words": stop_words}

    async def save_dictionary(self, *, stop_words: list[str]) -> dict[str, list[str]]:
        data = {"stop_words": sorted(_clean_words(stop_words))}
        setting, _ = await SystemSettingItem.get_or_create(section=self.SETTING_SECTION, defaults={"data": data})
        setting.data = data
        await setting.save()
        return await self.dictionary()

    async def search(self, keyword: str, limit: int = 10) -> list[dict]:
        if limit <= 0:
            return []
        dictionary = await self.dictionary()
        terms = search_terms(keyword, stop_words=set(dictionary["stop_words"]))
        if not terms:
            return []
        pages = await WikiPage.filter(_candidate_filter(terms))
        scored = []
        for page in pages:
            match = score_wiki_page(page, terms, query_text=keyword)
            if match:
                scored.append((match, page))
        scored.sort(key=lambda item: (-item[0].score, -item[0].hit_count, -item[0].coverage, -_updated_timestamp(item[1])))
        rows = []
        source_counts: dict[str, int] = {}
        for match, page in scored:
            source_key = _source_key(page)
            if source_counts.get(source_key, 0) >= MAX_MATCHES_PER_SOURCE:
                continue
            source_counts[source_key] = source_counts.get(source_key, 0) + 1
            rows.append(await self._row(page, match=match))
            if len(rows) >= limit:
                break
        return rows

    async def _row(self, page: WikiPage, *, match: WikiMatchScore | None = None) -> dict:
        data = await page.to_dict()
        data["score"] = match.score if match else None
        data["hit_count"] = match.hit_count if match else 0
        data["coverage"] = match.coverage if match else 0
        data["matched_content"] = match.excerpt if match else page.content
        data["excerpt"] = (match.excerpt if match else page.summary or page.content[:240]).strip()
        return data


wiki_search_service = WikiSearchService()
