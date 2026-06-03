from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Any, Callable

import anyio
from fastapi import HTTPException
from redminelib import Redmine
from redminelib.exceptions import AuthError, BaseRedmineError, ForbiddenError, ResourceNotFoundError


@dataclass(frozen=True)
class RedmineConfig:
    base_url: str
    api_key: str
    timeout: float = 30.0


class RedmineClient:
    def __init__(
        self,
        config: RedmineConfig | dict[str, Any],
        *,
        redmine_factory: Callable[..., Any] = Redmine,
    ) -> None:
        if isinstance(config, dict):
            config = RedmineConfig(
                base_url=str(config.get("base_url") or config.get("redmine_base_url") or ""),
                api_key=str(config.get("api_key") or config.get("redmine_api_key") or ""),
                timeout=float(config.get("timeout") or config.get("redmine_timeout") or 30.0),
            )
        self.config = config
        self.base_url = self._normalize_base_url(config.base_url)
        self.api_key = str(config.api_key or "").strip()
        self.timeout = config.timeout
        self.redmine_factory = redmine_factory
        if not self.api_key:
            raise HTTPException(status_code=400, detail="Redmine API Key 未配置")

    async def list_issues(self, **params: Any) -> Any:
        return await self._call(lambda redmine: redmine.issue.filter(**self._clean(params)))

    async def list_projects(self) -> Any:
        return await self._call(lambda redmine: redmine.project.all())

    async def list_trackers(self) -> Any:
        return await self._call(lambda redmine: redmine.tracker.all())

    async def list_issue_priorities(self) -> Any:
        return await self._call(lambda redmine: redmine.enumeration.filter(resource="issue_priorities"))

    async def list_users(self) -> Any:
        return await self._call(lambda redmine: redmine.user.all())

    async def list_custom_fields(self) -> Any:
        return await self._call(lambda redmine: redmine.custom_field.all())

    async def get_issue(self, issue_id: int, *, include: str | None = None) -> Any:
        kwargs = {"include": include} if include else {}
        return await self._call(lambda redmine: redmine.issue.get(int(issue_id), **kwargs))

    async def create_issue(self, issue: dict[str, Any]) -> Any:
        return await self._call(lambda redmine: redmine.issue.create(**self._clean(issue)))

    async def update_issue(self, issue_id: int, issue: dict[str, Any]) -> Any:
        return await self._call(lambda redmine: redmine.issue.update(int(issue_id), **self._clean(issue)))

    async def add_issue_note(self, issue_id: int, notes: str) -> Any:
        return await self.update_issue(issue_id, {"notes": notes})

    async def upload(self, filename: str, content: bytes, *, content_type: str = "application/octet-stream") -> str:
        clean_name = str(filename or "").strip()
        if not clean_name:
            raise HTTPException(status_code=400, detail="Redmine 上传文件名不能为空")

        def _upload(redmine: Any) -> Any:
            payload = BytesIO(content)
            payload.name = clean_name
            return redmine.upload(payload, filename=clean_name)

        upload = await self._call(_upload)
        token = self._get_value(upload, "token")
        if not token:
            raise HTTPException(status_code=502, detail="Redmine 上传响应缺少 token")
        return str(token)

    async def download_attachment(self, attachment: Any) -> bytes:
        url = self._get_value(attachment, "content_url") or self._get_value(attachment, "url")
        if not url:
            raise HTTPException(status_code=502, detail="Redmine 附件缺少下载地址")

        def _download(redmine: Any) -> Any:
            return redmine.download(str(url))

        response = await self._call(_download)
        content = getattr(response, "content", response)
        if isinstance(content, bytes):
            return content
        if isinstance(content, bytearray):
            return bytes(content)
        if hasattr(content, "read"):
            return content.read()
        raise HTTPException(status_code=502, detail="Redmine 附件下载响应不支持")

    async def _call(self, func: Callable[[Any], Any]) -> Any:
        def _run() -> Any:
            redmine = self._redmine()
            return func(redmine)

        try:
            return await anyio.to_thread.run_sync(_run)
        except AuthError as exc:
            raise HTTPException(status_code=502, detail="Redmine 认证失败，请检查 API Key") from exc
        except ForbiddenError as exc:
            raise HTTPException(status_code=502, detail="Redmine 权限不足") from exc
        except ResourceNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Redmine 资源不存在") from exc
        except BaseRedmineError as exc:
            raise HTTPException(status_code=502, detail=f"Redmine 请求失败: {exc}") from exc

    def _redmine(self) -> Any:
        return self.redmine_factory(
            self.base_url,
            key=self.api_key,
            requests={"timeout": self.timeout},
        )

    @staticmethod
    def _normalize_base_url(base_url: str) -> str:
        text = str(base_url or "").strip().rstrip("/")
        if not text:
            raise HTTPException(status_code=400, detail="Redmine 地址未配置")
        if not text.startswith(("http://", "https://")):
            raise HTTPException(status_code=400, detail="Redmine 地址必须以 http:// 或 https:// 开头")
        return text

    @staticmethod
    def _clean(data: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in data.items() if value is not None}

    @staticmethod
    def _get_value(value: Any, key: str) -> Any:
        if isinstance(value, dict):
            return value.get(key)
        return getattr(value, key, None)
