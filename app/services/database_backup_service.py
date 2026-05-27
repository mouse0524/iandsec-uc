from __future__ import annotations

import asyncio
import gzip
import os
import re
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Awaitable, Callable

from fastapi import HTTPException

from app.controllers.system_setting import system_setting_controller
from app.core.redis_client import execute_redis
from app.log import logger
from app.settings import settings


RedisExecutor = Callable[..., Awaitable[Any]]
RunCommand = Callable[..., subprocess.CompletedProcess]


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


class DatabaseBackupService:
    DEFAULT_DIRECTORY = os.getenv(
        "DB_BACKUP_DIRECTORY",
        os.path.join(settings.BASE_DIR, "storage", "db_backups"),
    )
    DEFAULT_RUN_AT = os.getenv("DB_BACKUP_RUN_AT", "02:30")
    DEFAULT_RETENTION_DAYS = _int_env("DB_BACKUP_RETENTION_DAYS", 7)

    def __init__(
        self,
        *,
        config_controller: Any | None = None,
        now_factory: Callable[[], datetime] | None = None,
        run_command: RunCommand | None = None,
    ) -> None:
        self.config_controller = config_controller or system_setting_controller
        self.now_factory = now_factory or datetime.now
        self.run_command = run_command or subprocess.run

    async def run_once(self, *, config: dict | None = None, force: bool = False) -> dict:
        config = self.normalize_config(config or await self.config_controller.get_full_dict())
        if not force and not config["db_backup_enabled"]:
            return {"ok": True, "skipped": True, "reason": "disabled", "enabled": False}

        directory = self.ensure_backup_directory(config["db_backup_directory"])
        now = self.now_factory()
        filename = self.build_filename(now)
        final_path = directory / filename
        temp_path = directory / f".{filename}.tmp"

        logger.info("[database_backup] start directory={} database={}", str(directory), settings.MYSQL_DATABASE)
        try:
            await asyncio.to_thread(self.dump_database, temp_path)
            os.replace(temp_path, final_path)
            deleted = self.cleanup_retention(directory, config["db_backup_retention_days"], now=now)
        except Exception:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
            logger.exception("[database_backup] failed directory={}", str(directory))
            raise

        size = final_path.stat().st_size
        logger.info("[database_backup] success path={} size={} deleted={}", str(final_path), size, deleted)
        return {
            "ok": True,
            "skipped": False,
            "path": str(final_path),
            "filename": final_path.name,
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
            directory = Path(directory_text)
            exists = directory.exists() and directory.is_dir()
            writable = self.is_writable_directory(directory) if exists else False
            latest_path = self.latest_backup(directory) if exists else None
            if latest_path:
                stat = latest_path.stat()
                latest = {
                    "filename": latest_path.name,
                    "path": str(latest_path),
                    "size": stat.st_size,
                    "created_at": datetime.fromtimestamp(stat.st_mtime).strftime(settings.DATETIME_FORMAT),
                }
        except Exception as exc:
            error = str(exc)

        return {
            **normalized,
            "directory_exists": exists,
            "directory_writable": writable,
            "latest_backup": latest,
            "error": error,
        }

    def test_directory(self, config: dict | None = None) -> dict:
        normalized = self.normalize_config(config or {})
        directory = self.ensure_backup_directory(normalized["db_backup_directory"])
        if not self.is_writable_directory(directory):
            raise HTTPException(status_code=400, detail="备份目录不可写，请检查 NAS 挂载和权限")
        usage = shutil.disk_usage(directory)
        return {
            "ok": True,
            "path": str(directory),
            "free": usage.free,
            "total": usage.total,
            "used": usage.used,
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
        return {
            "db_backup_enabled": enabled,
            "db_backup_directory": directory,
            "db_backup_run_at": run_at,
            "db_backup_retention_days": retention_days,
        }

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

    def dump_database(self, target_path: Path) -> None:
        command = [
            "mysqldump",
            f"--host={settings.MYSQL_HOST}",
            f"--port={settings.MYSQL_PORT}",
            f"--user={settings.MYSQL_USER}",
            "--single-transaction",
            "--routines",
            "--triggers",
            "--events",
            "--default-character-set=utf8mb4",
            settings.MYSQL_DATABASE,
        ]
        env = os.environ.copy()
        env["MYSQL_PWD"] = settings.MYSQL_PASSWORD

        plain_path = target_path.with_name(f"{target_path.name}.sql")
        try:
            with plain_path.open("wb") as output:
                result = self.run_command(
                    command,
                    stdout=output,
                    stderr=subprocess.PIPE,
                    env=env,
                    check=False,
                    timeout=60 * 60,
                )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=500, detail="未找到 mysqldump，请在运行环境安装 MySQL client") from exc
        except subprocess.TimeoutExpired as exc:
            raise HTTPException(status_code=500, detail="数据库备份超时") from exc
        except OSError as exc:
            raise HTTPException(status_code=500, detail=f"写入备份文件失败: {exc}") from exc
        finally:
            if "result" not in locals():
                try:
                    plain_path.unlink(missing_ok=True)
                except OSError:
                    pass

        if result.returncode != 0:
            stderr = self.decode_stderr(result.stderr)
            try:
                plain_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise HTTPException(status_code=500, detail=f"数据库备份失败: {stderr or 'mysqldump 执行失败'}")

        try:
            with plain_path.open("rb") as source, gzip.open(target_path, "wb") as output:
                shutil.copyfileobj(source, output, length=1024 * 1024)
        finally:
            try:
                plain_path.unlink(missing_ok=True)
            except OSError:
                pass

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
