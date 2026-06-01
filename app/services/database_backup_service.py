from __future__ import annotations

import asyncio
import gzip
import io
import os
import re
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Awaitable, Callable

import httpx
from fastapi import HTTPException

from app.controllers.system_setting import normalize_webdav_base_url
from app.controllers.system_setting import system_setting_controller
from app.core.redis_client import execute_redis
from app.log import logger
from app.settings import settings


RedisExecutor = Callable[..., Awaitable[Any]]
RunCommand = Callable[..., subprocess.CompletedProcess]
RemoteUploader = Callable[[dict, str, bytes], Awaitable[dict]]


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


class DatabaseBackupService:
    DEFAULT_DIRECTORY = os.getenv(
        "DB_BACKUP_DIRECTORY",
        "/iandsec-db-backups",
    )
    DEFAULT_RUN_AT = os.getenv("DB_BACKUP_RUN_AT", "02:30")
    DEFAULT_RETENTION_DAYS = _int_env("DB_BACKUP_RETENTION_DAYS", 7)
    DEFAULT_MYSQL_CONTAINER = os.getenv("DB_BACKUP_MYSQL_CONTAINER", "iandsec-uc-mysql")

    def __init__(
        self,
        *,
        config_controller: Any | None = None,
        now_factory: Callable[[], datetime] | None = None,
        run_command: RunCommand | None = None,
        upload_remote: RemoteUploader | None = None,
    ) -> None:
        self.config_controller = config_controller or system_setting_controller
        self.now_factory = now_factory or datetime.now
        self.run_command = run_command or subprocess.run
        self.upload_remote = upload_remote or self.upload_to_webdav

    async def run_once(self, *, config: dict | None = None, force: bool = False) -> dict:
        config = self.normalize_config(config or await self.config_controller.get_full_dict())
        if not force and not config["db_backup_enabled"]:
            return {"ok": True, "skipped": True, "reason": "disabled", "enabled": False}

        now = self.now_factory()
        filename = self.build_filename(now)

        logger.info(
            "[database_backup] start remote_dir={} database={} mysql_container={}",
            config["db_backup_directory"],
            settings.MYSQL_DATABASE,
            config["db_backup_mysql_container"],
        )
        try:
            payload = await asyncio.to_thread(self.dump_database, config["db_backup_mysql_container"])
            upload_result = await self.upload_remote(config, filename, payload)
            deleted = 0
        except Exception:
            logger.exception("[database_backup] failed remote_dir={}", config["db_backup_directory"])
            raise

        size = len(payload)
        remote_path = str(upload_result.get("remote_path") or "")
        logger.info("[database_backup] success remote_path={} size={} deleted={}", remote_path, size, deleted)
        return {
            "ok": True,
            "skipped": False,
            "path": remote_path,
            "remote_path": remote_path,
            "filename": filename,
            "size": size,
            "deleted": deleted,
            "created_at": now.strftime(settings.DATETIME_FORMAT),
        }

    def status(self, config: dict | None = None) -> dict:
        normalized = self.normalize_config(config or {})
        directory_text = normalized["db_backup_directory"]
        exists = False
        writable = False
        latest: dict | None = None
        error = ""

        try:
            exists = bool(directory_text)
            writable = bool(
                normalized.get("db_backup_webdav_base_url")
                and normalized.get("db_backup_webdav_username")
                and normalized.get("db_backup_webdav_password")
            )
        except Exception as exc:
            error = str(exc)

        result = {
            **normalized,
            "directory_exists": exists,
            "directory_writable": writable,
            "latest_backup": latest,
            "error": error,
        }
        if result.get("db_backup_webdav_password"):
            result["db_backup_webdav_password"] = "******"
        return result

    async def test_directory(self, config: dict | None = None) -> dict:
        normalized = self.normalize_config(config or {})
        self.ensure_remote_directory(normalized["db_backup_directory"])
        marker = f"write-test-{os.getpid()}-{id(self)}.txt"
        result = await self.upload_remote(normalized, marker, b"ok")
        remote_path = result.get("remote_path") or self.remote_path(normalized["db_backup_directory"], marker)
        if self.upload_remote == self.upload_to_webdav:
            await self.delete_from_webdav(normalized, remote_path)
        return {
            "ok": True,
            "path": remote_path,
            "remote_path": remote_path,
        }

    def normalize_config(self, config: dict) -> dict:
        enabled = self.as_bool(config.get("db_backup_enabled", False))
        directory = str(config.get("db_backup_directory") or self.DEFAULT_DIRECTORY).strip()
        run_at = self.normalize_run_at(config.get("db_backup_run_at") or self.DEFAULT_RUN_AT)
        retention_days = self.as_int(
            config.get("db_backup_retention_days", self.DEFAULT_RETENTION_DAYS),
            default=self.DEFAULT_RETENTION_DAYS,
            minimum=1,
            maximum=365,
        )
        mysql_container = str(config.get("db_backup_mysql_container") or self.DEFAULT_MYSQL_CONTAINER).strip()
        if not mysql_container:
            raise HTTPException(status_code=400, detail="MySQL容器名不能为空")
        webdav_base_url = str(config.get("db_backup_webdav_base_url") or "").strip()
        if webdav_base_url:
            webdav_base_url = normalize_webdav_base_url(webdav_base_url)
        return {
            "db_backup_enabled": enabled,
            "db_backup_directory": directory,
            "db_backup_run_at": run_at,
            "db_backup_retention_days": retention_days,
            "db_backup_mysql_container": mysql_container,
            "db_backup_webdav_base_url": webdav_base_url,
            "db_backup_webdav_username": str(config.get("db_backup_webdav_username") or "").strip(),
            "db_backup_webdav_password": str(config.get("db_backup_webdav_password") or ""),
        }

    def ensure_remote_directory(self, directory_text: str) -> str:
        text = str(directory_text or "").strip().replace("\\", "/")
        if not text:
            raise HTTPException(status_code=400, detail="NAS远端目录不能为空")
        if not text.startswith("/"):
            raise HTTPException(status_code=400, detail="NAS远端目录必须以 / 开头")
        if ".." in [part for part in text.split("/") if part]:
            raise HTTPException(status_code=400, detail="NAS远端目录非法")
        return "/" + text.strip("/")

    def ensure_backup_directory(self, directory_text: str) -> Path:
        directory = Path(str(directory_text or "").strip())
        if not str(directory):
            raise HTTPException(status_code=400, detail="备份目录不能为空")
        if not directory.is_absolute():
            raise HTTPException(status_code=400, detail="备份目录必须是绝对路径")
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise HTTPException(status_code=400, detail=f"备份目录不可用: {exc}") from exc
        if not directory.is_dir():
            raise HTTPException(status_code=400, detail="备份路径不是目录")
        return directory

    def dump_database(self, mysql_container: str | None = None) -> bytes:
        container = str(mysql_container or self.DEFAULT_MYSQL_CONTAINER).strip()
        if not container:
            raise HTTPException(status_code=400, detail="MySQL容器名不能为空")
        command = [
            "docker",
            "exec",
            "-e",
            f"MYSQL_PWD={settings.MYSQL_PASSWORD}",
            container,
            "mysqldump",
            "--host=127.0.0.1",
            "--port=3306",
            f"--user={settings.MYSQL_USER}",
            "--single-transaction",
            "--routines",
            "--triggers",
            "--events",
            "--default-character-set=utf8mb4",
            settings.MYSQL_DATABASE,
        ]
        try:
            result = self.run_command(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=60 * 60,
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=500, detail="未找到 docker 命令，无法进入 MySQL 容器执行备份") from exc
        except subprocess.TimeoutExpired as exc:
            raise HTTPException(status_code=500, detail="数据库备份超时") from exc
        except OSError as exc:
            raise HTTPException(status_code=500, detail=f"执行 MySQL 容器备份失败: {exc}") from exc

        if result.returncode != 0:
            stderr = self.decode_stderr(result.stderr)
            raise HTTPException(status_code=500, detail=f"数据库备份失败: {stderr or 'docker exec mysqldump 执行失败'}")

        buffer = io.BytesIO()
        with gzip.GzipFile(fileobj=buffer, mode="wb") as output:
            output.write(result.stdout or b"")
        return buffer.getvalue()

    async def upload_to_webdav(self, config: dict, filename: str, payload: bytes) -> dict:
        if not config.get("db_backup_webdav_base_url"):
            raise HTTPException(status_code=400, detail="备份 NAS 地址未配置")
        if not config.get("db_backup_webdav_username") or not config.get("db_backup_webdav_password"):
            raise HTTPException(status_code=400, detail="备份 NAS 账号或密码未配置")

        remote_path = self.remote_path(config["db_backup_directory"], filename)
        await self.ensure_webdav_directory(config, config["db_backup_directory"])
        url = self.webdav_url(config["db_backup_webdav_base_url"], remote_path)
        try:
            async with httpx.AsyncClient(timeout=60 * 60, follow_redirects=True) as client:
                response = await client.put(
                    url,
                    content=payload,
                    auth=(config["db_backup_webdav_username"], config["db_backup_webdav_password"]),
                    headers={"Content-Type": "application/gzip"},
                )
        except httpx.RequestError as exc:
            raise HTTPException(status_code=502, detail=f"上传 NAS 远端失败: {exc}") from exc
        if response.status_code == 405:
            raise HTTPException(status_code=502, detail="上传 NAS 远端失败：当前备份地址或目录不支持文件上传，请确认备份地址指向 WebDAV 根目录，NAS远端目录填写可写目录")
        if response.status_code not in {200, 201, 204}:
            raise HTTPException(status_code=502, detail=f"上传 NAS 远端失败，状态码 {response.status_code}")
        return {"remote_path": remote_path, "status_code": response.status_code}

    async def ensure_webdav_directory(self, config: dict, directory_text: str) -> None:
        directory = self.ensure_remote_directory(directory_text)
        parts = [part for part in directory.strip("/").split("/") if part]
        current = ""
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                for part in parts:
                    current = f"{current}/{part}"
                    response = await client.request(
                        "MKCOL",
                        self.webdav_url(config["db_backup_webdav_base_url"], current),
                        auth=(config["db_backup_webdav_username"], config["db_backup_webdav_password"]),
                    )
                    if response.status_code not in {200, 201, 204, 405}:
                        raise HTTPException(
                            status_code=502,
                            detail=f"创建 NAS 远端目录失败，状态码 {response.status_code}",
                        )
        except httpx.RequestError as exc:
            raise HTTPException(status_code=502, detail=f"创建 NAS 远端目录失败: {exc}") from exc

    async def delete_from_webdav(self, config: dict, remote_path: str) -> None:
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.delete(
                    self.webdav_url(config["db_backup_webdav_base_url"], remote_path),
                    auth=(config["db_backup_webdav_username"], config["db_backup_webdav_password"]),
                )
        except httpx.RequestError:
            logger.warning("[database_backup] cleanup_test_file_failed path={}", remote_path)
            return
        if response.status_code not in {200, 202, 204, 404}:
            logger.warning(
                "[database_backup] cleanup_test_file_failed path={} status={}",
                remote_path,
                response.status_code,
            )

    def remote_path(self, directory_text: str, filename: str) -> str:
        directory = self.ensure_remote_directory(directory_text)
        clean_name = str(filename or "").strip()
        if not clean_name or "/" in clean_name or "\\" in clean_name:
            raise HTTPException(status_code=400, detail="备份文件名非法")
        return f"{directory.rstrip('/')}/{clean_name}"

    def webdav_url(self, base_url: str, remote_path: str) -> str:
        from urllib.parse import quote

        base = normalize_webdav_base_url(base_url)
        return f"{base}{quote(remote_path, safe='/')}"

    def cleanup_retention(self, directory: Path, retention_days: int, *, now: datetime | None = None) -> int:
        cutoff = (now or self.now_factory()) - timedelta(days=retention_days)
        deleted = 0
        for path in directory.glob("*.sql.gz"):
            if not path.is_file():
                continue
            if datetime.fromtimestamp(path.stat().st_mtime) >= cutoff:
                continue
            try:
                path.unlink()
                deleted += 1
            except OSError as exc:
                logger.warning("[database_backup] cleanup_failed path={} error={}", str(path), str(exc))
        return deleted

    def latest_backup(self, directory: Path) -> Path | None:
        backups = [path for path in directory.glob("*.sql.gz") if path.is_file()]
        if not backups:
            return None
        return max(backups, key=lambda path: path.stat().st_mtime)

    def is_writable_directory(self, directory: Path) -> bool:
        if not directory.exists() or not directory.is_dir():
            return False
        marker = directory / f".write-test-{os.getpid()}-{id(self)}"
        try:
            marker.write_text("ok", encoding="utf-8")
            marker.unlink(missing_ok=True)
            return True
        except OSError:
            return False

    def build_filename(self, now: datetime) -> str:
        database = re.sub(r"[^A-Za-z0-9_.-]+", "_", settings.MYSQL_DATABASE).strip("._") or "database"
        return f"{database}_{now.strftime('%Y%m%d_%H%M%S')}.sql.gz"

    def normalize_run_at(self, value: Any) -> str:
        try:
            hour_text, minute_text = str(value).strip().split(":", 1)
            hour = int(hour_text)
            minute = int(minute_text)
            if hour < 0 or hour > 23 or minute < 0 or minute > 59:
                raise ValueError("run_at out of range")
        except Exception:
            return self.DEFAULT_RUN_AT
        return f"{hour:02d}:{minute:02d}"

    def as_bool(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on", "enabled"}

    def as_int(self, value: Any, *, default: int, minimum: int, maximum: int) -> int:
        try:
            parsed = int(value)
        except Exception:
            return default
        return min(maximum, max(minimum, parsed))

    def decode_stderr(self, value: Any) -> str:
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace").strip()
        return str(value or "").strip()


class DatabaseBackupScheduler:
    LOCK_KEY = "database_backup:daily:lock"
    LOCK_TTL_SECONDS = 6 * 60 * 60

    def __init__(
        self,
        *,
        service: DatabaseBackupService | None = None,
        config_controller: Any | None = None,
        redis_executor: RedisExecutor | None = None,
    ) -> None:
        self.service = service or DatabaseBackupService()
        self.config_controller = config_controller or system_setting_controller
        self.redis_executor = redis_executor or execute_redis
        self._task: asyncio.Task | None = None
        self._stopping = asyncio.Event()
        self._local_lock = asyncio.Lock()

    def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stopping = asyncio.Event()
        self._task = asyncio.create_task(self._run_loop())
        logger.info("[database_backup.scheduler] started")

    async def stop(self) -> None:
        self._stopping.set()
        if not self._task:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        finally:
            self._task = None
            logger.info("[database_backup.scheduler] stopped")

    async def _run_loop(self) -> None:
        while not self._stopping.is_set():
            try:
                config = self.service.normalize_config(await self.config_controller.get_full_dict())
                if not config["db_backup_enabled"]:
                    await self._sleep_or_stop(3600)
                    continue

                wait_seconds = self.seconds_until_next_run(datetime.now().astimezone(), config["db_backup_run_at"])
                logger.info(
                    "[database_backup.scheduler] next_run_in={}s run_at={}",
                    wait_seconds,
                    config["db_backup_run_at"],
                )
                if await self._sleep_or_stop(wait_seconds):
                    return
                await self.run_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.exception("[database_backup.scheduler] run_failed error={}", str(exc))
                await self._sleep_or_stop(3600)

    async def run_once(self, *, config: dict | None = None, force: bool = False) -> dict | None:
        token = self._lock_token()
        acquired = await self._acquire_distributed_lock(token)
        if acquired is False:
            logger.info("[database_backup.scheduler] skip_run lock_held")
            return None

        if acquired is None:
            if self._local_lock.locked():
                logger.info("[database_backup.scheduler] skip_run local_lock_held")
                return None
            async with self._local_lock:
                return await self.service.run_once(config=config, force=force)

        try:
            return await self.service.run_once(config=config, force=force)
        finally:
            await self._release_distributed_lock(token)

    async def _acquire_distributed_lock(self, token: str) -> bool | None:
        try:
            result = await self.redis_executor(
                "set",
                self.LOCK_KEY,
                token,
                ex=self.LOCK_TTL_SECONDS,
                nx=True,
            )
            return bool(result)
        except Exception as exc:
            logger.warning("[database_backup.scheduler] redis_lock_unavailable fallback=local error={}", str(exc))
            return None

    async def _release_distributed_lock(self, token: str) -> None:
        script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        end
        return 0
        """
        try:
            await self.redis_executor("eval", script, 1, self.LOCK_KEY, token)
        except Exception as exc:
            logger.warning("[database_backup.scheduler] release_lock_failed error={}", str(exc))

    async def _sleep_or_stop(self, seconds: int) -> bool:
        try:
            await asyncio.wait_for(self._stopping.wait(), timeout=max(1, seconds))
            return True
        except TimeoutError:
            return False

    def seconds_until_next_run(self, now: datetime, run_at: str) -> int:
        normalized = self.service.normalize_run_at(run_at)
        hour_text, minute_text = normalized.split(":", 1)
        target = now.replace(hour=int(hour_text), minute=int(minute_text), second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        return int((target - now).total_seconds())

    def _lock_token(self) -> str:
        return f"{id(self)}:{datetime.now().astimezone().isoformat(timespec='microseconds')}"


database_backup_service = DatabaseBackupService()
database_backup_scheduler = DatabaseBackupScheduler(service=database_backup_service)
