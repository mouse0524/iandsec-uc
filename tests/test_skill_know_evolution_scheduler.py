from __future__ import annotations

from datetime import datetime

import pytest

from app.services.skill_know.evolution_scheduler import SkillKnowEvolutionScheduler


class FakeEvolutionService:
    def __init__(self):
        self.calls = []

    async def run_daily_eval_report(self, *, top_k: int = 8):
        self.calls.append(top_k)
        return {"top_k": top_k}


def test_next_run_seconds_uses_today_when_time_is_future():
    scheduler = SkillKnowEvolutionScheduler()
    now = datetime(2026, 5, 15, 1, 0, 0)

    seconds = scheduler.seconds_until_next_run(now, "02:10")

    assert seconds == 70 * 60


def test_next_run_seconds_rolls_to_tomorrow_when_time_passed():
    scheduler = SkillKnowEvolutionScheduler()
    now = datetime(2026, 5, 15, 3, 0, 0)

    seconds = scheduler.seconds_until_next_run(now, "02:10")

    assert seconds == 23 * 60 * 60 + 10 * 60


def test_next_run_seconds_falls_back_for_invalid_time():
    scheduler = SkillKnowEvolutionScheduler()
    now = datetime(2026, 5, 15, 1, 0, 0)

    seconds = scheduler.seconds_until_next_run(now, "bad")

    assert seconds == 60 * 60


@pytest.mark.anyio
async def test_run_once_uses_redis_lock_when_available():
    service = FakeEvolutionService()
    calls = []

    async def redis_executor(command, *args, **kwargs):
        calls.append((command, args, kwargs))
        if command == "set":
            return True
        if command == "eval":
            return 1
        return None

    scheduler = SkillKnowEvolutionScheduler(evolution_service=service, redis_executor=redis_executor)

    result = await scheduler.run_once(top_k=6)

    assert result == {"top_k": 6}
    assert service.calls == [6]
    assert calls[0][0] == "set"
    assert calls[0][2]["nx"] is True
    assert calls[1][0] == "eval"


@pytest.mark.anyio
async def test_run_once_skips_when_redis_lock_is_held():
    service = FakeEvolutionService()

    async def redis_executor(command, *args, **kwargs):
        return False if command == "set" else None

    scheduler = SkillKnowEvolutionScheduler(evolution_service=service, redis_executor=redis_executor)

    result = await scheduler.run_once(top_k=6)

    assert result is None
    assert service.calls == []


@pytest.mark.anyio
async def test_run_once_falls_back_to_local_lock_when_redis_unavailable():
    service = FakeEvolutionService()

    async def redis_executor(command, *args, **kwargs):
        raise OSError("redis down")

    scheduler = SkillKnowEvolutionScheduler(evolution_service=service, redis_executor=redis_executor)

    result = await scheduler.run_once(top_k=7)

    assert result == {"top_k": 7}
    assert service.calls == [7]
