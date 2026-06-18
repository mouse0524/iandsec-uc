from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta
from typing import Any, Awaitable, Callable

from app.controllers.mail import mail_controller
from app.core.redis_client import execute_redis
from app.log import logger
from app.models.admin import Ticket, User
from app.models.enums import TicketStatus


RedisExecutor = Callable[..., Awaitable[Any]]


class ChinaWorkdayCalendar:
    def __init__(self) -> None:
        try:
            from chinesedays.date_utils import is_workday
        except Exception:
            is_workday = None
        self._is_workday = is_workday

    def is_working_day(self, value: date) -> bool:
        if self._is_workday:
            return bool(self._is_workday(value))
        return value.weekday() < 5


class TicketDailyReminderService:
    REMINDER_STATUSES = [TicketStatus.FIELD_VERIFICATION, TicketStatus.PENDING_CLOSE]

    def __init__(self, *, ticket_model: Any | None = None, user_model: Any | None = None) -> None:
        self.ticket_model = ticket_model or Ticket
        self.user_model = user_model or User

    async def send_daily_reminders(self) -> dict[str, int]:
        tickets = await self.ticket_model.filter(status__in=self.REMINDER_STATUSES).order_by("status", "id")
        users = await self.user_model.filter(is_active=True).prefetch_related("roles")
        users_by_id = await self._eligible_users_by_id(users)

        sent = 0
        failed = 0
        for ticket in tickets:
            recipient = self._recipient_for_ticket(ticket, users_by_id)
            if not recipient or not getattr(recipient, "email", None):
                continue
            try:
                await mail_controller.send_ticket_status_notice(
                    ticket=ticket,
                    to_user=recipient,
                    status=ticket.status,
                    operator_name="系统定时提醒",
                )
                sent += 1
            except Exception:
                failed += 1
                logger.warning(
                    "[ticket.daily_reminder] send_failed ticket_id={} status={} to_user_id={}",
                    getattr(ticket, "id", None),
                    getattr(ticket, "status", None),
                    getattr(recipient, "id", None),
                    exc_info=True,
                )

        if tickets:
            logger.info(
                "[ticket.daily_reminder] batch_done tickets={} sent={} failed={}",
                len(tickets),
                sent,
                failed,
            )
        return {"tickets": len(tickets), "sent": sent, "failed": failed}

    async def _eligible_users_by_id(self, users: list[Any]) -> dict[int, Any]:
        result = {}
        for user in users:
            if not getattr(user, "email", None):
                continue
            result[int(user.id)] = user
        return result

    def _recipient_for_ticket(self, ticket: Any, users_by_id: dict[int, Any]) -> Any | None:
        if ticket.status in self.REMINDER_STATUSES:
            submitter_id = getattr(ticket, "submitter_id", None)
            return users_by_id.get(int(submitter_id)) if submitter_id else None
        return None


class TicketDailyReminderScheduler:
    LOCK_KEY = "ticket:daily_reminder:lock"
    LOCK_TTL_SECONDS = 6 * 60 * 60
    RUN_AT = "10:00"

    def __init__(
        self,
        *,
        service: TicketDailyReminderService | None = None,
        redis_executor: RedisExecutor | None = None,
        workday_calendar: Any | None = None,
    ) -> None:
        self.service = service or TicketDailyReminderService()
        self.redis_executor = redis_executor or execute_redis
        self.workday_calendar = workday_calendar or ChinaWorkdayCalendar()
        self._task: asyncio.Task | None = None
        self._stopping = asyncio.Event()
        self._local_lock = asyncio.Lock()

    def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stopping = asyncio.Event()
        self._task = asyncio.create_task(self._run_loop())
        logger.info("[ticket.daily_reminder.scheduler] started")

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
            logger.info("[ticket.daily_reminder.scheduler] stopped")

    async def _run_loop(self) -> None:
        while not self._stopping.is_set():
            try:
                wait_seconds = self.seconds_until_next_run(datetime.now().astimezone())
                logger.info(
                    "[ticket.daily_reminder.scheduler] next_run_in={}s run_at={}",
                    wait_seconds,
                    self.RUN_AT,
                )
                if await self._sleep_or_stop(wait_seconds):
                    return
                await self.run_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.exception("[ticket.daily_reminder.scheduler] run_failed error={}", str(exc))
                await self._sleep_or_stop(3600)

    async def run_once(self, *, now: date | datetime | None = None) -> dict[str, int] | None:
        current = now or datetime.now().astimezone()
        run_date = current.date() if isinstance(current, datetime) else current
        if not self.workday_calendar.is_working_day(run_date):
            logger.info("[ticket.daily_reminder.scheduler] skip_run non_workday date={}", run_date)
            return {"tickets": 0, "sent": 0, "failed": 0, "skipped": 1}

        token = self._lock_token()
        acquired = await self._acquire_distributed_lock(token)
        if acquired is False:
            logger.info("[ticket.daily_reminder.scheduler] skip_run lock_held")
            return None

        if acquired is None:
            if self._local_lock.locked():
                logger.info("[ticket.daily_reminder.scheduler] skip_run local_lock_held")
                return None
            async with self._local_lock:
                return await self.service.send_daily_reminders()

        try:
            return await self.service.send_daily_reminders()
        finally:
            await self._release_distributed_lock(token)

    def seconds_until_next_run(self, now: datetime) -> int:
        target = self._next_workday_target(now)
        return int((target - now).total_seconds())

    def _next_workday_target(self, now: datetime) -> datetime:
        target = now.replace(hour=10, minute=0, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        while not self.workday_calendar.is_working_day(target.date()):
            target += timedelta(days=1)
        return target

    async def _acquire_distributed_lock(self, token: str) -> bool | None:
        try:
            result = await self.redis_executor("set", self.LOCK_KEY, token, ex=self.LOCK_TTL_SECONDS, nx=True)
            return bool(result)
        except Exception as exc:
            logger.warning("[ticket.daily_reminder.scheduler] redis_lock_unavailable fallback=local error={}", str(exc))
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
            logger.warning("[ticket.daily_reminder.scheduler] release_lock_failed error={}", str(exc))

    async def _sleep_or_stop(self, seconds: int) -> bool:
        try:
            await asyncio.wait_for(self._stopping.wait(), timeout=max(1, seconds))
            return True
        except TimeoutError:
            return False

    def _lock_token(self) -> str:
        return f"{id(self)}:{datetime.now().astimezone().isoformat(timespec='microseconds')}"


ticket_daily_reminder_service = TicketDailyReminderService()
ticket_daily_reminder_scheduler = TicketDailyReminderScheduler(service=ticket_daily_reminder_service)
