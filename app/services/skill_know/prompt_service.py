from __future__ import annotations

import json

from fastapi import HTTPException

from app.core.redis_client import execute_redis
from app.log import logger
from app.models.admin import SkillKnowPrompt
from app.models.enums import SkillKnowPromptCategory
from app.services.skill_know.utils import prompt_to_dict


DEFAULT_PROMPTS = [
    {
        "key": "system.chat",
        "category": SkillKnowPromptCategory.CHAT,
        "name": "产品技术支持与数据安全专家",
        "description": "控制知识库助手的整体身份、边界和安全原则",
        "content": """你是企业级产品技术支持专家，重点服务产品问题咨询、故障排查、配置指导、权限账号、数据安全与外发审计场景。你必须基于检索到的知识库 Markdown 片段回答，不得编造不存在的产品能力、配置项、接口、命令、版本差异或安全承诺。

回答时请遵循：
1. 先识别问题类型：故障排查、配置咨询、功能说明、集成对接、权限账号、数据安全、合规审计、工单流转或未知类型。
2. 优先给出一线支持可执行的处理建议：先快速确认，再逐步排查，最后给出升级条件。
3. 如果知识库证据不足，明确说“当前知识库没有足够依据”，并列出需要补充的产品版本、部署环境、错误信息、操作步骤、影响范围、日志或截图。
4. 如果涉及数据安全、权限、文件外发、审计、密钥、备份、删除或脱敏，必须说明风险、影响范围、最小权限建议、审计要求和验证步骤。
5. 不要臆测，不要输出未经知识库支持的结论；可以给排查思路，但必须标明需要用户补充或管理员确认。
6. 回答要简洁、专业、面向解决问题，末尾列出引用来源。""",
        "variables": ["context", "question"],
    },
    {
        "key": "rag.answer",
        "category": SkillKnowPromptCategory.CHAT,
        "name": "RAG 回答模板",
        "description": "控制基于 Markdown 片段的回答结构",
        "content": """请基于已检索到的 Markdown 知识库片段回答用户问题。

要求：
- 只使用片段中能支持的事实。
- 保留产品名称、模块名称、配置项、路径、参数、错误信息、限制条件、版本信息和操作入口。
- 先给结论，再给步骤；步骤必须可执行，使用编号列表。
- 对故障类问题，按“现象确认 -> 可能原因 -> 快速检查 -> 处理步骤 -> 验证方式”组织。
- 对配置/功能类问题，按“适用场景 -> 配置路径/操作步骤 -> 注意事项 -> 验证方式”组织。
- 对风险点使用“风险提示”单独说明。
- 对安全相关问题必须说明权限边界、数据影响、审计建议和回滚方案。
- 如果多个片段冲突，指出冲突并建议以更新时间较新的文档或管理员确认为准。
- 如果无法回答，说明“当前知识库没有足够依据”，不要编造。

输出结构：
1. 结论
2. 问题判断
3. 处理步骤
4. 验证方式
5. 风险提示
6. 需要补充的信息
7. 引用来源""",
        "variables": ["context", "question"],
    },
    {
        "key": "rag.no_context",
        "category": SkillKnowPromptCategory.CHAT,
        "name": "无上下文回答模板",
        "description": "没有检索到相关片段时使用",
        "content": """当前知识库没有检索到足够相关的 Markdown 片段。请不要直接给出确定结论，也不要凭经验编造产品能力或配置路径。

请输出：
1. 当前无法确认的原因。
2. 建议用户补充的信息：产品版本、模块名称、部署环境、操作步骤、错误提示、影响范围、日志或截图。
3. 可先做的安全检查：确认账号权限、最近变更、服务状态、网络连通性、审计日志是否异常。
4. 建议管理员补充到知识库的文档内容。""",
        "variables": ["question"],
    },
    {
        "key": "security.expert",
        "category": SkillKnowPromptCategory.SYSTEM,
        "name": "数据安全专家规则",
        "description": "安全、权限、审计、合规类问题的专家约束",
        "content": """你是数据安全专家。遇到账号权限、数据访问、文件外发、接口调用、日志审计、敏感信息、密钥、备份恢复、数据删除、数据脱敏、合规要求相关问题时，请优先执行安全分析，并把安全建议融入产品支持答案。

分析维度：
- 数据分类分级
- 最小权限原则
- 身份认证与授权
- 操作审计
- 数据传输与存储加密
- 密钥与凭证保护
- 数据泄露影响面
- 回滚与应急处置
- 合规留痕

必须做到：
- 不建议用户绕过权限、关闭审计、明文传输敏感数据、共享密钥或直接暴露内部接口。
- 涉及权限变更时，提醒遵循最小权限、审批留痕和到期回收。
- 涉及文件外发或共享时，提醒访问范围、有效期、水印/下载控制、审计记录和撤销方案。
- 涉及异常访问或疑似泄露时，先隔离风险，再保全日志，再做影响面排查。""",
        "variables": ["question", "context"],
    },
    {
        "key": "support.troubleshooting",
        "category": SkillKnowPromptCategory.CHAT,
        "name": "产品故障排查模板",
        "description": "产品技术支持排障问题的回答结构",
        "content": """你是产品技术支持专家。处理故障排查问题时，请优先帮助一线支持快速定位和推进闭环。

回答结构：
1. 现象确认：复述用户现象，指出还需要确认的关键信息。
2. 可能原因：只列知识库支持的原因；不足时标明“需要确认”。
3. 快速检查：给出低风险、可立即执行的检查项。
4. 深入排查：给出日志、配置、权限、网络、任务状态等排查路径。
5. 解决方案：按步骤说明处理方法和预期结果。
6. 验证方式：说明如何确认问题已经恢复。
7. 升级处理条件：说明何时转技术支持或安全响应。

必须基于知识库片段，不足时先追问产品版本、部署环境、错误信息、操作步骤、影响范围、最近变更、日志或截图。""",
        "variables": ["question", "context"],
    },
    {
        "key": "support.escalation",
        "category": SkillKnowPromptCategory.CHAT,
        "name": "升级处理规则",
        "description": "判断何时升级技术支持或安全响应",
        "content": """当问题满足以下任一条件时，建议升级技术支持或安全响应：
- 涉及疑似数据泄露、权限绕过、未授权访问
- 影响生产业务连续性
- 涉及数据删除、损坏、不可恢复
- 涉及密钥泄露、账号异常、审计缺失
- 知识库无明确方案且用户影响范围较大
- 多次操作仍无法恢复
- 涉及客户现场重大阻塞、批量用户不可用、核心流程无法提交或审批

升级时请列出必须提供的信息：
1. 产品版本、模块名称、部署方式和环境。
2. 问题开始时间、影响用户/组织/数据范围。
3. 完整错误信息、请求 ID、任务 ID、审计日志或服务日志。
4. 用户操作步骤、已尝试处理方式和处理结果。
5. 最近变更：配置、权限、网络、版本、证书、密钥、策略。
6. 相关截图或录屏，注意脱敏敏感信息。""",
        "variables": ["question", "context"],
    },
    {
        "key": "markdown.beautifier",
        "category": SkillKnowPromptCategory.SKILL,
        "name": "Markdown 分片前优化",
        "description": "文档转换完成后、分片索引前，对 Markdown 做结构整理并保护图片链接",
        "content": """你是 Skill-Know 的 Markdown 文档整理器。

任务：在不改变事实、不删除图片、不破坏链接的前提下，整理转换后的 Markdown，使其更适合知识库检索与分片。

规则：
- 保留所有原始事实、数字、日期、专有名词、代码、命令、表格、链接和图片。
- 图片语法必须原样保留，尤其是 /skill-know/documents/assets/... 路径，不能改写、删除或合并。
- 只做结构优化：补齐合理标题、整理段落、统一列表、修复明显重复空行。
- 不要新增来源中没有的信息，不要输出解释，不要包裹代码块。
- 直接返回优化后的 Markdown。""",
        "variables": ["title", "markdown"],
    },
]

