from app.log import logger
from app.services.skill_know.config_service import skill_know_config_service
from app.services.skill_know.openai_client import skill_know_openai_client


class SkillKnowQuickSetupService:
    async def state(self) -> dict:
        config = await skill_know_config_service.llm_config(masked=True)
        configured = await skill_know_config_service.is_configured()
        return {
            "configured": configured,
            "llm": config,
            "checklist": await self.checklist(),
        }

    async def checklist(self) -> list[dict]:
        legacy_key = await skill_know_config_service.get("llm_api_key")
        chat_provider = str(await skill_know_config_service.get("llm_chat_provider", "openai") or "openai").lower()
        embedding_provider = str(await skill_know_config_service.get("llm_embedding_provider", "openai") or "openai").lower()
        chat_key_configured = chat_provider == "ollama" or bool(await skill_know_config_service.get("llm_chat_api_key", legacy_key))
        embedding_key_configured = embedding_provider == "ollama" or bool(await skill_know_config_service.get("llm_embedding_api_key", legacy_key))
        return [
            {"key": "chat_api_key", "label": "对话 API Key", "done": chat_key_configured},
            {"key": "embedding_api_key", "label": "Embedding API Key", "done": embedding_key_configured},
            {"key": "chat_model", "label": "Chat Model", "done": bool(await skill_know_config_service.get("llm_chat_model"))},
            {"key": "embedding_model", "label": "Embedding Model", "done": bool(await skill_know_config_service.get("llm_embedding_model"))},
            {"key": "vector_store", "label": "ChromaDB 向量库", "done": True},
            {"key": "retrieval", "label": "检索与分块参数", "done": True},
        ]

    async def complete(self, data) -> dict:
        logger.info(
            "[skill_know.quick_setup.complete] chat_provider={} embedding_provider={} chat_api_key_set={} embedding_api_key_set={} legacy_api_key_set={} chat_base_url={} embedding_base_url={} chat_model={} embedding_model={}",
            data.llm_chat_provider,
            data.llm_embedding_provider,
            isinstance(data.llm_chat_api_key, str) and bool(data.llm_chat_api_key.strip()),
            isinstance(data.llm_embedding_api_key, str) and bool(data.llm_embedding_api_key.strip()),
            isinstance(data.llm_api_key, str) and bool(data.llm_api_key.strip()),
            data.llm_chat_base_url,
            data.llm_embedding_base_url,
            data.llm_chat_model,
            data.llm_embedding_model,
        )
        # 空 key 不覆盖已有 key，防止“保存其他项时把 key 清空”。旧 llm_api_key 仅作为迁移兜底。
        if isinstance(data.llm_api_key, str) and data.llm_api_key.strip():
            await skill_know_config_service.set("llm_api_key", data.llm_api_key.strip(), description="OpenAI API Key")
        if isinstance(data.llm_chat_api_key, str) and data.llm_chat_api_key.strip():
            await skill_know_config_service.set("llm_chat_api_key", data.llm_chat_api_key.strip(), description="Chat API Key")
        if isinstance(data.llm_embedding_api_key, str) and data.llm_embedding_api_key.strip():
            await skill_know_config_service.set("llm_embedding_api_key", data.llm_embedding_api_key.strip(), description="Embedding API Key")
        await skill_know_config_service.set("llm_chat_provider", data.llm_chat_provider, description="Chat Provider")
        await skill_know_config_service.set("llm_embedding_provider", data.llm_embedding_provider, description="Embedding Provider")
        await skill_know_config_service.set("llm_chat_base_url", data.llm_chat_base_url, description="Chat Base URL")
        await skill_know_config_service.set("llm_embedding_base_url", data.llm_embedding_base_url, description="Embedding Base URL")
        await skill_know_config_service.set("llm_chat_model", data.llm_chat_model, description="OpenAI Chat Model")
        await skill_know_config_service.set("llm_embedding_model", data.llm_embedding_model, description="OpenAI Embedding Model")
        await skill_know_config_service.set("retrieval_top_k", data.retrieval_top_k, group="retrieval", description="检索 Top K")
        await skill_know_config_service.set("retrieval_score_threshold", data.retrieval_score_threshold, group="retrieval", description="检索分数阈值")
        await skill_know_config_service.set("retrieval_max_context_chars", data.retrieval_max_context_chars, group="retrieval", description="最大上下文字符数")
        await skill_know_config_service.set("chunk_size", data.chunk_size, group="retrieval", description="Markdown 分块大小")
        await skill_know_config_service.set("chunk_overlap", data.chunk_overlap, group="retrieval", description="Markdown 分块重叠")
        await skill_know_config_service.set("markdown_optimize_enabled", data.markdown_optimize_enabled, group="retrieval", description="Markdown 分片前优化开关")
        if data.markdown_optimize_prompt is not None:
            await skill_know_config_service.set("markdown_optimize_prompt", data.markdown_optimize_prompt, group="retrieval", description="Markdown 优化提示词")
        await skill_know_config_service.set("markdown_optimize_max_chars", data.markdown_optimize_max_chars, group="retrieval", description="Markdown 优化最大字符数")
        await skill_know_config_service.set("markdown_optimize_timeout", data.markdown_optimize_timeout, group="retrieval", description="Markdown 优化超时时间")
        return await self.state()

    async def test_connection(self, data) -> dict:
        payload = data.model_dump()
        for key in ("llm_api_key", "llm_chat_api_key", "llm_embedding_api_key"):
            if not str(payload.get(key) or "").strip():
                payload.pop(key, None)
        return await skill_know_openai_client.test_connection(payload)

    async def reset(self) -> dict:
        for key in [
            "llm_api_key",
            "llm_chat_api_key",
            "llm_embedding_api_key",
            "llm_chat_provider",
            "llm_embedding_provider",
            "llm_chat_base_url",
            "llm_embedding_base_url",
            "llm_chat_model",
            "llm_embedding_model",
            "retrieval_top_k",
            "retrieval_score_threshold",
            "retrieval_max_context_chars",
            "chunk_size",
            "chunk_overlap",
            "markdown_optimize_enabled",
            "markdown_optimize_prompt",
            "markdown_optimize_max_chars",
            "markdown_optimize_timeout",
        ]:
            await skill_know_config_service.set(key, None)
        return await self.state()


skill_know_quick_setup_service = SkillKnowQuickSetupService()
