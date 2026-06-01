from __future__ import annotations

import asyncio
import gzip
import os
import subprocess
from datetime import datetime, timedelta

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


def test_run_once_dumps_from_mysql_container_and_uploads_to_nas():
    now = datetime(2026, 5, 26, 2, 30, 0)
    uploads = []

    def fake_run(command, stdout, stderr, check, timeout):
        assert command[:2] == ["docker", "exec"]
        assert "iandsec-uc-mysql" in command
        assert "mysqldump" in command
        assert stdout == subprocess.PIPE
        assert stderr == subprocess.PIPE
        assert check is False
        assert timeout == 60 * 60
        return subprocess.CompletedProcess(command, 0, stdout=b"CREATE TABLE demo (id int);\n", stderr=b"")

    async def fake_upload(config, filename, payload):
        uploads.append((config, filename, payload))
        return {"remote_path": f"/db/{filename}", "status_code": 201}

    service = DatabaseBackupService(now_factory=lambda: now, run_command=fake_run, upload_remote=fake_upload)

    result = run(
        service.run_once(
            config={
                "db_backup_enabled": True,
                "db_backup_directory": "/db",
                "db_backup_retention_days": 7,
                "db_backup_webdav_base_url": "https://nas.example.com/dav",
                "db_backup_webdav_username": "backup",
                "db_backup_webdav_password": "secret",
            }
        )
    )

    assert result["ok"] is True
    assert result["skipped"] is False
    assert result["remote_path"].startswith("/db/")
    assert result["filename"].endswith(".sql.gz")
    assert len(uploads) == 1
    assert uploads[0][0]["db_backup_webdav_base_url"] == "https://nas.example.com/dav"
    assert gzip.decompress(uploads[0][2]) == b"CREATE TABLE demo (id int);\n"


def test_run_once_uses_configured_mysql_container():
    def fake_run(command, stdout, stderr, check, timeout):
        assert command[4] == "custom-mysql"
        return subprocess.CompletedProcess(command, 0, stdout=b"-- dump\n", stderr=b"")

    async def fake_upload(config, filename, payload):
        return {"remote_path": f"/db/{filename}", "status_code": 201}

    service = DatabaseBackupService(run_command=fake_run, upload_remote=fake_upload)

    result = run(
        service.run_once(
            config={
                "db_backup_enabled": True,
                "db_backup_directory": "/db",
                "db_backup_mysql_container": "custom-mysql",
                "db_backup_webdav_base_url": "https://nas.example.com/dav",
                "db_backup_webdav_username": "backup",
                "db_backup_webdav_password": "secret",
            },
            force=True,
        )
    )

    assert result["ok"] is True


def test_status_uses_independent_backup_webdav_config():
    service = DatabaseBackupService()

    status = service.status(
        {
            "db_backup_directory": "/db",
            "webdav_enabled": True,
            "webdav_base_url": "https://general-webdav.example.com/dav",
            "webdav_username": "general",
            "webdav_password": "general-secret",
        }
    )

    assert status["directory_writable"] is False
    assert "webdav_password" not in status


def test_status_masks_backup_webdav_password():
    service = DatabaseBackupService()

    status = service.status(
        {
            "db_backup_directory": "/db",
            "db_backup_webdav_base_url": "https://nas.example.com/dav",
            "db_backup_webdav_username": "backup",
            "db_backup_webdav_password": "secret",
        }
    )

    assert status["directory_writable"] is True
    assert status["db_backup_webdav_password"] == "******"


def test_test_directory_rejects_relative_path():
    service = DatabaseBackupService()

    with pytest.raises(HTTPException):
        run(service.test_directory({"db_backup_directory": "relative/path"}))


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
