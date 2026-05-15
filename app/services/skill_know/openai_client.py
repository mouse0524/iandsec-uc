import json
from collections.abc import AsyncGenerator
from typing import Any

import httpx
from fastapi import HTTPException

from app.log import logger
from app.services.security import validate_external_service_url
from app.services.skill_know.config_service import skill_know_config_service


class SkillKnowOpenAIClient:
    @staticmethod
    def _provider(value: Any) -> str:
        provider = str(value or "openai").strip().lower()
        return provider if provider in {"openai", "ollama"} else "openai"

    @staticmethod
    def _validate_ollama_url(url: str | None, *, label: str) -> str:
        from urllib.parse import urlparse

        raw = str(url or "").strip().rstrip("/")
        parsed = urlparse(raw)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise RuntimeError(f"{label}地址必须是有效的 HTTP/HTTPS URL")
        if parsed.username or parsed.password:
            raise RuntimeError(f"{label}地址不能包含认证信息")
        if parsed.scheme == "https":
            try:
                return validate_external_service_url(raw, label=label)
            except HTTPException as exc:
                raise RuntimeError(str(exc.detail)) from exc
        return raw

    async def _config(self, override: dict | None = None) -> dict:
        data = await skill_know_config_service.llm_config()
        if override:
            data.update({k: v for k, v in override.items() if v is not None})
        legacy_base = str(data.get("llm_base_url") or "https://api.openai.com/v1").rstrip("/")
        data["llm_chat_provider"] = self._provider(data.get("llm_chat_provider"))
        data["llm_embedding_provider"] = self._provider(data.get("llm_embedding_provider"))
        if data["llm_chat_provider"] == "ollama":
            data["llm_chat_base_url"] = self._validate_ollama_url(data.get("llm_chat_base_url") or "http://127.0.0.1:11434", label="Ollama对话地址")
        else:
            data["llm_chat_base_url"] = validate_external_service_url(str(data.get("llm_chat_base_url") or legacy_base), label="LLM对话地址")
        if data["llm_embedding_provider"] == "ollama":
            data["llm_embedding_base_url"] = self._validate_ollama_url(data.get("llm_embedding_base_url") or "http://127.0.0.1:11434", label="Ollama向量地址")
        else:
            data["llm_embedding_base_url"] = validate_external_service_url(str(data.get("llm_embedding_base_url") or legacy_base), label="LLM向量地址")
        legacy_key = data.get("llm_api_key")
        data["llm_chat_api_key"] = data.get("llm_chat_api_key") or legacy_key
        data["llm_embedding_api_key"] = data.get("llm_embedding_api_key") or legacy_key
        return data

    @staticmethod
    def _headers(api_key: str | None = None) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    @staticmethod
    def _ollama_messages(messages: list[dict[str, Any]]) -> list[dict[str, str]]:
        result = []
        for item in messages:
            role = item.get("role") if item.get("role") in {"system", "user", "assistant"} else "user"
            result.append({"role": role, "content": str(item.get("content") or "")})
        return result

    @staticmethod
    def _ollama_to_openai_response(data: dict[str, Any]) -> dict[str, Any]:
        content = (data.get("message") or {}).get("content") or data.get("response") or ""
        return {"choices": [{"message": {"content": content}}], "raw": data}

    @staticmethod
    def _normalize_embeddings_payload(payload: Any) -> list[list[float]]:
        raw = payload
        if isinstance(raw, dict):
            raw = raw.get("embeddings") or raw.get("data") or raw.get("embedding") or []
        if not isinstance(raw, list):
            return []
        if not raw:
            return []
        if all(isinstance(item, (int, float)) for item in raw):
            return [[float(item) for item in raw]]
        vectors: list[list[float]] = []
        for item in raw:
            if isinstance(item, list):
                vectors.append([float(value) for value in item if isinstance(value, (int, float))])
                continue
            if isinstance(item, dict):
                embedding = item.get("embedding")
                if isinstance(embedding, list):
                    vectors.append([float(value) for value in embedding if isinstance(value, (int, float))])
                    continue
            vectors.append([])
        return vectors

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict] | None = None,
        override: dict | None = None,
        timeout: float | None = None,
    ) -> dict:
        config = await self._config(override)
        api_key = config.get("llm_chat_api_key")
        if config["llm_chat_provider"] != "ollama" and not api_key:
            raise RuntimeError("未配置对话 API Key")
        if config["llm_chat_provider"] == "ollama":
            payload = {
                "model": config.get("llm_chat_model") or "llama3.1",
                "messages": self._ollama_messages(messages),
                "stream": False,
                "options": {"temperature": float(config.get("llm_temperature") or 0.2)},
            }
            request_timeout = float(timeout or config.get("llm_timeout") or 60)
            async with httpx.AsyncClient(timeout=request_timeout) as client:
                resp = await client.post(f"{config['llm_chat_base_url']}/api/chat", headers=self._headers(), json=payload)
                resp.raise_for_status()
                return self._ollama_to_openai_response(resp.json())
        payload: dict[str, Any] = {
            "model": config.get("llm_chat_model") or "gpt-4o-mini",
            "messages": messages,
            "temperature": float(config.get("llm_temperature") or 0.2),
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        request_timeout = float(timeout or config.get("llm_timeout") or 60)
        async with httpx.AsyncClient(timeout=request_timeout) as client:
            resp = await client.post(
                f"{config['llm_chat_base_url']}/chat/completions",
                headers=self._headers(api_key),
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
        api_key = config.get("llm_chat_api_key")
        if config["llm_chat_provider"] != "ollama" and not api_key:
            raise RuntimeError("未配置对话 API Key")
        if config["llm_chat_provider"] == "ollama":
            payload = {
                "model": config.get("llm_chat_model") or "llama3.1",
                "messages": self._ollama_messages(messages),
                "stream": True,
                "options": {"temperature": float(config.get("llm_temperature") or 0.2)},
            }
            stream_timeout = httpx.Timeout(connect=30.0, read=300.0, write=60.0, pool=60.0)
            logger.info(
                "[skill_know.ollama.stream_chat.start] chat_base_url={} model={} message_count={} payload_chars={}",
                config.get("llm_chat_base_url"),
                config.get("llm_chat_model") or "llama3.1",
                len(messages),
                sum(len(str(item.get("content") or "")) for item in messages),
            )
            async with httpx.AsyncClient(timeout=stream_timeout) as client:
                async with client.stream("POST", f"{config['llm_chat_base_url']}/api/chat", headers=self._headers(), json=payload) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        try:
                            item = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        delta = (item.get("message") or {}).get("content") or ""
                        if delta:
                            yield {"choices": [{"delta": {"content": delta}}], "raw": item}
                        if item.get("done"):
                            break
            return
        payload: dict[str, Any] = {
            "model": config.get("llm_chat_model") or "gpt-4o-mini",
            "messages": messages,
            "temperature": float(config.get("llm_temperature") or 0.2),
            "stream": True,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        stream_timeout = httpx.Timeout(connect=30.0, read=300.0, write=60.0, pool=60.0)
        logger.info(
            "[skill_know.openai.stream_chat.start] chat_base_url={} model={} connect_timeout={} read_timeout={} message_count={} payload_chars={}",
            config.get("llm_chat_base_url"),
            config.get("llm_chat_model") or "gpt-4o-mini",
            30.0,
            300.0,
            len(messages),
            sum(len(str(item.get("content") or "")) for item in messages),
        )
        async with httpx.AsyncClient(timeout=stream_timeout) as client:
            async with client.stream(
                "POST",
                f"{config['llm_chat_base_url']}/chat/completions",
                headers=self._headers(api_key),
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
        return await self.embeddings_with_override(texts)

    async def test_chat_connection(self, override: dict) -> dict:
        try:
            result = await self.chat(
                [{"role": "user", "content": "Reply with OK."}],
                override=override,
            )
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            return {"success": True, "message": content or "连接成功"}
        except Exception as exc:
            logger.warning("[skill_know.openai.test_chat] failed error={}", repr(exc))
            return {"success": False, "message": "连接失败，请检查模型配置和网络"}

    async def test_embedding_connection(self, override: dict) -> dict:
        try:
            vectors = await self.embeddings_with_override(["hello world"], override=override)
            dimension = len(vectors[0]) if vectors and vectors[0] else 0
            return {"success": True, "message": f"连接成功，向量维度 {dimension}", "dimension": dimension}
        except Exception as exc:
            logger.warning("[skill_know.openai.test_embedding] failed error={}", repr(exc))
            return {"success": False, "message": "连接失败，请检查模型配置和网络"}

    async def test_connection(self, override: dict) -> dict:
        chat_result = await self.test_chat_connection(override)
        embedding_result = await self.test_embedding_connection(override)
        return {
            "success": bool(chat_result.get("success") and embedding_result.get("success")),
            "chat": chat_result,
            "embedding": embedding_result,
        }

    async def embeddings_with_override(self, texts: list[str], *, override: dict | None = None) -> list[list[float]]:
        if not texts:
            return []
        config = await self._config(override)
        api_key = config.get("llm_embedding_api_key")
        if config["llm_embedding_provider"] != "ollama" and not api_key:
            raise RuntimeError("未配置 Embedding API Key")
        if config["llm_embedding_provider"] == "ollama":
            model = config.get("llm_embedding_model") or "nomic-embed-text"
            async with httpx.AsyncClient(timeout=float(config.get("llm_timeout") or 60)) as client:
                payload_input: str | list[str]
                payload_input = texts[0] if len(texts) == 1 else texts
                resp = await client.post(
                    f"{config['llm_embedding_base_url']}/api/embed",
                    headers=self._headers(),
                    json={"model": model, "input": payload_input},
                )
                resp.raise_for_status()
                return self._normalize_embeddings_payload(resp.json())
        async with httpx.AsyncClient(timeout=float(config.get("llm_timeout") or 60)) as client:
            resp = await client.post(
                f"{config['llm_embedding_base_url']}/embeddings",
                headers=self._headers(api_key),
                json={"model": config.get("llm_embedding_model") or "text-embedding-3-small", "input": texts},
            )
            resp.raise_for_status()
            return self._normalize_embeddings_payload(resp.json())


skill_know_openai_client = SkillKnowOpenAIClient()