DEPRECATED_DEFAULT_PROMPT_KEYS = {"learning.feedback_summary"}


class SkillKnowPromptService:
    CACHE_TTL_SECONDS = 600
    _defaults_ready = False

    @staticmethod
    def _prompt_cache_key(key: str) -> str:
        return f"skill_know:prompt:{key}:v1"

    @staticmethod
    def _list_cache_key(category: str | None, include_inactive: bool) -> str:
        return f"skill_know:prompts:list:{category or 'all'}:{int(include_inactive)}:v1"

    async def initialize_defaults(self, *, update_existing: bool = False, prune_deprecated: bool = False) -> dict:
        if self._defaults_ready and not update_existing and not prune_deprecated:
            return {"created": 0, "updated": 0, "deleted": 0}
        created_count = 0
        updated_count = 0
        for item in DEFAULT_PROMPTS:
            exists = await SkillKnowPrompt.filter(key=item["key"]).first()
            if not exists:
                await SkillKnowPrompt.create(**item)
                created_count += 1
            elif update_existing:
                changed = False
                for field in ("category", "name", "description", "content", "variables"):
                    if getattr(exists, field) != item[field]:
                        setattr(exists, field, item[field])
                        changed = True
                if changed:
                    await exists.save()
                    updated_count += 1
        deleted_count = 0
        if prune_deprecated:
            deleted_count = await SkillKnowPrompt.filter(key__in=DEPRECATED_DEFAULT_PROMPT_KEYS).delete()
        if created_count or updated_count or deleted_count:
            await self.clear_cache()
        if not update_existing and not prune_deprecated:
            self._defaults_ready = True
        return {"created": created_count, "updated": updated_count, "deleted": deleted_count}

    async def sync_defaults(self) -> dict:
        result = await self.initialize_defaults(update_existing=True, prune_deprecated=True)
        await self.clear_cache()
        self._defaults_ready = True
        total = await SkillKnowPrompt.all().count()
        return {**result, "total": total}

    async def list(self, category: str | None = None, include_inactive: bool = False) -> list[dict]:
        await self.initialize_defaults()
        cache_key = self._list_cache_key(category, include_inactive)
        try:
            cached = await execute_redis("get", cache_key)
            if cached:
                return json.loads(cached)
        except Exception as exc:
            logger.warning("[skill_know.prompt.cache] list_read_failed key={} error={}", cache_key, str(exc))

        query = SkillKnowPrompt.all()
        if category:
            query = query.filter(category=category)
        if not include_inactive:
            query = query.filter(is_active=True)
        rows = await query.order_by("category", "key")
        data = [await prompt_to_dict(item) for item in rows]
        try:
            await execute_redis("setex", cache_key, self.CACHE_TTL_SECONDS, json.dumps(data, ensure_ascii=False))
        except Exception as exc:
            logger.warning("[skill_know.prompt.cache] list_write_failed key={} error={}", cache_key, str(exc))
        return data

    async def get(self, key: str) -> dict:
        await self.initialize_defaults()
        cache_key = self._prompt_cache_key(key)
        try:
            cached = await execute_redis("get", cache_key)
            if cached:
                return json.loads(cached)
        except Exception as exc:
            logger.warning("[skill_know.prompt.cache] get_read_failed key={} error={}", cache_key, str(exc))

        item = await SkillKnowPrompt.filter(key=key).first()
        if not item:
            raise HTTPException(status_code=404, detail="提示词不存在")
        data = await prompt_to_dict(item)
        try:
            await execute_redis("setex", cache_key, self.CACHE_TTL_SECONDS, json.dumps(data, ensure_ascii=False))
        except Exception as exc:
            logger.warning("[skill_know.prompt.cache] get_write_failed key={} error={}", cache_key, str(exc))
        return data

    async def update(self, key: str, data) -> dict:
        item = await SkillKnowPrompt.filter(key=key).first()
        if not item:
            raise HTTPException(status_code=404, detail="提示词不存在")
        if data.content is not None:
            item.content = data.content
        if data.is_active is not None:
            item.is_active = data.is_active
        await item.save()
        self._defaults_ready = True
        await self.clear_cache(key)
        return await prompt_to_dict(item)

    async def reset(self, key: str) -> dict:
        default = next((item for item in DEFAULT_PROMPTS if item["key"] == key), None)
        if not default:
            raise HTTPException(status_code=400, detail="该提示词没有默认值")
        item = await SkillKnowPrompt.filter(key=key).first()
        if not item:
            item = await SkillKnowPrompt.create(**default)
        else:
            item.name = default["name"]
            item.description = default["description"]
            item.category = default["category"]
            item.content = default["content"]
            item.variables = default["variables"]
            item.is_active = True
            await item.save()
        self._defaults_ready = True
        await self.clear_cache(key)
        return await prompt_to_dict(item)

    async def clear_cache(self, key: str | None = None) -> None:
        try:
            keys: set[str] = set()
            if key:
                keys.add(self._prompt_cache_key(key))
            cursor = 0
            while True:
                cursor, batch = await execute_redis("scan", cursor=cursor, match="skill_know:prompts:list:*", count=200)
                keys.update(batch or [])
                if int(cursor or 0) == 0:
                    break
            if not key:
                cursor = 0
                while True:
                    cursor, batch = await execute_redis("scan", cursor=cursor, match="skill_know:prompt:*", count=200)
                    keys.update(batch or [])
                    if int(cursor or 0) == 0:
                        break
            if keys:
                await execute_redis("delete", *keys)
        except Exception as exc:
            logger.warning("[skill_know.prompt.cache] clear_failed key={} error={}", key or "*", str(exc))


skill_know_prompt_service = SkillKnowPromptService()
