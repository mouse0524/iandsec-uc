import json
from collections.abc import AsyncGenerator
from typing import Any

import httpx

from app.services.skill_know.config_service import skill_know_config_service


class SkillKnowOpenAIClient:
    async def _config(self, override: dict | None = None) -> dict:
        data = await skill_know_config_service.llm_config()
        if override:
            data.update({k: v for k, v in override.items() if v is not None})
        legacy_base = str(data.get("llm_base_url") or "https://api.openai.com/v1").rstrip("/")
        data["llm_chat_base_url"] = str(data.get("llm_chat_base_url") or legacy_base).rstrip("/")
        data["llm_embedding_base_url"] = str(data.get("llm_embedding_base_url") or legacy_base).rstrip("/")
        return data

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict] | None = None,
        override: dict | None = None,
    ) -> dict:
        config = await self._config(override)
        api_key = config.get("llm_api_key")
        if not api_key:
            raise RuntimeError("未配置 OpenAI API Key")
        payload: dict[str, Any] = {
            "model": config.get("llm_chat_model") or "gpt-4o-mini",
            "messages": messages,
            "temperature": float(config.get("llm_temperature") or 0.2),
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        async with httpx.AsyncClient(timeout=float(config.get("llm_timeout") or 60)) as client:
            resp = await client.post(
                f"{config['llm_chat_base_url']}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()

    async def stream_chat(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        config = await self._config()
        api_key = config.get("llm_api_key")
        if not api_key:
            raise RuntimeError("未配置 OpenAI API Key")
        payload: dict[str, Any] = {
            "model": config.get("llm_chat_model") or "gpt-4o-mini",
            "messages": messages,
            "temperature": float(config.get("llm_temperature") or 0.2),
            "stream": True,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        stream_timeout = httpx.Timeout(connect=10.0, read=300.0, write=60.0, pool=60.0)
        async with httpx.AsyncClient(timeout=stream_timeout) as client:
            async with client.stream(
                "POST",
                f"{config['llm_chat_base_url']}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line.removeprefix("data:").strip()
                    if not data or data == "[DONE]":
                        break
                    try:
                        yield json.loads(data)
                    except json.JSONDecodeError:
                        continue

    async def embeddings(self, texts: list[str]) -> list[list[float]]:
        config = await self._config()
        api_key = config.get("llm_api_key")
        if not api_key:
            raise RuntimeError("未配置 OpenAI API Key")
        async with httpx.AsyncClient(timeout=float(config.get("llm_timeout") or 60)) as client:
            resp = await client.post(
                f"{config['llm_embedding_base_url']}/embeddings",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": config.get("llm_embedding_model") or "text-embedding-3-small", "input": texts},
            )
            resp.raise_for_status()
            data = resp.json().get("data") or []
            return [item.get("embedding") or [] for item in data]

    async def test_connection(self, override: dict) -> dict:
        try:
            result = await self.chat(
                [{"role": "user", "content": "Reply with OK."}],
                override=override,
            )
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            return {"success": True, "message": content or "连接成功"}
        except Exception as exc:
            return {"success": False, "message": str(exc)}


skill_know_openai_client = SkillKnowOpenAIClient()
