from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any, Awaitable, Callable

from tortoise.expressions import Q

from app.controllers.system_setting import system_setting_controller
from app.controllers.user import user_controller
from app.core.redis_client import execute_redis
from app.log import logger
from app.models.admin import User


RedisExecutor = Callable[..., Awaitable[Any]]


class InactiveUserAutoDisableService:
    def __init__(
        self,
        *,
        config_controller: Any | None = None,
        user_model: Any | None = None,
        user_ctrl: Any | None = None,
        now_factory: Callable[[], datetime] | None = None,
    ) -> None:
        self.config_controller = config_controller or system_setting_controller
        self.user_model = user_model or User
        self.user_ctrl = user_ctrl or user_controller
        self.now_factory = now_factory or datetime.now

    async def run_once(self, *, config: dict | None = None) -> dict:
        config = config or await self.config_controller.get_public_config()
        days = self.user_ctrl.inactive_auto_disable_days(config)
        if not self.user_ctrl.inactive_auto_disable_enabled(config):
            return {"checked": 0, "disabled": 0, "days": days}

        now = self.now_factory()
        cutoff = now - timedelta(days=days)
        query = self.user_model.filter(is_active=True, is_superuser=False)
        query = query.filter(Q(last_login__lt=cutoff) | Q(last_login__isnull=True, created_at__lt=cutoff))
        candidates = await query.all()

        disabled_count = 0
        for user in candidates:
            if await self.user_ctrl.disable_if_login_inactive(user, config=config, now=now):
                disabled_count += 1

        if disabled_count:
            logger.warning(
                "[inactive_user] auto_disabled count={} checked={} days={}",
                disabled_count,
                len(candidates),
                days,
            )
        return {"checked": len(candidates), "disabled": disabled_count, "days": days}


class InactiveUserAutoDisableScheduler:
    LOCK_KEY = "inactive_user:auto_disable:lock"
    LOCK_TTL_SECONDS = 30 * 60
    INTERVAL_SECONDS = 60 * 60

    def __init__(
        self,
        *,
        service: InactiveUserAutoDisableService | None = None,
        redis_executor: RedisExecutor | None = None,
    ) -> None:
        self.service = service or InactiveUserAutoDisableService()
        self.redis_executor = redis_executor or execute_redis
        self._task: asyncio.Task | None = None
        self._stopping = asyncio.Event()
        self._local_lock = asyncio.Lock()

    def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stopping = asyncio.Event()
        self._task = asyncio.create_task(self._run_loop())
        logger.info("[inactive_user.scheduler] started")

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
            logger.info("[inactive_user.scheduler] stopped")

    async def _run_loop(self) -> None:
        while not self._stopping.is_set():
            try:
                await self.run_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.exception("[inactive_user.scheduler] run_failed error={}", str(exc))

            if await self._sleep_or_stop(self.INTERVAL_SECONDS):
                return

    async def run_once(self) -> dict | None:
        token = self._lock_token()
        acquired = await self._acquire_distributed_lock(token)
        if acquired is False:
            logger.info("[inactive_user.scheduler] skip_run lock_held")
            return None

        if acquired is None:
            if self._local_lock.locked():
                logger.info("[inactive_user.scheduler] skip_run local_lock_held")
                return None
            async with self._local_lock:
                return await self.service.run_once()

        try:
            return await self.service.run_once()
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
            logger.warning("[inactive_user.scheduler] redis_lock_unavailable fallback=local error={}", str(exc))
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
            logger.warning("[inactive_user.scheduler] release_lock_failed error={}", str(exc))

    async def _sleep_or_stop(self, seconds: int) -> bool:
        try:
            await asyncio.wait_for(self._stopping.wait(), timeout=max(1, seconds))
            return True
        except TimeoutError:
            return False

    def _lock_token(self) -> str:
        return f"{id(self)}:{datetime.now().isoformat(timespec='microseconds')}"


inactive_user_auto_disable_service = InactiveUserAutoDisableService()
inactive_user_auto_disable_scheduler = InactiveUserAutoDisableScheduler(service=inactive_user_auto_disable_service)
