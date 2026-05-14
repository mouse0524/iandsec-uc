from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from uuid import uuid4

from fastapi import HTTPException

from app.core.ctx import CTX_USER_ID
from app.log import logger
from app.services.skill_know.chat_service import event, skill_know_chat_service


@dataclass
class SkillKnowChatJob:
    id: str
    owner_id: int
    message: str
    conversation_id: int | None
    events: list[dict] = field(default_factory=list)
    subscribers: set[asyncio.Queue] = field(default_factory=set)
    created_at: float = field(default_factory=time.monotonic)
    completed_at: float | None = None
    done: bool = False
    error: str | None = None
    task: asyncio.Task | None = None


class SkillKnowChatJobService:
    _completed_ttl_seconds = 300
    _max_jobs = 100

    def __init__(self) -> None:
        self._jobs: dict[str, SkillKnowChatJob] = {}
        self._lock = asyncio.Lock()

    async def start(self, message: str, conversation_id: int | None = None) -> SkillKnowChatJob:
        job = SkillKnowChatJob(id=uuid4().hex, owner_id=CTX_USER_ID.get(), message=message, conversation_id=conversation_id)
        async with self._lock:
            self._cleanup_locked()
            self._jobs[job.id] = job
        job.task = asyncio.create_task(self._run(job))
        return job

    async def stream_started_job(self, message: str, conversation_id: int | None = None):
        job = await self.start(message, conversation_id)
        async for item in self.events(job.id):
            yield item

    async def events(self, job_id: str):
        job = await self._get_owned_job(job_id)
        queue: asyncio.Queue = asyncio.Queue()
        for item in job.events:
            yield item
        if job.done:
            return
        job.subscribers.add(queue)
        try:
            while True:
                item = await queue.get()
                yield item
                if item.get("type") in {"final", "job.completed"} and job.done:
                    return
        finally:
            job.subscribers.discard(queue)

    async def _get_owned_job(self, job_id: str) -> SkillKnowChatJob:
        job = self._jobs.get(job_id)
        if not job or job.owner_id != CTX_USER_ID.get():
            raise HTTPException(status_code=404, detail="Chat job not found")
        return job

    async def _run(self, job: SkillKnowChatJob) -> None:
        try:
            async for item in skill_know_chat_service.stream(job.message, conversation_id=job.conversation_id):
                await self._publish(job, item)
        except Exception as exc:
            logger.exception("[skill_know.chat_job.failed] job_id={} error={}", job.id, str(exc))
            job.error = str(exc)
            await self._publish(job, event("error", {"message": "对话生成失败，请稍后重试"}), terminal=True)
        finally:
            job.done = True
            job.completed_at = time.monotonic()
            for queue in list(job.subscribers):
                await queue.put(event("job.completed", {"job_id": job.id, "error": job.error}))
            async with self._lock:
                self._cleanup_locked()

    async def _publish(self, job: SkillKnowChatJob, item: dict, *, terminal: bool = False) -> None:
        job.events.append(item)
        if item.get("type") == "final" or terminal:
            job.done = True
            job.completed_at = time.monotonic()
        for queue in list(job.subscribers):
            await queue.put(item)

    def _cleanup_locked(self) -> None:
        now = time.monotonic()
        expired_ids = [
            job_id
            for job_id, job in self._jobs.items()
            if job.done and job.completed_at is not None and now - job.completed_at > self._completed_ttl_seconds
        ]
        for job_id in expired_ids:
            self._jobs.pop(job_id, None)

        if len(self._jobs) <= self._max_jobs:
            return

        completed_jobs = sorted(
            (job for job in self._jobs.values() if job.done),
            key=lambda item: item.completed_at or item.created_at,
        )
        while len(self._jobs) > self._max_jobs and completed_jobs:
            self._jobs.pop(completed_jobs.pop(0).id, None)


skill_know_chat_job_service = SkillKnowChatJobService()
