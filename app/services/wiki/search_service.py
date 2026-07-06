import re

from app.models.admin import SystemSettingItem, WikiPage


DEFAULT_DOMAIN_TERMS = {
    "授权",
    "许可",
    "到期",
    "续费",
    "维保",
    "维护",
    "终端",
    "客户端",
    "服务器",
    "版本",
    "升级",
    "安装",
    "部署",
    "工单",
    "审批",
    "驳回",
    "派单",
    "客服",
    "技术",
    "项目",
    "代理商",
    "渠道商",
    "证书",
    "密码",
    "登录",
    "同步",
    "备份",
    "webdav",
    "redmine",
}

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

def _clean_words(words: list[str] | set[str]) -> set[str]:
    return {str(item or "").strip().lower() for item in words if str(item or "").strip()}


def search_terms(
    keyword: str,
    *,
    domain_terms: list[str] | set[str] | None = None,
    stop_words: list[str] | set[str] | None = None,
) -> list[str]:
    text = str(keyword or "").strip().lower()
    domain_words = _clean_words(domain_terms or DEFAULT_DOMAIN_TERMS)
    stop_words = _clean_words(stop_words or DEFAULT_STOP_WORDS)
    matched_domain_terms = sorted((term for term in domain_words if term in text), key=text.find)
    words = re.findall(r"[0-9a-z]+|[\u4e00-\u9fff]+", text)
    terms: list[str] = matched_domain_terms[:]
    for word in words:
        if re.fullmatch(r"[\u4e00-\u9fff]+", word) and len(word) > 2:
            terms.extend(word[i : i + 2] for i in range(len(word) - 1))
        terms.append(word)
    return list(dict.fromkeys(item for item in terms if item and item not in stop_words))


class WikiSearchService:
    SETTING_SECTION = "wiki"

    async def dictionary(self) -> dict[str, list[str]]:
        setting = await SystemSettingItem.filter(section=self.SETTING_SECTION).first()
        data = setting.data if setting else {}
        domain_terms = sorted(_clean_words(DEFAULT_DOMAIN_TERMS | set(data.get("domain_terms") or [])))
        stop_words = sorted(_clean_words(DEFAULT_STOP_WORDS | set(data.get("stop_words") or [])))
        return {"domain_terms": domain_terms, "stop_words": stop_words}

    async def save_dictionary(self, *, domain_terms: list[str], stop_words: list[str]) -> dict[str, list[str]]:
        data = {"domain_terms": sorted(_clean_words(domain_terms)), "stop_words": sorted(_clean_words(stop_words))}
        setting, _ = await SystemSettingItem.get_or_create(section=self.SETTING_SECTION, defaults={"data": data})
        setting.data = data
        await setting.save()
        return await self.dictionary()

    async def search(self, keyword: str, limit: int = 10) -> list[dict]:
        dictionary = await self.dictionary()
        domain_terms = set(dictionary["domain_terms"])
        terms = search_terms(keyword, domain_terms=domain_terms, stop_words=set(dictionary["stop_words"]))
        if not terms:
            return []
        pages = await WikiPage.all().limit(500)
        scored = []
        for page in pages:
            haystack = f"{page.title}\n{page.summary or ''}\n{page.content}".lower()
            # ponytail: plain DB-backed keyword scoring; switch to full-text search only when this becomes slow.
            score = sum(haystack.count(term) * (3 if term in domain_terms else 1) for term in terms)
            if score:
                scored.append((score, page))
        scored.sort(key=lambda item: (-item[0], item[1].updated_at))
        return [await self._row(page, score=score) for score, page in scored[:limit]]

    async def _row(self, page: WikiPage, *, score: int | None = None) -> dict:
        data = await page.to_dict()
        data["score"] = score
        data["excerpt"] = (page.summary or page.content[:240]).strip()
        return data


wiki_search_service = WikiSearchService()
