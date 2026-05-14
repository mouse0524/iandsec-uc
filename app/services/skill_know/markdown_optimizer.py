from __future__ import annotations

import re

import httpx

from app.log import logger
from app.models.admin import SkillKnowPrompt
from app.services.skill_know.config_service import skill_know_config_service
from app.services.skill_know.openai_client import skill_know_openai_client
from app.services.skill_know.prompt_service import skill_know_prompt_service


DEFAULT_MARKDOWN_OPTIMIZE_PROMPT = """你是 Skill-Know 的 Markdown 文档整理器。

任务：在不改变事实、不删除图片、不破坏链接的前提下，整理转换后的 Markdown，使其更适合知识库检索与分片。

规则：
- 保留所有原始事实、数字、日期、专有名词、代码、命令、表格、链接和图片。
- 图片语法必须原样保留，尤其是 /skill-know/documents/assets/... 路径，不能改写、删除或合并。
- 只做结构优化：补齐合理标题、整理段落、统一列表、修复明显重复空行。
- 不要新增来源中没有的信息，不要输出解释，不要包裹代码块。
- 直接返回优化后的 Markdown。
"""


class SkillKnowMarkdownOptimizer:
    ASSET_PATTERN = re.compile(r"!\[[^\]]*]\(/skill-know/documents/assets/\d+/[^)]+\)")

    async def optimize(self, title: str, markdown: str) -> tuple[str, bool]:
        content = str(markdown or "").strip()
        if not content:
            return markdown, False
        enabled = await skill_know_config_service.get("markdown_optimize_enabled", True)
        if not enabled or not await skill_know_config_service.is_configured():
            return markdown, False
        try:
            max_chars = int(await skill_know_config_service.get("markdown_optimize_max_chars", 30000) or 30000)
            if len(content) > max_chars:
                logger.info(
                    "[skill_know.markdown_optimizer.skipped_oversize] title={} chars={} max_chars={}",
                    title,
                    len(content),
                    max_chars,
                )
                return markdown, False
            prompt = await self._prompt()
            result = await self._optimize_with_llm(title, content, str(prompt or DEFAULT_MARKDOWN_OPTIMIZE_PROMPT), max_chars=max_chars)
            if not self._keeps_assets(content, result):
                logger.warning("[skill_know.markdown_optimizer.asset_guard] optimization discarded because asset links changed title={}", title)
                return markdown, False
            return result, result != markdown
        except httpx.ReadTimeout:
            timeout = await skill_know_config_service.get("markdown_optimize_timeout", 45)
            logger.warning(
                "[skill_know.markdown_optimizer.timeout] title={} timeout={}s action=skip_and_keep_original",
                title,
                timeout,
            )
            return markdown, False
        except Exception as exc:
            logger.warning("[skill_know.markdown_optimizer.failed] title={} error={} action=skip_and_keep_original", title, repr(exc))
            return markdown, False

    async def _optimize_with_llm(self, title: str, markdown: str, prompt: str, *, max_chars: int) -> str:
        timeout = float(await skill_know_config_service.get("markdown_optimize_timeout", 45) or 45)
        resp = await skill_know_openai_client.chat(
            [
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"文档标题：{title}\n\nMarkdown：\n{markdown}"},
            ],
            timeout=timeout,
        )
        text = resp.get("choices", [{}])[0].get("message", {}).get("content", "")
        return self._strip_fences(text).strip() or markdown

    @classmethod
    def _keeps_assets(cls, before: str, after: str) -> bool:
        before_assets = cls.ASSET_PATTERN.findall(before or "")
        if not before_assets:
            return True
        after_text = after or ""
        return all(asset in after_text for asset in before_assets)

    @staticmethod
    def _strip_fences(text: str) -> str:
        value = str(text or "").strip()
        match = re.fullmatch(r"```(?:markdown|md)?\s*\n([\s\S]*?)\n```", value, flags=re.I)
        return match.group(1) if match else value

    async def _prompt(self) -> str:
        await skill_know_prompt_service.initialize_defaults()
        prompt = await SkillKnowPrompt.filter(key="markdown.beautifier", is_active=True).first()
        if prompt and prompt.content:
            return prompt.content
        configured = await skill_know_config_service.get("markdown_optimize_prompt", "")
        return str(configured or DEFAULT_MARKDOWN_OPTIMIZE_PROMPT)


skill_know_markdown_optimizer = SkillKnowMarkdownOptimizer()
