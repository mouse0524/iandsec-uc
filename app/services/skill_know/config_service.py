import json

from app.core.redis_client import execute_redis
from app.log import logger
from app.models.admin import SkillKnowSystemConfig


class SkillKnowConfigService:
    CACHE_KEY_ALL = "skill_know:config:all:v1"
    CACHE_TTL_SECONDS = 600
    DEFAULTS = {
        "llm_base_url": "https://api.openai.com/v1",
        "llm_chat_provider": "openai",
        "llm_embedding_provider": "openai",
        "llm_chat_base_url": "https://api.openai.com/v1",
        "llm_embedding_base_url": "https://api.openai.com/v1",
        "llm_chat_model": "gpt-4o-mini",
        "llm_embedding_model": "text-embedding-3-small",
        "llm_temperature": 0.2,
        "llm_timeout": 120,
        "retrieval_top_k": 8,
        "retrieval_score_threshold": 0.25,
        "retrieval_max_context_chars": 128000,
        "chunk_size": 1400,
        "chunk_overlap": 150,
        "markdown_optimize_enabled": True,
        "markdown_optimize_prompt": "",
        "markdown_optimize_max_chars": 30000,
        "markdown_optimize_timeout": 45,
    }
    SENSITIVE_KEYS = {"llm_api_key", "llm_chat_api_key", "llm_embedding_api_key"}

    @staticmethod
    def _mask_value(key: str, value):
        if key not in {"llm_api_key", "llm_chat_api_key", "llm_embedding_api_key", "llm_api_key_test"}:
            return value
        text = str(value or "")
        if len(text) <= 8:
            return "****"
        return text[:4] + "****" + text[-4:]

    async def get(self, key: str, default=None):
        if key not in self.SENSITIVE_KEYS:
            try:
                cached = await execute_redis("get", self.CACHE_KEY_ALL)
                if cached:
                    data = json.loads(cached)
                    if key in data:
                        return data[key]
            except Exception as exc:
                logger.warning("[skill_know.config.cache] read_failed key={} error={}", self.CACHE_KEY_ALL, str(exc))

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
            await self.clear_cache()
            return item
        item = await SkillKnowSystemConfig.create(
            key=key,
            value=store_value,
            group=group,
            description=description,
            is_sensitive=key in self.SENSITIVE_KEYS,
        )
        await self.clear_cache()
        return item

    async def llm_config(self, masked: bool = False) -> dict:
        keys = [
            "llm_api_key",
            "llm_chat_api_key",
            "llm_embedding_api_key",
            "llm_base_url",
            "llm_chat_provider",
            "llm_embedding_provider",
            "llm_chat_base_url",
            "llm_embedding_base_url",
            "llm_chat_model",
            "llm_embedding_model",
            "llm_temperature",
            "llm_timeout",
            "retrieval_top_k",
            "retrieval_score_threshold",
            "retrieval_max_context_chars",
            "chunk_size",
            "chunk_overlap",
            "markdown_optimize_enabled",
            "markdown_optimize_prompt",
            "markdown_optimize_max_chars",
            "markdown_optimize_timeout",
        ]
        data = {key: await self.get(key) for key in keys}
        if not masked:
            try:
                cache_data = {key: value for key, value in data.items() if key not in self.SENSITIVE_KEYS}
                await execute_redis("setex", self.CACHE_KEY_ALL, self.CACHE_TTL_SECONDS, json.dumps(cache_data, ensure_ascii=False))
            except Exception as exc:
                logger.warning("[skill_know.config.cache] write_failed key={} error={}", self.CACHE_KEY_ALL, str(exc))
        if masked:
            for item_key in ("llm_api_key", "llm_chat_api_key", "llm_embedding_api_key"):
                if data.get(item_key):
                    data[item_key] = self._mask_value(item_key, data[item_key])
        return data

    async def is_configured(self) -> bool:
        legacy_key = await self.get("llm_api_key")
        chat_provider = str(await self.get("llm_chat_provider", "openai") or "openai").lower()
        embedding_provider = str(await self.get("llm_embedding_provider", "openai") or "openai").lower()
        chat_ready = chat_provider == "ollama" or bool(await self.get("llm_chat_api_key", legacy_key))
        embedding_ready = embedding_provider == "ollama" or bool(await self.get("llm_embedding_api_key", legacy_key))
        return chat_ready and embedding_ready

    async def clear_cache(self) -> None:
        try:
            await execute_redis("delete", self.CACHE_KEY_ALL)
        except Exception as exc:
            logger.warning("[skill_know.config.cache] clear_failed key={} error={}", self.CACHE_KEY_ALL, str(exc))


skill_know_config_service = SkillKnowConfigService()
