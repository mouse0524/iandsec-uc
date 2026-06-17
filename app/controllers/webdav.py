import secrets
import hmac
import hashlib
import os
from base64 import b64encode
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import quote, quote_from_bytes, urlencode, unquote, urlparse, urlunparse
from xml.etree import ElementTree as ET
import json

import httpx
from fastapi import HTTPException, UploadFile

from app.core.redis_client import execute_redis
from app.log import logger
from app.models.admin import WebDavShareLink
from app.controllers.system_setting import normalize_webdav_base_url, system_setting_controller
from app.settings import settings


class WebDavController:
    LIST_CACHE_TTL_SECONDS = 24 * 60 * 60
    LIST_CACHE_KEY_PATTERN = "webdav:list:*"
    PREVIEW_CACHE_DIR = os.path.join(settings.BASE_DIR, "storage", "webdav_preview_cache")

    @staticmethod
    def _auth(conf: dict) -> tuple[str, str]:
        return conf["webdav_username"], conf["webdav_password"]

    def _client(self, conf: dict, timeout: float) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=timeout, follow_redirects=True)

    def _auth_headers(self, conf: dict, headers: dict[str, str] | None = None) -> dict[str, str]:
        username, password = self._auth(conf)
        token = b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
        merged = {"Authorization": f"Basic {token}"}
        if headers:
            merged.update(headers)
        return merged

    @staticmethod
    def _raise_webdav_error(action: str, status_code: int) -> HTTPException:
        if status_code in {401, 403}:
            return HTTPException(status_code=502, detail="WebDAV认证失败，请检查系统设置中的账号和密码")
        if status_code == 404:
            return HTTPException(status_code=404, detail=f"{action}失败：目标路径不存在")
        if status_code == 405:
            return HTTPException(status_code=400, detail=f"{action}失败：当前路径不支持该操作")
        if status_code == 409:
            return HTTPException(status_code=409, detail=f"{action}失败：资源冲突")
        if status_code == 423:
            return HTTPException(status_code=423, detail=f"{action}失败：资源被锁定")
        if status_code == 429:
            return HTTPException(status_code=429, detail="WebDAV请求过于频繁，请稍后重试")
        if status_code >= 500:
            return HTTPException(status_code=502, detail="WebDAV服务暂时不可用，请稍后重试")
        return HTTPException(status_code=400, detail=f"{action}失败：WebDAV返回状态码 {status_code}")

    @staticmethod
    def _raise_webdav_network_error(action: str, exc: Exception) -> HTTPException:
        if isinstance(exc, httpx.TimeoutException):
            return HTTPException(status_code=504, detail=f"{action}超时，请稍后重试")
        if isinstance(exc, httpx.ConnectError):
            return HTTPException(status_code=502, detail="无法连接WebDAV服务，请检查服务地址和网络")
        if isinstance(exc, httpx.RequestError):
            return HTTPException(status_code=502, detail=f"{action}失败：与WebDAV服务通信异常")
        return HTTPException(status_code=502, detail=f"{action}失败：网络异常")

    @staticmethod
    def _now_like(dt: datetime) -> datetime:
        return datetime.now(dt.tzinfo) if dt.tzinfo is not None else datetime.now()

    @staticmethod
    def _normalize_path(path: str | None) -> str:
        p = (path or "/").strip()
        if not p:
            p = "/"
        if not p.startswith("/"):
            p = f"/{p}"
        p = p.replace("\\", "/")
        while "//" in p:
            p = p.replace("//", "/")
        pure = PurePosixPath(p)
        if ".." in pure.parts:
            raise HTTPException(status_code=400, detail="非法路径")
        norm = str(pure)
        if not norm.startswith("/"):
            norm = f"/{norm}"
        return norm

    @staticmethod
    def _normalize_base_prefix(path: str | None) -> str:
        p = (path or "").strip().replace("\\", "/")
        if not p:
            return ""
        if not p.startswith("/"):
            p = f"/{p}"
        while "//" in p:
            p = p.replace("//", "/")
        pure = PurePosixPath(p)
        norm = str(pure)
        if norm == ".":
            return ""
        if not norm.startswith("/"):
            norm = f"/{norm}"
        if norm != "/":
            norm = norm.rstrip("/")
        return norm

    @staticmethod
    async def _get_config() -> dict:
        data = await system_setting_controller.get_full_dict()
        if not data.get("webdav_enabled"):
            raise HTTPException(status_code=400, detail="WebDAV未启用，请先在系统设置中启用")
        if not data.get("webdav_base_url"):
            raise HTTPException(status_code=400, detail="WebDAV Base URL 未配置")
        data["webdav_base_url"] = normalize_webdav_base_url(data.get("webdav_base_url"))
        if not data.get("webdav_username") or not data.get("webdav_password"):
            raise HTTPException(status_code=400, detail="WebDAV账号或密码未配置")
        return data

    @staticmethod
    def _get_signature_secret(conf: dict) -> str:
        secret = str(conf.get("webdav_signature_secret") or "").strip()
        if not secret:
            raise HTTPException(status_code=400, detail="WebDAV分享签名密钥未配置")
        return secret

    @staticmethod
    def _sign(secret: str, code: str, ts: int) -> str:
        msg = f"{code}:{ts}".encode("utf-8")
        return hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()

    @staticmethod
    def _signature_ttl_seconds(conf: dict) -> int:
        return int(conf.get("webdav_signature_ttl") or 24) * 60 * 60

    async def build_share_signature(self, *, code: str) -> dict[str, int | str]:
        conf = await self._get_config()
        secret = self._get_signature_secret(conf)
        ts = int(datetime.now(timezone.utc).timestamp())
        sig = self._sign(secret, code, ts)
        return {"ts": ts, "sig": sig}

    async def build_direct_download_signature(self, *, path: str) -> dict[str, int | str]:
        conf = await self._get_config()
        secret = self._get_signature_secret(conf)
        norm_path = self._normalize_path(path)
        ts = int(datetime.now(timezone.utc).timestamp())
        sig = self._sign(secret, f"direct-download:{norm_path}", ts)
        return {"ts": ts, "sig": sig}

    async def verify_share_signature(self, *, code: str, ts: int, sig: str) -> None:
        conf = await self._get_config()
        secret = self._get_signature_secret(conf)
        signature_ttl = self._signature_ttl_seconds(conf)
        now_ts = int(datetime.now(timezone.utc).timestamp())
        if abs(now_ts - int(ts)) > signature_ttl:
            raise HTTPException(status_code=401, detail="签名已过期")
        expected = self._sign(secret, code, int(ts))
        if not hmac.compare_digest(expected, str(sig)):
            raise HTTPException(status_code=401, detail="签名校验失败")

    async def verify_direct_download_signature(self, *, path: str, ts: int, sig: str) -> None:
        conf = await self._get_config()
        secret = self._get_signature_secret(conf)
        signature_ttl = self._signature_ttl_seconds(conf)
        now_ts = int(datetime.now(timezone.utc).timestamp())
        if abs(now_ts - int(ts)) > signature_ttl:
            raise HTTPException(status_code=401, detail="签名已过期")
        norm_path = self._normalize_path(path)
        expected = self._sign(secret, f"direct-download:{norm_path}", int(ts))
        if not hmac.compare_digest(expected, str(sig)):
            raise HTTPException(status_code=401, detail="签名校验失败")

    async def build_preview_cache_signature(self, *, cache_key: str, filename: str) -> dict[str, int | str]:
        conf = await self._get_config()
        secret = self._get_signature_secret(conf)
        ts = int(datetime.now(timezone.utc).timestamp())
        sig = self._sign(secret, f"preview-cache:{cache_key}:{filename}", ts)
        return {"ts": ts, "sig": sig}

    async def verify_preview_cache_signature(self, *, cache_key: str, filename: str, ts: int, sig: str) -> None:
        conf = await self._get_config()
        secret = self._get_signature_secret(conf)
        signature_ttl = self._signature_ttl_seconds(conf)
        now_ts = int(datetime.now(timezone.utc).timestamp())
        if abs(now_ts - int(ts)) > signature_ttl:
            raise HTTPException(status_code=401, detail="signature expired")
        expected = self._sign(secret, f"preview-cache:{cache_key}:{filename}", int(ts))
        if not hmac.compare_digest(expected, str(sig)):
            raise HTTPException(status_code=401, detail="signature invalid")

    @staticmethod
    def _build_url(base_url: str, path: str) -> str:
        base = base_url.rstrip("/")
        safe_path = quote(path, safe="/()[]-_.~")
        return f"{base}{safe_path}"

    def build_direct_download_url(self, conf: dict, file_path: str, *, include_credentials: bool = True) -> str:
        base_url = normalize_webdav_base_url(conf.get("webdav_base_url"))
        norm_path = self._normalize_path(file_path)
        url = self._build_url(base_url, norm_path)
        if not include_credentials:
            return url
        username, password = self._auth(conf)
        parsed = urlparse(url)
        credentials = f"{quote_from_bytes(str(username).encode('utf-8'))}:{quote_from_bytes(str(password).encode('utf-8'))}@"
        return urlunparse(parsed._replace(netloc=f"{credentials}{parsed.netloc}"))

    async def get_direct_download_url(self, file_path: str, *, include_credentials: bool = True) -> str:
        conf = await self._get_config()
        return self.build_direct_download_url(conf, file_path, include_credentials=include_credentials)

    @classmethod
    def _build_list_url(cls, base_url: str, path: str) -> str:
        norm_path = cls._normalize_path(path)
        return cls._build_url(base_url, norm_path)

    def _is_share_expired(self, share: WebDavShareLink) -> bool:
        return self._now_like(share.expire_time) > share.expire_time

    def _share_to_dict(
        self,
        share: WebDavShareLink,
        *,
        creator_name: str = "",
        download_url: str = "",
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if data is None:
            data = {}
            for field in ["id", "code", "file_path", "file_name", "expire_time", "is_active", "created_by"]:
                value = getattr(share, field, None)
                if isinstance(value, datetime):
                    value = value.strftime(settings.DATETIME_FORMAT)
                data[field] = value
        expired = self._is_share_expired(share)
        active = bool(getattr(share, "is_active", False)) and not expired
        data["is_active"] = active
        data["is_expired"] = expired
        data["status"] = "active" if active else ("expired" if expired else "inactive")
        data["creator_name"] = creator_name
        data["download_url"] = download_url
        return data

    @staticmethod
    def _list_cache_key(path: str) -> str:
        return f"webdav:list:{quote(path, safe='')}"

    @staticmethod
    def _parent_path(path: str) -> str:
        if path == "/":
            return "/"
        parts = [p for p in path.split("/") if p]
        if len(parts) <= 1:
            return "/"
        return "/" + "/".join(parts[:-1])

    async def _get_cached_list(self, path: str) -> list[dict[str, Any]] | None:
        key = self._list_cache_key(path)
        try:
            raw = await execute_redis("get", key)
            if not raw:
                return None
            data = json.loads(raw)
            if isinstance(data, list):
                return data
        except Exception as exc:
            logger.warning("[webdav.cache.get] key={} error={}", key, str(exc))
        return None

    async def _set_cached_list(self, path: str, rows: list[dict[str, Any]]) -> None:
        key = self._list_cache_key(path)
        try:
            await execute_redis("setex", key, self.LIST_CACHE_TTL_SECONDS, json.dumps(rows, ensure_ascii=False))
        except Exception as exc:
            logger.warning("[webdav.cache.set] key={} error={}", key, str(exc))

    async def _invalidate_list_cache(self, paths: list[str]) -> None:
        keys = [self._list_cache_key(path) for path in set(paths) if path]
        if not keys:
            return
        try:
            await execute_redis("delete", *keys)
        except Exception as exc:
            logger.warning("[webdav.cache.delete] keys={} error={}", ",".join(keys), str(exc))

    async def clear_list_cache(self) -> int:
        cleared = 0
        cursor = 0
        try:
            while True:
                cursor, keys = await execute_redis("scan", cursor=cursor, match=self.LIST_CACHE_KEY_PATTERN, count=500)
                keys = list(keys or [])
                if keys:
                    cleared += int(await execute_redis("delete", *keys) or 0)
                if int(cursor or 0) == 0:
                    break
        except Exception as exc:
            logger.warning("[webdav.cache.clear] pattern={} error={}", self.LIST_CACHE_KEY_PATTERN, str(exc))
            raise HTTPException(status_code=500, detail="清理网盘缓存失败") from exc
        logger.info("[webdav.cache.clear] cleared={}", cleared)
        return cleared

    @staticmethod
    def _parse_file_list(xml_text: str, current_path: str, base_prefix: str) -> list[dict[str, Any]]:
        ns = {"d": "DAV:"}
        root = ET.fromstring(xml_text)
        rows: list[dict[str, Any]] = []

        for resp in root.findall("d:response", ns):
            href = resp.findtext("d:href", default="", namespaces=ns)
            if not href:
                continue
            parsed = urlparse(href)
            full_path = unquote(parsed.path)
            if not full_path:
                continue

            if base_prefix and full_path.startswith(base_prefix):
                full_path = full_path[len(base_prefix) :]
                if not full_path.startswith("/"):
                    full_path = f"/{full_path}"

            path_for_match = full_path
            if path_for_match.endswith("/") and path_for_match != "/":
                path_for_match = path_for_match[:-1]

            base_for_match = current_path
            if base_for_match.endswith("/") and base_for_match != "/":
                base_for_match = base_for_match[:-1]

            if path_for_match == base_for_match:
                continue

            prop = resp.find("d:propstat/d:prop", ns)
            if prop is None:
                continue

            is_dir = prop.find("d:resourcetype/d:collection", ns) is not None
            name = unquote(path_for_match.split("/")[-1])
            if not name:
                continue

            size_text = prop.findtext("d:getcontentlength", default="0", namespaces=ns)
            try:
                size = int(size_text or 0)
            except ValueError:
                size = 0

            mod_time_raw = prop.findtext("d:getlastmodified", default="", namespaces=ns)
            mod_time = ""
            if mod_time_raw:
                try:
                    mod_time = parsedate_to_datetime(mod_time_raw).strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    mod_time = mod_time_raw

            rows.append(
                {
                    "name": name,
                    "path": path_for_match,
                    "is_dir": is_dir,
                    "size": size,
                    "mod_time": mod_time,
                }
            )

        rows.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
        return rows

    async def list_dir(self, path: str) -> list[dict[str, Any]]:
        conf = await self._get_config()
        norm_path = self._normalize_path(path)
        logger.info("[webdav.list] path={}", norm_path)

        cached = await self._get_cached_list(norm_path)
        if cached is not None:
            logger.info("[webdav.list] cache_hit path={} count={}", norm_path, len(cached))
            return cached

        body = """<?xml version=\"1.0\" encoding=\"utf-8\" ?><d:propfind xmlns:d=\"DAV:\"><d:allprop/></d:propfind>"""
        url = self._build_list_url(conf["webdav_base_url"], norm_path)
        try:
            async with self._client(conf, timeout=30.0) as client:
                res = await client.request(
                "PROPFIND",
                url,
                content=body,
                headers=self._auth_headers(conf, {"Depth": "1", "Content-Type": "application/xml"}),
                )
        except httpx.RequestError as exc:
            raise self._raise_webdav_network_error("读取目录", exc) from exc
        if res.status_code not in {200, 207}:
            raise self._raise_webdav_error("读取目录", res.status_code)
        parsed = urlparse(conf["webdav_base_url"])
        base_prefix = self._normalize_base_prefix(parsed.path)
        rows = self._parse_file_list(res.text, norm_path, base_prefix)
        await self._set_cached_list(norm_path, rows)
        logger.info("[webdav.list] success path={} count={}", norm_path, len(rows))
        return rows

    async def upload_file(self, path: str, file: UploadFile):
        conf = await self._get_config()
        norm_path = self._normalize_path(path)
        filename = (file.filename or "").strip()
        if not filename:
            raise HTTPException(status_code=400, detail="文件名为空")
        if "/" in filename or "\\" in filename:
            raise HTTPException(status_code=400, detail="文件名非法")

        target_path = f"{norm_path.rstrip('/')}/{filename}" if norm_path != "/" else f"/{filename}"
        url = self._build_url(conf["webdav_base_url"], target_path)

        chunks: list[bytes] = []
        total_size = 0
        chunk_size = 1024 * 1024
        max_upload_size = int(conf.get("webdav_max_upload_size") or 50 * 1024 * 1024)
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            total_size += len(chunk)
            if total_size > max_upload_size:
                raise HTTPException(status_code=400, detail="文件大小超限")
            chunks.append(chunk)
        payload = b"".join(chunks)
        logger.info("[webdav.upload] path={} filename={} size={}", norm_path, filename, total_size)
        try:
            async with self._client(conf, timeout=180.0) as client:
                res = await client.put(
                    url,
                    content=payload,
                    headers=self._auth_headers(conf, {"Content-Type": file.content_type or "application/octet-stream"}),
                )
        except httpx.RequestError as exc:
            raise self._raise_webdav_network_error("上传文件", exc) from exc
        if res.status_code not in {200, 201, 204}:
            raise self._raise_webdav_error("上传文件", res.status_code)
        await self._invalidate_list_cache([norm_path])

    async def create_folder(self, path: str, name: str):
        conf = await self._get_config()
        norm_path = self._normalize_path(path)
        folder_name = (name or "").strip()
        if not folder_name:
            raise HTTPException(status_code=400, detail="目录名不能为空")
        if "/" in folder_name or "\\" in folder_name:
            raise HTTPException(status_code=400, detail="目录名非法")

        target_path = f"{norm_path.rstrip('/')}/{folder_name}" if norm_path != "/" else f"/{folder_name}"
        url = self._build_url(conf["webdav_base_url"], target_path)
        logger.info("[webdav.mkdir] path={} name={}", norm_path, folder_name)

        try:
            async with self._client(conf, timeout=30.0) as client:
                res = await client.request("MKCOL", url, headers=self._auth_headers(conf))
        except httpx.RequestError as exc:
            raise self._raise_webdav_network_error("创建目录", exc) from exc
        if res.status_code not in {200, 201, 204}:
            raise self._raise_webdav_error("创建目录", res.status_code)
        await self._invalidate_list_cache([norm_path])

    async def delete_path(self, path: str):
        conf = await self._get_config()
        norm_path = self._normalize_path(path)
        url = self._build_url(conf["webdav_base_url"], norm_path)
        logger.info("[webdav.delete] path={}", norm_path)

        try:
            async with self._client(conf, timeout=30.0) as client:
                res = await client.request("DELETE", url, headers=self._auth_headers(conf))
        except httpx.RequestError as exc:
            raise self._raise_webdav_network_error("删除资源", exc) from exc
        if res.status_code not in {200, 204}:
            raise self._raise_webdav_error("删除资源", res.status_code)
        await self._invalidate_list_cache([self._parent_path(norm_path), norm_path])

    async def create_share(self, *, file_path: str, file_name: str, created_by: int, expire_hours: int | None = None) -> dict:
        conf = await self._get_config()
        norm_path = self._normalize_path(file_path)
        parent_rows = await self.list_dir(self._parent_path(norm_path))
        target = next((item for item in parent_rows if item.get("path") == norm_path), None)
        if not target or target.get("is_dir"):
            raise HTTPException(status_code=404, detail="分享目标文件不存在")
        file_name = str(target.get("name") or file_name or "")

        existing = (
            await WebDavShareLink.filter(file_path=norm_path, created_by=created_by, is_active=True)
            .order_by("-id")
            .first()
        )
        if existing and self._now_like(existing.expire_time) <= existing.expire_time:
            logger.info(
                "[webdav.share.reuse] share_id={} code={} file_path={}",
                existing.id,
                existing.code,
                existing.file_path,
            )
            data = await existing.to_dict()
            data["reused"] = True
            return data

        hours = expire_hours if expire_hours and expire_hours > 0 else int(conf.get("webdav_share_default_expire_hours") or 168)
        code = secrets.token_urlsafe(6)[:8]
        expire_time = datetime.now(timezone.utc) + timedelta(hours=hours)

        share = await WebDavShareLink.create(
            code=code,
            file_path=norm_path,
            file_name=file_name,
            expire_time=expire_time,
            is_active=True,
            created_by=created_by,
        )
        logger.info("[webdav.share.create] share_id={} code={} file_path={}", share.id, share.code, share.file_path)
        data = await share.to_dict()
        data["reused"] = False
        return data

    async def list_shares(
        self,
        *,
        created_by: int | None,
        page: int,
        page_size: int,
        include_history: bool = False,
        file_name: str | None = None,
    ) -> tuple[int, list[WebDavShareLink]]:
        q = WebDavShareLink.all()
        if created_by is not None:
            q = q.filter(created_by=created_by)
        keyword = (file_name or "").strip()
        if keyword:
            q = q.filter(file_name__icontains=keyword)
        if not include_history:
            now = datetime.now(timezone.utc)
            q = q.filter(is_active=True, expire_time__gt=now)
        q = q.order_by("-id")
        total = await q.count()
        rows = await q.offset((page - 1) * page_size).limit(page_size)
        return total, rows

    async def delete_share(self, share_id: int, created_by: int | None):
        q = WebDavShareLink.filter(id=share_id)
        if created_by is not None:
            q = q.filter(created_by=created_by)
        obj = await q.first()
        if not obj:
            raise HTTPException(status_code=404, detail="分享记录不存在")
        await obj.delete()
        logger.info("[webdav.share.delete] share_id={} created_by={}", share_id, created_by)

    async def get_share(self, code: str) -> WebDavShareLink:
        obj = await WebDavShareLink.filter(code=code).first()
        if not obj:
            logger.warning("[webdav.share.get] not_found code={}", code)
            raise HTTPException(status_code=404, detail="分享链接不存在")
        if not obj.is_active:
            logger.warning("[webdav.share.get] inactive code={} share_id={}", code, obj.id)
            raise HTTPException(status_code=410, detail="分享链接已失效")
        if self._now_like(obj.expire_time) > obj.expire_time:
            obj.is_active = False
            await obj.save()
            logger.warning("[webdav.share.get] expired code={} share_id={} expire_time={}", code, obj.id, obj.expire_time)
            raise HTTPException(status_code=410, detail="分享链接已过期")
        logger.info("[webdav.share.get] ok code={} share_id={} expire_time={}", code, obj.id, obj.expire_time)
        return obj

    async def download_stream(self, file_path: str):
        conf = await self._get_config()
        norm_path = self._normalize_path(file_path)
        url = self._build_url(conf["webdav_base_url"], norm_path)

        client = self._client(conf, timeout=180.0)
        try:
            req = client.build_request("GET", url, headers=self._auth_headers(conf))
            resp = await client.send(req, stream=True)
        except httpx.RequestError as exc:
            await client.aclose()
            raise self._raise_webdav_network_error("下载文件", exc) from exc
        if 300 <= resp.status_code < 400:
            location = resp.headers.get("location", "")
            logger.warning(
                "[webdav.download] redirect_not_followed path={} status={} location={}",
                norm_path,
                resp.status_code,
                location,
            )
            await resp.aclose()
            await client.aclose()
            raise HTTPException(status_code=502, detail="下载文件失败：WebDAV返回跳转但未能获取真实文件")
        if resp.status_code >= 400:
            await resp.aclose()
            await client.aclose()
            raise self._raise_webdav_error("下载文件", resp.status_code)

        async def iterator():
            try:
                async for chunk in resp.aiter_bytes():
                    yield chunk
            finally:
                await resp.aclose()
                await client.aclose()

        return iterator, resp.headers

    @staticmethod
    def _safe_preview_filename(file_path: str) -> str:
        name = PurePosixPath(file_path).name or "preview"
        return name.replace("\\", "_").replace("/", "_")

    async def _build_preview_cache_url(self, cache_key: str, filename: str) -> str:
        sign_data = await self.build_preview_cache_signature(cache_key=cache_key, filename=filename)
        query = urlencode({"ts": sign_data["ts"], "sig": sign_data["sig"]})
        return f"/api/v1/public/webdav/preview-cache/{cache_key}/{quote(filename)}?{query}"

    async def cache_preview_file(self, file_path: str) -> dict[str, str]:
        norm_path = self._normalize_path(file_path)
        cache_key = hashlib.sha256(norm_path.encode("utf-8")).hexdigest()[:24]
        filename = self._safe_preview_filename(norm_path)
        target_dir = os.path.join(self.PREVIEW_CACHE_DIR, cache_key)
        target_path = os.path.join(target_dir, filename)

        if os.path.exists(target_path) and os.path.getsize(target_path) > 0:
            return {
                "url_path": await self._build_preview_cache_url(cache_key, filename),
                "abs_path": target_path,
                "content_type": "application/octet-stream",
            }

        os.makedirs(target_dir, exist_ok=True)
        iterator, headers = await self.download_stream(norm_path)
        temp_path = f"{target_path}.tmp"
        try:
            with open(temp_path, "wb") as file:
                async for chunk in iterator():
                    file.write(chunk)
            os.replace(temp_path, target_path)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

        content_type = headers.get("content-type") or headers.get("Content-Type") or "application/octet-stream"
        return {
            "url_path": await self._build_preview_cache_url(cache_key, filename),
            "abs_path": target_path,
            "content_type": content_type,
        }


webdav_controller = WebDavController()
