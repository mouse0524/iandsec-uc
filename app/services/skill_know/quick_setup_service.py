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
        configured = await skill_know_config_service.is_configured()
        return [
            {"key": "api_key", "label": "OpenAI API Key", "done": configured},
            {"key": "chat_model", "label": "Chat Model", "done": bool(await skill_know_config_service.get("llm_chat_model"))},
            {"key": "embedding_model", "label": "Embedding Model", "done": bool(await skill_know_config_service.get("llm_embedding_model"))},
            {"key": "vector_store", "label": "ChromaDB 向量库", "done": True},
            {"key": "retrieval", "label": "检索与分块参数", "done": True},
        ]

    async def complete(self, data) -> dict:
        key_preview = str(data.llm_api_key or "")
        if len(key_preview) > 8:
            key_preview = key_preview[:4] + "****" + key_preview[-4:]
        else:
            key_preview = "(empty)"
        logger.info(
            "[skill_know.quick_setup.complete] api_key_type={} api_key_preview={} chat_base_url={} embedding_base_url={} chat_model={} embedding_model={}",
            type(data.llm_api_key).__name__,
            key_preview,
            data.llm_chat_base_url,
            data.llm_embedding_base_url,
            data.llm_chat_model,
            data.llm_embedding_model,
        )
        # 空 key 不覆盖已有 key，防止“保存其他项时把 key 清空”
        if isinstance(data.llm_api_key, str) and data.llm_api_key.strip():
            await skill_know_config_service.set("llm_api_key", data.llm_api_key.strip(), description="OpenAI API Key")
        await skill_know_config_service.set("llm_chat_base_url", data.llm_chat_base_url, description="Chat Base URL")
        await skill_know_config_service.set("llm_embedding_base_url", data.llm_embedding_base_url, description="Embedding Base URL")
        await skill_know_config_service.set("llm_chat_model", data.llm_chat_model, description="OpenAI Chat Model")
        await skill_know_config_service.set("llm_embedding_model", data.llm_embedding_model, description="OpenAI Embedding Model")
        await skill_know_config_service.set("retrieval_top_k", data.retrieval_top_k, group="retrieval", description="检索 Top K")
        await skill_know_config_service.set("retrieval_score_threshold", data.retrieval_score_threshold, group="retrieval", description="检索分数阈值")
        await skill_know_config_service.set("retrieval_max_context_chars", data.retrieval_max_context_chars, group="retrieval", description="最大上下文字符数")
        await skill_know_config_service.set("chunk_size", data.chunk_size, group="retrieval", description="Markdown 分块大小")
        await skill_know_config_service.set("chunk_overlap", data.chunk_overlap, group="retrieval", description="Markdown 分块重叠")
        return await self.state()

    async def test_connection(self, data) -> dict:
        payload = data.model_dump()
        if not str(payload.get("llm_api_key") or "").strip():
            payload.pop("llm_api_key", None)
        return await skill_know_openai_client.test_connection(payload)

    async def reset(self) -> dict:
        for key in [
            "llm_api_key",
            "llm_chat_base_url",
            "llm_embedding_base_url",
            "llm_chat_model",
            "llm_embedding_model",
            "retrieval_top_k",
            "retrieval_score_threshold",
            "retrieval_max_context_chars",
            "chunk_size",
            "chunk_overlap",
        ]:
            await skill_know_config_service.set(key, None)
        return await self.state()


skill_know_quick_setup_service = SkillKnowQuickSetupService()
