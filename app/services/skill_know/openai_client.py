import json
import re
from collections.abc import AsyncGenerator
from typing import Any

import httpx

from app.log import logger
from app.services.security import _is_private_hostname
from app.services.skill_know.config_service import skill_know_config_service
from app.settings import settings


class SkillKnowOpenAIClient:
    MAX_CHAT_MODELS = 5

    @staticmethod
    def _provider(value: Any) -> str:
        provider = str(value or "openai").strip().lower()
        return provider if provider in {"openai", "ollama"} else "openai"

    @staticmethod
    def _validate_model_base_url(url: str | None, *, label: str, allow_private: bool = False) -> str:
        from urllib.parse import urlparse

        raw = str(url or "").strip().rstrip("/")
        parsed = urlparse(raw)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise RuntimeError(f"{label}地址必须是有效的 HTTP/HTTPS URL")
        if parsed.username or parsed.password:
            raise RuntimeError(f"{label}地址不能包含认证信息")
        if not allow_private and _is_private_hostname(parsed.hostname):
            raise RuntimeError(f"{label}地址不能指向内网或本机")
        allowed_hosts = {item.lower() for item in settings.EXTERNAL_URL_ALLOWED_HOSTS}
        if not allow_private and allowed_hosts and parsed.hostname.lower() not in allowed_hosts:
            raise RuntimeError(f"{label}地址不在允许的域名列表中")
        return raw

    @staticmethod
    def _validate_ollama_url(url: str | None, *, label: str) -> str:
        return SkillKnowOpenAIClient._validate_model_base_url(url, label=label, allow_private=True)

    @staticmethod
    def _validate_openai_compatible_url(url: str | None, *, label: str) -> str:
        return SkillKnowOpenAIClient._validate_model_base_url(url, label=label)

    async def _config(self, override: dict | None = None) -> dict:
        data = await skill_know_config_service.llm_config()
        if override:
            data.update({k: v for k, v in override.items() if v is not None})
        legacy_base = str(data.get("llm_base_url") or "https://api.openai.com/v1").rstrip("/")
        data["llm_chat_provider"] = self._provider(data.get("llm_chat_provider"))
        if data["llm_chat_provider"] == "ollama":
            data["llm_chat_base_url"] = self._validate_ollama_url(data.get("llm_chat_base_url") or "http://127.0.0.1:11434", label="Ollama对话地址")
        else:
            data["llm_chat_base_url"] = self._validate_openai_compatible_url(str(data.get("llm_chat_base_url") or legacy_base), label="LLM对话地址")
        legacy_key = data.get("llm_api_key")
        data["llm_chat_api_key"] = data.get("llm_chat_api_key") or legacy_key
        return data

    @staticmethod
    def _headers(api_key: str | None = None) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    @classmethod
    def _chat_models(cls, config: dict, *, default: str) -> list[str]:
        raw = str(config.get("llm_chat_model") or default)
        models: list[str] = []
        for item in re.split(r"[\n,;，；]+", raw):
            model = item.strip()
            if model and model not in models:
                models.append(model)
            if len(models) >= cls.MAX_CHAT_MODELS:
                break
        return models or [default]

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
            model = self._chat_models(config, default="llama3.1")[0]
            payload = {
                "model": model,
                "messages": self._ollama_messages(messages),
                "stream": False,
                "options": {"temperature": float(config.get("llm_temperature") or 0.2)},
            }
            request_timeout = float(timeout or config.get("llm_timeout") or 60)
            async with httpx.AsyncClient(timeout=request_timeout) as client:
                resp = await client.post(f"{config['llm_chat_base_url']}/api/chat", headers=self._headers(), json=payload)
                resp.raise_for_status()
                result = self._ollama_to_openai_response(resp.json())
                result["model"] = model
                return result
        request_timeout = float(timeout or config.get("llm_timeout") or 60)
        models = self._chat_models(config, default="gpt-4o-mini")
        errors: list[str] = []
        async with httpx.AsyncClient(timeout=request_timeout) as client:
            for model in models:
                payload: dict[str, Any] = {
                    "model": model,
                    "messages": messages,
                    "temperature": float(config.get("llm_temperature") or 0.2),
                }
                if tools:
                    payload["tools"] = tools
                    payload["tool_choice"] = "auto"
                try:
                    resp = await client.post(
                        f"{config['llm_chat_base_url']}/chat/completions",
                        headers=self._headers(api_key),
                        json=payload,
                    )
                    resp.raise_for_status()
                    result = resp.json()
                    result.setdefault("model", model)
                    return result
                except Exception as exc:
                    errors.append(f"{model}: {str(exc) or repr(exc)}")
                    logger.warning("[skill_know.openai.chat.model_failed] model={} error={}", model, repr(exc))
        raise RuntimeError("所有对话模型均不可用：" + "；".join(errors))

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
            model = self._chat_models(config, default="llama3.1")[0]
            payload = {
                "model": model,
                "messages": self._ollama_messages(messages),
                "stream": True,
                "options": {"temperature": float(config.get("llm_temperature") or 0.2)},
            }
            stream_timeout = httpx.Timeout(connect=30.0, read=300.0, write=60.0, pool=60.0)
            logger.info(
                "[skill_know.ollama.stream_chat.start] chat_base_url={} model={} message_count={} payload_chars={}",
                config.get("llm_chat_base_url"),
                model,
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
        stream_timeout = httpx.Timeout(connect=30.0, read=300.0, write=60.0, pool=60.0)
        payload_chars = sum(len(str(item.get("content") or "")) for item in messages)
        models = self._chat_models(config, default="gpt-4o-mini")
        errors: list[str] = []
        async with httpx.AsyncClient(timeout=stream_timeout) as client:
            for index, model in enumerate(models, start=1):
                payload: dict[str, Any] = {
                    "model": model,
                    "messages": messages,
                    "temperature": float(config.get("llm_temperature") or 0.2),
                    "stream": True,
                }
                if tools:
                    payload["tools"] = tools
                    payload["tool_choice"] = "auto"
                logger.info(
                    "[skill_know.openai.stream_chat.start] chat_base_url={} model={} fallback_index={} model_count={} connect_timeout={} read_timeout={} message_count={} payload_chars={}",
                    config.get("llm_chat_base_url"),
                    model,
                    index,
                    len(models),
                    30.0,
                    300.0,
                    len(messages),
                    payload_chars,
                )
                emitted = False
                try:
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
                                return
                            try:
                                item = json.loads(data)
                            except json.JSONDecodeError:
                                continue
                            emitted = True
                            yield item
                        return
                except Exception as exc:
                    logger.warning("[skill_know.openai.stream_chat.model_failed] model={} emitted={} error={}", model, emitted, repr(exc))
                    if emitted:
                        raise
                    errors.append(f"{model}: {str(exc) or repr(exc)}")
        raise RuntimeError("所有对话模型均不可用：" + "；".join(errors))

    async def test_chat_connection(self, override: dict) -> dict:
        try:
            result = await self.chat(
                [{"role": "user", "content": "Reply with OK."}],
                override=override,
            )
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            model = result.get("model")
            suffix = f"（模型：{model}）" if model else ""
            return {"success": True, "message": f"{content or '连接成功'}{suffix}"}
        except Exception as exc:
            logger.warning("[skill_know.openai.test_chat] failed error={}", repr(exc))
            detail = getattr(exc, "detail", None) or str(exc) or "连接失败，请检查模型配置和网络"
            return {"success": False, "message": detail}

    async def list_chat_models(self, override: dict | None = None) -> dict:
        config = await self._config(override)
        api_key = config.get("llm_chat_api_key")
        if config["llm_chat_provider"] != "ollama" and not api_key:
            raise RuntimeError("未配置对话 API Key")

        request_timeout = float(config.get("llm_timeout") or 60)
        if config["llm_chat_provider"] == "ollama":
            async with httpx.AsyncClient(timeout=request_timeout) as client:
                resp = await client.get(f"{config['llm_chat_base_url']}/api/tags", headers=self._headers())
                resp.raise_for_status()
                data = resp.json()
            models = []
            for item in data.get("models") or []:
                model_id = str(item.get("name") or item.get("model") or "").strip()
                if model_id:
                    models.append({"id": model_id, "name": model_id, "owned_by": "ollama"})
            return {"provider": "ollama", "base_url": config["llm_chat_base_url"], "models": models}

        async with httpx.AsyncClient(timeout=request_timeout) as client:
            resp = await client.get(
                f"{config['llm_chat_base_url']}/models",
                headers=self._headers(api_key),
            )
            resp.raise_for_status()
            data = resp.json()

        models = []
        for item in data.get("data") or []:
            model_id = str(item.get("id") or "").strip()
            if not model_id:
                continue
            models.append(
                {
                    "id": model_id,
                    "name": model_id,
                    "owned_by": item.get("owned_by") or "",
                    "created": item.get("created"),
                }
            )
        models.sort(key=lambda item: item["id"].lower())
        return {"provider": "openai", "base_url": config["llm_chat_base_url"], "models": models}


skill_know_openai_client = SkillKnowOpenAIClient()


