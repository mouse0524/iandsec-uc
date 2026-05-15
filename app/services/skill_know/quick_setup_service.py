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
        chat_key_configured = chat_provider == "ollama" or bool(await skill_know_config_service.get("llm_chat_api_key", legacy_key))
        return [
            {"key": "chat_api_key", "label": "对话 API Key", "done": chat_key_configured},
            {"key": "chat_model", "label": "Chat Model", "done": bool(await skill_know_config_service.get("llm_chat_model"))},
            {"key": "reader_index", "label": "文档阅读索引", "done": True},
        ]

    async def complete(self, data) -> dict:
        logger.info(
            "[skill_know.quick_setup.complete] chat_provider={} chat_api_key_set={} legacy_api_key_set={} chat_base_url={} chat_model={}",
            data.llm_chat_provider,
            isinstance(data.llm_chat_api_key, str) and bool(data.llm_chat_api_key.strip()),
            isinstance(data.llm_api_key, str) and bool(data.llm_api_key.strip()),
            data.llm_chat_base_url,
            data.llm_chat_model,
        )
        # 空 key 不覆盖已有 key，防止“保存其他项时把 key 清空”。旧 llm_api_key 仅作为迁移兜底。
        if isinstance(data.llm_api_key, str) and data.llm_api_key.strip():
            await skill_know_config_service.set("llm_api_key", data.llm_api_key.strip(), description="OpenAI API Key")
        if isinstance(data.llm_chat_api_key, str) and data.llm_chat_api_key.strip():
            await skill_know_config_service.set("llm_chat_api_key", data.llm_chat_api_key.strip(), description="Chat API Key")
        await skill_know_config_service.set("llm_chat_provider", data.llm_chat_provider, description="Chat Provider")
        await skill_know_config_service.set("llm_chat_base_url", data.llm_chat_base_url, description="Chat Base URL")
        await skill_know_config_service.set("llm_chat_model", data.llm_chat_model, description="OpenAI Chat Model")
        return await self.state()

    async def test_connection(self, data) -> dict:
        payload = data.model_dump()
        for key in ("llm_api_key", "llm_chat_api_key"):
            if not str(payload.get(key) or "").strip():
                payload.pop(key, None)
        chat_result = await skill_know_openai_client.test_chat_connection(payload)
        return {"success": bool(chat_result.get("success")), "chat": chat_result}

    async def reset(self) -> dict:
        for key in [
            "llm_api_key",
            "llm_chat_api_key",
            "llm_chat_provider",
            "llm_chat_base_url",
            "llm_chat_model",
        ]:
            await skill_know_config_service.set(key, None)
        return await self.state()


skill_know_quick_setup_service = SkillKnowQuickSetupService()
