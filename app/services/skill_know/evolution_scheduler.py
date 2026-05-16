from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any, Awaitable, Callable

from app.core.redis_client import execute_redis
from app.log import logger
from app.services.skill_know.config_service import skill_know_config_service
from app.services.skill_know.evolution_service import skill_know_evolution_service


RedisExecutor = Callable[..., Awaitable[Any]]


class SkillKnowEvolutionScheduler:
    LOCK_KEY = "skill_know:evolution:daily_eval:lock"
    LOCK_TTL_SECONDS = 6 * 60 * 60

    def __init__(
        self,
        *,
        config_service: Any | None = None,
        evolution_service: Any | None = None,
        redis_executor: RedisExecutor | None = None,
    ) -> None:
        self.config_service = config_service or skill_know_config_service
        self.evolution_service = evolution_service or skill_know_evolution_service
        self.redis_executor = redis_executor or execute_redis
        self._task: asyncio.Task | None = None
        self._stopping = asyncio.Event()
        self._local_lock = asyncio.Lock()

    def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stopping = asyncio.Event()
        self._task = asyncio.create_task(self._run_loop())
        logger.info("[skill_know.evolution.scheduler] started")

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
            logger.info("[skill_know.evolution.scheduler] stopped")

    async def _run_loop(self) -> None:
        while not self._stopping.is_set():
            try:
                enabled = await self.config_service.get("evolution_daily_eval_enabled", True)
                if not self._as_bool(enabled):
                    await self._sleep_or_stop(3600)
                    continue

                run_at = await self.config_service.get("evolution_daily_eval_time", "02:10")
                wait_seconds = self.seconds_until_next_run(datetime.now().astimezone(), str(run_at or "02:10"))
                logger.info(
                    "[skill_know.evolution.scheduler] next_run_in={}s run_at={}",
                    wait_seconds,
                    run_at,
                )
                if await self._sleep_or_stop(wait_seconds):
                    return

                top_k = await self.config_service.get("evolution_daily_eval_top_k", 8)
                await self.run_once(top_k=self._as_top_k(top_k))
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.exception("[skill_know.evolution.scheduler] run_failed error={}", str(exc))
                await self._sleep_or_stop(3600)

    async def run_once(self, *, top_k: int = 8) -> dict | None:
        lock_token = self._lock_token()
        acquired = await self._acquire_distributed_lock(lock_token)
        if acquired is False:
            logger.info("[skill_know.evolution.scheduler] skip_run lock_held")
            return None

        if acquired is None:
            if self._local_lock.locked():
                logger.info("[skill_know.evolution.scheduler] skip_run local_lock_held")
                return None
            async with self._local_lock:
                return await self.evolution_service.run_daily_eval_report(top_k=top_k)

        try:
            return await self.evolution_service.run_daily_eval_report(top_k=top_k)
        finally:
            await self._release_distributed_lock(lock_token)

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
            logger.warning(
                "[skill_know.evolution.scheduler] redis_lock_unavailable fallback=local error={}",
                str(exc),
            )
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
            logger.warning("[skill_know.evolution.scheduler] release_lock_failed error={}", str(exc))

    async def _sleep_or_stop(self, seconds: int) -> bool:
        try:
            await asyncio.wait_for(self._stopping.wait(), timeout=max(1, seconds))
            return True
        except TimeoutError:
            return False

    def seconds_until_next_run(self, now: datetime, run_at: str) -> int:
        try:
            hour_text, minute_text = str(run_at).strip().split(":", 1)
            hour = int(hour_text)
            minute = int(minute_text)
            if hour < 0 or hour > 23 or minute < 0 or minute > 59:
                raise ValueError("run_at out of range")
        except Exception:
            return 3600

        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        return int((target - now).total_seconds())

    def _lock_token(self) -> str:
        return f"{id(self)}:{datetime.now().astimezone().isoformat(timespec='microseconds')}"

    def _as_bool(self, value) -> bool:
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() not in {"0", "false", "no", "off", "disabled"}

    def _as_top_k(self, value) -> int:
        try:
            parsed = int(value)
        except Exception:
            return 8
        return min(20, max(1, parsed))


skill_know_evolution_scheduler = SkillKnowEvolutionScheduler()
