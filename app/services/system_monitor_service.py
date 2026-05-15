from __future__ import annotations

import os
import platform
import shutil
import time
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from tortoise import Tortoise

from app.core.redis_client import execute_redis
from app.services.skill_know.chroma_store import skill_know_chroma_store
from app.settings import settings


class SystemMonitorService:
    PROCESS_STARTED_AT = time.time()
    REDIS_SAFE_CLEAR_PATTERNS = (
        "stats:*",
        "user:basic:*",
        "perm:*",
        "role:dict:*",
        "dept:dict:*",
        "notice:inbox:*",
        "notice:unread:*",
        "webdav:list:*",
        "config:public:*",
        "skill_know:config:*",
        "skill_know:prompt:*",
        "skill_know:prompts:list:*",
        "ticket:prefill:*",
        "monitor:*",
    )

    def _bytes(self, value: Any) -> int:
        try:
            return int(value or 0)
        except Exception:
            return 0

    def _percent(self, used: int, total: int) -> float:
        return round(used / total * 100, 2) if total else 0.0

    async def _cached(self, key: str, ttl_seconds: int, loader):
        try:
            cached = await execute_redis("get", key)
            if cached:
                return json.loads(cached)
        except Exception:
            pass
        data = await loader()
        try:
            await execute_redis("setex", key, ttl_seconds, json.dumps(data, ensure_ascii=False))
        except Exception:
            pass
        return data

    async def overview(self) -> dict[str, Any]:
        async def load():
            return {
                "generated_at": datetime.now().strftime(settings.DATETIME_FORMAT),
                "system": await self.system_resources(),
                "mysql": await self.mysql_status(),
                "redis": await self.redis_status(),
                "chroma": await self.chroma_status(),
            }

        return await self._cached("monitor:overview:v1", 5, load)

    async def system_resources(self) -> dict[str, Any]:
        async def load():
            return await self._system_resources_uncached()

        return await self._cached("monitor:resources:v1", 5, load)

    async def _system_resources_uncached(self) -> dict[str, Any]:
        disk = shutil.disk_usage(settings.BASE_DIR)
        data: dict[str, Any] = {
            "hostname": platform.node(),
            "platform": platform.platform(),
            "python": platform.python_version(),
            "base_dir": settings.BASE_DIR,
            "disk": {
                "total": disk.total,
                "used": disk.used,
                "free": disk.free,
                "percent": self._percent(disk.used, disk.total),
            },
            "process": {
                "pid": os.getpid(),
                "uptime_seconds": int(time.time() - self.PROCESS_STARTED_AT),
            },
            "psutil_available": False,
        }
        try:
            import psutil
        except Exception:
            return data

        virtual_memory = psutil.virtual_memory()
        cpu_percent = psutil.cpu_percent(interval=0.05)
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        process_uptime = max(0, int(time.time() - process.create_time()))
        data.update({
            "psutil_available": True,
            "cpu": {
                "percent": cpu_percent,
                "logical_count": psutil.cpu_count(logical=True),
                "physical_count": psutil.cpu_count(logical=False),
            },
            "memory": {
                "total": virtual_memory.total,
                "available": virtual_memory.available,
                "used": virtual_memory.used,
                "percent": virtual_memory.percent,
            },
            "process": {
                **data["process"],
                "uptime_seconds": process_uptime,
                "memory_rss": memory_info.rss,
                "memory_vms": memory_info.vms,
                "cpu_percent": process.cpu_percent(interval=0.0),
                "threads": process.num_threads(),
            },
        })
        return data

    async def mysql_status(self) -> dict[str, Any]:
        async def load():
            return await self._mysql_status_uncached()

        return await self._cached("monitor:mysql:v1", 10, load)

    async def _mysql_status_uncached(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "host": settings.MYSQL_HOST,
            "port": settings.MYSQL_PORT,
            "database": settings.MYSQL_DATABASE,
            "status": "unknown",
        }
        try:
            conn = Tortoise.get_connection("mysql")
            version_rows = await conn.execute_query_dict("SELECT VERSION() AS version")
            status_rows = await conn.execute_query_dict("SHOW GLOBAL STATUS WHERE Variable_name IN ('Threads_connected','Threads_running','Max_used_connections','Uptime','Questions','Slow_queries')")
            size_rows = await conn.execute_query_dict(
                "SELECT COALESCE(SUM(data_length + index_length), 0) AS size_bytes "
                "FROM information_schema.TABLES WHERE table_schema = DATABASE()"
            )
            data.update({
                "status": "ok",
                "version": version_rows[0].get("version") if version_rows else "",
                "database_size": self._bytes(size_rows[0].get("size_bytes") if size_rows else 0),
                "metrics": {row.get("Variable_name"): self._bytes(row.get("Value")) for row in status_rows},
            })
        except Exception as exc:
            data.update({"status": "error", "error": str(exc)})
        return data

    async def redis_status(self) -> dict[str, Any]:
        async def load():
            return await self._redis_status_uncached()

        return await self._cached("monitor:redis:v1", 5, load)

    async def _redis_status_uncached(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "host": settings.REDIS_HOST,
            "port": settings.REDIS_PORT,
            "db": settings.REDIS_DB,
            "status": "unknown",
        }
        try:
            info = await execute_redis("info")
            db_size = await execute_redis("dbsize")
            data.update({
                "status": "ok",
                "db_size": self._bytes(db_size),
                "version": info.get("redis_version"),
                "uptime_seconds": self._bytes(info.get("uptime_in_seconds")),
                "used_memory": self._bytes(info.get("used_memory")),
                "used_memory_human": info.get("used_memory_human"),
                "connected_clients": self._bytes(info.get("connected_clients")),
                "hit_rate": self._redis_hit_rate(info),
                "keyspace": {key: value for key, value in info.items() if str(key).startswith("db")},
            })
        except Exception as exc:
            data.update({"status": "error", "error": str(exc)})
        return data

    def _redis_hit_rate(self, info: dict[str, Any]) -> float:
        hits = self._bytes(info.get("keyspace_hits"))
        misses = self._bytes(info.get("keyspace_misses"))
        total = hits + misses
        return round(hits / total * 100, 2) if total else 0.0

    async def clear_redis(self, *, confirm: bool = False) -> dict[str, Any]:
        if not confirm:
            raise HTTPException(status_code=400, detail="清空 Redis 需要 confirm=true")
        before = self._bytes(await execute_redis("dbsize"))
        cleared = 0
        for pattern in self.REDIS_SAFE_CLEAR_PATTERNS:
            cursor = 0
            while True:
                cursor, keys = await execute_redis("scan", cursor=cursor, match=pattern, count=500)
                if keys:
                    cleared += self._bytes(await execute_redis("delete", *keys))
                if int(cursor or 0) == 0:
                    break
        after = self._bytes(await execute_redis("dbsize"))
        return {
            "cleared": cleared,
            "remaining": after,
            "before": before,
            "db": settings.REDIS_DB,
            "patterns": list(self.REDIS_SAFE_CLEAR_PATTERNS),
        }

    async def chroma_status(self) -> dict[str, Any]:
        async def load():
            return await self._chroma_status_uncached()

        return await self._cached("monitor:chroma:v1", 10, load)

    async def _chroma_status_uncached(self) -> dict[str, Any]:
        data = await skill_know_chroma_store.diagnose()
        persist_dir = Path(str(data.get("persist_dir") or ""))
        if persist_dir.exists():
            data["persist_size"] = sum(path.stat().st_size for path in persist_dir.rglob("*") if path.is_file())
        else:
            data["persist_size"] = 0
        return data


system_monitor_service = SystemMonitorService()
