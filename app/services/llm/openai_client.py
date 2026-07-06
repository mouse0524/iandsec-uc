import json
import re
from collections.abc import AsyncGenerator
from typing import Any

import httpx

from app.log import logger
from app.services.security import _is_private_hostname
from app.settings import settings


class LLMOpenAIClient:
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

    async def _config(self, override: dict | None = None) -> dict:
        try:
            from app.controllers.system_setting import system_setting_controller

            data = await system_setting_controller.get_full_dict()
        except Exception as exc:
            logger.warning("[llm.openai.config] fallback_to_env error={}", repr(exc))
            data = {}
        data = {
            "llm_chat_provider": data.get("llm_chat_provider") or settings.LLM_CHAT_PROVIDER,
            "llm_chat_base_url": data.get("llm_chat_base_url") or settings.LLM_CHAT_BASE_URL,
            "llm_chat_api_key": data.get("llm_chat_api_key") or settings.LLM_CHAT_API_KEY,
            "llm_chat_model": data.get("llm_chat_model") or settings.LLM_CHAT_MODEL,
            "llm_temperature": data.get("llm_temperature") or settings.LLM_TEMPERATURE,
            "llm_timeout": data.get("llm_timeout") or settings.LLM_TIMEOUT,
        }
        if override:
            data.update({k: v for k, v in override.items() if v is not None})
        data["llm_chat_provider"] = self._provider(data.get("llm_chat_provider"))
        if data["llm_chat_provider"] == "ollama":
            data["llm_chat_base_url"] = self._validate_model_base_url(
                data.get("llm_chat_base_url") or "http://127.0.0.1:11434",
                label="Ollama对话地址",
                allow_private=True,
            )
        else:
            data["llm_chat_base_url"] = self._validate_model_base_url(
                data.get("llm_chat_base_url") or "https://api.openai.com/v1",
                label="LLM对话地址",
            )
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

    @staticmethod
    def _message_content(result: dict[str, Any]) -> str:
        choices = result.get("choices") if isinstance(result, dict) else None
        if isinstance(choices, list) and choices:
            first = choices[0] if isinstance(choices[0], dict) else {}
            message = first.get("message") if isinstance(first, dict) else {}
            if isinstance(message, dict):
                return str(message.get("content") or "")
            if isinstance(message, str):
                return message
            return str(first.get("text") or "")
        if isinstance(result, dict):
            message = result.get("message")
            if isinstance(message, dict):
                return str(message.get("content") or "")
            if isinstance(message, str):
                return message
            return str(result.get("content") or result.get("response") or "")
        return ""

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
                    logger.warning("[llm.openai.chat.model_failed] model={} error={}", model, repr(exc))
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
        models = self._chat_models(config, default="gpt-4o-mini")
        errors: list[str] = []
        async with httpx.AsyncClient(timeout=stream_timeout) as client:
            for model in models:
                payload: dict[str, Any] = {
                    "model": model,
                    "messages": messages,
                    "temperature": float(config.get("llm_temperature") or 0.2),
                    "stream": True,
                }
                if tools:
                    payload["tools"] = tools
                    payload["tool_choice"] = "auto"
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
                    logger.warning("[llm.openai.stream_chat.model_failed] model={} emitted={} error={}", model, emitted, repr(exc))
                    if emitted:
                        raise
                    errors.append(f"{model}: {str(exc) or repr(exc)}")
        raise RuntimeError("所有对话模型均不可用：" + "；".join(errors))

    async def test_chat_connection(self, override: dict) -> dict:
        try:
            result = await self.chat([{"role": "user", "content": "Reply with OK."}], override=override)
            content = self._message_content(result)
            model = result.get("model")
            suffix = f"（模型：{model}）" if model else ""
            return {"success": True, "message": f"{content or '连接成功'}{suffix}"}
        except Exception as exc:
            logger.warning("[llm.openai.test_chat] failed error={}", repr(exc))
            return {"success": False, "message": str(exc) or "连接失败，请检查模型配置和网络"}

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
            models = [
                {"id": model_id, "name": model_id, "owned_by": "ollama"}
                for item in data.get("models") or []
                if (model_id := str(item.get("name") or item.get("model") or "").strip())
            ]
            return {"provider": "ollama", "base_url": config["llm_chat_base_url"], "models": models}

        async with httpx.AsyncClient(timeout=request_timeout) as client:
            resp = await client.get(f"{config['llm_chat_base_url']}/models", headers=self._headers(api_key))
            resp.raise_for_status()
            data = resp.json()

        models = [
            {
                "id": model_id,
                "name": model_id,
                "owned_by": item.get("owned_by") or "",
                "created": item.get("created"),
            }
            for item in data.get("data") or []
            if (model_id := str(item.get("id") or "").strip())
        ]
        models.sort(key=lambda item: item["id"].lower())
        return {"provider": "openai", "base_url": config["llm_chat_base_url"], "models": models}


llm_openai_client = LLMOpenAIClient()
