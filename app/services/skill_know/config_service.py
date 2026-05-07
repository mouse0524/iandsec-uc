from app.log import logger
from app.models.admin import SkillKnowSystemConfig


class SkillKnowConfigService:
    DEFAULTS = {
        "llm_base_url": "https://api.openai.com/v1",
        "llm_chat_model": "gpt-4o-mini",
        "llm_embedding_model": "text-embedding-3-small",
        "llm_temperature": 0.2,
        "llm_timeout": 60,
        "retrieval_top_k": 8,
        "retrieval_score_threshold": 0.25,
        "retrieval_max_context_chars": 12000,
        "chunk_size": 1400,
        "chunk_overlap": 150,
    }
    SENSITIVE_KEYS = {"llm_api_key"}

    @staticmethod
    def _mask_value(key: str, value):
        if key not in {"llm_api_key", "llm_api_key_test"}:
            return value
        text = str(value or "")
        if len(text) <= 8:
            return "****"
        return text[:4] + "****" + text[-4:]

    async def get(self, key: str, default=None):
        item = await SkillKnowSystemConfig.filter(key=key).first()
        if not item:
            return self.DEFAULTS.get(key, default)
        value = item.value
        if isinstance(value, dict) and "__raw" in value:
            return value.get("__raw")
        return value

    async def set(self, key: str, value, *, group: str = "llm", description: str | None = None) -> SkillKnowSystemConfig:
        logger.info(
            "[skill_know.config.set] key={} type={} masked_value={}",
            key,
            type(value).__name__,
            self._mask_value(key, value),
        )
        if isinstance(value, str):
            store_value = {"__raw": value}
        elif value is None:
            store_value = None
        elif isinstance(value, (dict, list, int, float, bool)):
            store_value = value
        else:
            store_value = {"__raw": str(value)}
        logger.info(
            "[skill_know.config.set] key={} stored_type={} stored_preview={}",
            key,
            type(store_value).__name__,
            self._mask_value(key, store_value.get("__raw") if isinstance(store_value, dict) and "__raw" in store_value else store_value),
        )
        item = await SkillKnowSystemConfig.filter(key=key).first()
        if item:
            item.value = store_value
            item.group = group
            item.description = description or item.description
            item.is_sensitive = key in self.SENSITIVE_KEYS
            await item.save()
            return item
        return await SkillKnowSystemConfig.create(
            key=key,
            value=store_value,
            group=group,
            description=description,
            is_sensitive=key in self.SENSITIVE_KEYS,
        )

    async def llm_config(self, masked: bool = False) -> dict:
        keys = [
            "llm_api_key",
            "llm_base_url",
            "llm_chat_model",
            "llm_embedding_model",
            "llm_temperature",
            "llm_timeout",
            "retrieval_top_k",
            "retrieval_score_threshold",
            "retrieval_max_context_chars",
            "chunk_size",
            "chunk_overlap",
        ]
        data = {key: await self.get(key) for key in keys}
        if masked and data.get("llm_api_key"):
            key = str(data["llm_api_key"])
            data["llm_api_key"] = key[:4] + "****" + key[-4:] if len(key) > 8 else "****"
        return data

    async def is_configured(self) -> bool:
        return bool(await self.get("llm_api_key"))


skill_know_config_service = SkillKnowConfigService()
