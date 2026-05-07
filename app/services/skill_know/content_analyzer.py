import json
import re

from app.services.skill_know.config_service import skill_know_config_service
from app.services.skill_know.openai_client import skill_know_openai_client
from app.services.skill_know.utils import preview_text


class SkillKnowContentAnalyzer:
    async def analyze(self, title: str, content: str, *, use_llm: bool = True) -> dict:
        if use_llm and await skill_know_config_service.is_configured():
            try:
                return await self._analyze_with_llm(title, content)
            except Exception:
                pass
        return self._analyze_by_rule(title, content)

    async def _analyze_with_llm(self, title: str, content: str) -> dict:
        sample = content[:12000]
        prompt = (
            "你是 Skill-Know 知识库内容分析器。请把文档处理为 JSON，字段包括："
            "abstract(100字内摘要), overview(Markdown结构化概览), category(短分类), tags(字符串数组), "
            "keywords(字符串数组)。只返回JSON。\n\n"
            f"标题：{title}\n\n内容：\n{sample}"
        )
        resp = await skill_know_openai_client.chat([{"role": "user", "content": prompt}])
        text = resp.get("choices", [{}])[0].get("message", {}).get("content", "")
        match = re.search(r"\{.*\}", text, flags=re.S)
        data = json.loads(match.group(0) if match else text)
        return {
            "abstract": data.get("abstract") or preview_text(content, 160),
            "overview": data.get("overview") or self._make_overview(title, content),
            "category": data.get("category") or "未分类",
            "tags": data.get("tags") or [],
            "keywords": data.get("keywords") or data.get("tags") or [],
        }

    def _analyze_by_rule(self, title: str, content: str) -> dict:
        words = re.findall(r"[\u4e00-\u9fa5a-zA-Z0-9_+-]{2,}", content[:5000])
        seen = []
        for word in words:
            if word not in seen:
                seen.append(word)
            if len(seen) >= 8:
                break
        return {
            "abstract": preview_text(content, 180) or title,
            "overview": self._make_overview(title, content),
            "category": "未分类",
            "tags": seen[:5],
            "keywords": seen,
        }

    def _make_overview(self, title: str, content: str) -> str:
        return f"## {title}\n\n{preview_text(content, 1200)}"

skill_know_content_analyzer = SkillKnowContentAnalyzer()
