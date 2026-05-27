from __future__ import annotations

import asyncio
import gzip
import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.services.database_backup_service import DatabaseBackupScheduler, DatabaseBackupService


def run(awaitable):
    return asyncio.run(awaitable)


def test_run_once_skips_when_disabled(tmp_path):
    service = DatabaseBackupService()

    result = run(
        service.run_once(
            config={
                "db_backup_enabled": False,
                "db_backup_directory": str(tmp_path),
            }
        )
    )

    assert result == {"ok": True, "skipped": True, "reason": "disabled", "enabled": False}


def test_run_once_creates_gzip_backup_and_cleans_old_files(tmp_path):
    now = datetime(2026, 5, 26, 2, 30, 0)
    old_backup = tmp_path / "old.sql.gz"
    old_backup.write_bytes(b"old")
    old_time = (now - timedelta(days=10)).timestamp()
    os.utime(old_backup, (old_time, old_time))

    def fake_run(command, stdout, stderr, env, check, timeout):
        stdout.write(b"CREATE TABLE demo (id int);\n")
        assert command[0] == "mysqldump"
        assert "MYSQL_PWD" in env
        assert stderr == subprocess.PIPE
        assert check is False
        assert timeout == 60 * 60
        return subprocess.CompletedProcess(command, 0, stderr=b"")

    service = DatabaseBackupService(now_factory=lambda: now, run_command=fake_run)

    result = run(
        service.run_once(
            config={
                "db_backup_enabled": True,
                "db_backup_directory": str(tmp_path),
                "db_backup_retention_days": 7,
            }
        )
    )

    backup_path = Path(result["path"])
    assert result["ok"] is True
    assert result["skipped"] is False
    assert result["deleted"] == 1
    assert backup_path.exists()
    assert old_backup.exists() is False
    with gzip.open(backup_path, "rb") as f:
        assert f.read() == b"CREATE TABLE demo (id int);\n"


def test_test_directory_rejects_relative_path():
    service = DatabaseBackupService()

    with pytest.raises(HTTPException):
        service.test_directory({"db_backup_directory": "relative/path"})


def test_scheduler_seconds_until_next_run():
    scheduler = DatabaseBackupScheduler()
    now = datetime(2026, 5, 26, 1, 0, 0)

    assert scheduler.seconds_until_next_run(now, "02:30") == 90 * 60
    assert scheduler.seconds_until_next_run(now.replace(hour=3), "02:30") == 23 * 60 * 60 + 30 * 60


@pytest.mark.anyio
async def test_scheduler_run_once_passes_force_and_config_to_service():
    calls = []

    class FakeService(DatabaseBackupService):
        async def run_once(self, *, config=None, force=False):
            calls.append((config, force))
            return {"ok": True, "forced": force}

    async def redis_executor(command, *args, **kwargs):
        if command == "set":
            return True
        if command == "eval":
            return 1
        return None

    scheduler = DatabaseBackupScheduler(service=FakeService(), redis_executor=redis_executor)
    config = {"db_backup_directory": "/tmp/nas"}

    result = await scheduler.run_once(config=config, force=True)

    assert result == {"ok": True, "forced": True}
    assert calls == [(config, True)]


@pytest.mark.anyio
async def test_scheduler_run_once_uses_redis_lock_when_available(tmp_path):
    calls = []

    class FakeService(DatabaseBackupService):
        async def run_once(self, *, config=None, force=False):
            calls.append("run")
            return {"ok": True}

    redis_calls = []

    async def redis_executor(command, *args, **kwargs):
        redis_calls.append((command, args, kwargs))
        if command == "set":
            return True
        if command == "eval":
            return 1
        return None

    scheduler = DatabaseBackupScheduler(service=FakeService(), redis_executor=redis_executor)

    result = await scheduler.run_once()

    assert result == {"ok": True}
    assert calls == ["run"]
    assert redis_calls[0][0] == "set"
    assert redis_calls[0][2]["nx"] is True
    assert redis_calls[1][0] == "eval"


@pytest.mark.anyio
async def test_scheduler_run_once_skips_when_lock_is_held():
    class FakeService(DatabaseBackupService):
        async def run_once(self, *, config=None, force=False):
            raise AssertionError("should not run")

    async def redis_executor(command, *args, **kwargs):
        return False if command == "set" else None

    scheduler = DatabaseBackupScheduler(service=FakeService(), redis_executor=redis_executor)

    assert await scheduler.run_once() is None
