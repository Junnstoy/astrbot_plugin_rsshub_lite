"""Session-scoped push job queue.

The queue keeps push delivery serialized per target session while allowing
different sessions to send concurrently. Jobs are in-memory runtime jobs; push
history remains the durable audit log.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from itertools import count
from threading import RLock
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass
class PushJob:
    """Runtime state for one session push job."""

    job_id: str
    session_id: str
    description: str = ""
    feed_id: int | None = None
    feed_title: str = ""
    sub_id: int | None = None
    status: str = "queued"
    queued_before: int = 0
    cancel_requested: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str = ""


@dataclass(frozen=True)
class PushJobResult(Generic[T]):
    """Result returned after a queued push job finishes."""

    job_id: str
    session_id: str
    ok: bool
    cancelled: bool = False
    error: str = ""
    value: T | None = None


@dataclass(frozen=True)
class StopPushJobResult:
    """Result returned by a stop request."""

    stopped: bool
    session_id: str
    job_id: str | None = None
    queued_count: int = 0
    message: str = ""


@dataclass
class _SessionQueueState:
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    current_job: PushJob | None = None
    current_task: asyncio.Task | None = None
    queued_count: int = 0
    jobs: dict[str, PushJob] = field(default_factory=dict)


class SessionPushQueue:
    """Serialize push jobs per session and allow cancelling the active job."""

    def __init__(self) -> None:
        self._states: dict[str, _SessionQueueState] = {}
        self._counter = count(1)
        self._state_guard = RLock()

    def _next_job_id(self) -> str:
        return f"rss-{next(self._counter):06d}"

    def _state_for(self, session_id: str) -> _SessionQueueState:
        with self._state_guard:
            state = self._states.get(session_id)
            if state is None:
                state = _SessionQueueState()
                self._states[session_id] = state
            return state

    def _cleanup_state_if_idle(
        self, session_id: str, state: _SessionQueueState
    ) -> None:
        """Remove per-session state when there is no active or queued work."""
        if (
            state.queued_count == 0
            and state.current_job is None
            and state.current_task is None
        ):
            self._states.pop(session_id, None)

    async def enqueue(
        self,
        session_id: str,
        work: Callable[[PushJob], Awaitable[T]],
        *,
        description: str = "",
        feed_id: int | None = None,
        feed_title: str = "",
        sub_id: int | None = None,
    ) -> PushJobResult[T]:
        """Queue a push job for a session and wait for its result."""
        state = self._state_for(session_id)
        with self._state_guard:
            job = PushJob(
                job_id=self._next_job_id(),
                session_id=session_id,
                description=description,
                feed_id=feed_id,
                feed_title=feed_title,
                sub_id=sub_id,
                queued_before=state.queued_count,
            )
            state.queued_count += 1
            state.jobs[job.job_id] = job
        try:
            async with state.lock:
                with self._state_guard:
                    if job.status == "queued":
                        state.queued_count = max(0, state.queued_count - 1)
                    if job.cancel_requested:
                        job.status = "cancelled"
                        job.completed_at = datetime.now(timezone.utc)
                        return PushJobResult(
                            job_id=job.job_id,
                            session_id=session_id,
                            ok=False,
                            cancelled=True,
                            error="job cancelled",
                        )
                    job.status = "running"
                    job.started_at = datetime.now(timezone.utc)

                task = asyncio.create_task(work(job))
                with self._state_guard:
                    state.current_job = job
                    state.current_task = task
                try:
                    value = await task
                except asyncio.CancelledError:
                    job.status = "cancelled"
                    job.completed_at = datetime.now(timezone.utc)
                    return PushJobResult(
                        job_id=job.job_id,
                        session_id=session_id,
                        ok=False,
                        cancelled=True,
                        error="job cancelled",
                    )
                except Exception as ex:
                    job.status = "failed"
                    job.error = str(ex)
                    job.completed_at = datetime.now(timezone.utc)
                    return PushJobResult(
                        job_id=job.job_id,
                        session_id=session_id,
                        ok=False,
                        error=str(ex),
                    )

                job.status = "completed"
                job.completed_at = datetime.now(timezone.utc)
                return PushJobResult(
                    job_id=job.job_id,
                    session_id=session_id,
                    ok=True,
                    value=value,
                )
        finally:
            with self._state_guard:
                if state.current_job is job:
                    state.current_job = None
                    state.current_task = None
                state.jobs.pop(job.job_id, None)
                self._cleanup_state_if_idle(session_id, state)

    def stop_current(self, session_id: str) -> StopPushJobResult:
        """Cancel the currently running push job for a session.

        The queue is single-process and in-memory. This method uses a short
        synchronous guard because command handlers call it without awaiting.
        It may observe a just-finished task before `enqueue` has run its final
        cleanup; in that case it reports that no running job exists and lets
        the enqueue finalizer remove idle state.
        """
        with self._state_guard:
            state = self._states.get(session_id)
            if state is None or state.current_job is None:
                if state is not None:
                    self._cleanup_state_if_idle(session_id, state)
                return StopPushJobResult(
                    stopped=False,
                    session_id=session_id,
                    message="当前会话没有正在运行的 RSS 推送任务",
                )

            job = state.current_job
            task = state.current_task
            if task is None or task.done():
                self._cleanup_state_if_idle(session_id, state)
                return StopPushJobResult(
                    stopped=False,
                    session_id=session_id,
                    queued_count=state.queued_count,
                    message="当前会话没有正在运行的 RSS 推送任务",
                )

            job.cancel_requested = True
            task.cancel()
            return StopPushJobResult(
                stopped=True,
                session_id=session_id,
                job_id=job.job_id,
                queued_count=state.queued_count,
                message=f"已请求停止 RSS 推送任务 {job.job_id}",
            )

    def get_current_job(self, session_id: str) -> PushJob | None:
        """Return the currently running job for a session, if any."""
        with self._state_guard:
            state = self._states.get(session_id)
            return state.current_job if state else None

    def get_jobs(self, session_id: str) -> list[PushJob]:
        """Return current and queued jobs for a session."""
        with self._state_guard:
            state = self._states.get(session_id)
            if not state:
                return []
            jobs = list(state.jobs.values())
            jobs.sort(
                key=lambda job: (
                    0 if job.status == "running" else 1,
                    job.created_at,
                )
            )
            return jobs

    def get_queued_count(self, session_id: str) -> int:
        """Return the number of queued jobs for a session."""
        with self._state_guard:
            state = self._states.get(session_id)
            return state.queued_count if state else 0

    def stop_by_job_id(self, session_id: str, job_id: str) -> StopPushJobResult:
        """Cancel a specific job by job_id for a session."""
        with self._state_guard:
            state = self._states.get(session_id)
            if state is None:
                return StopPushJobResult(
                    stopped=False,
                    session_id=session_id,
                    message=f"当前会话没有任务: {job_id}",
                )
            job = state.jobs.get(job_id)
            if job is None:
                return StopPushJobResult(
                    stopped=False,
                    session_id=session_id,
                    queued_count=state.queued_count,
                    message=f"未找到任务: {job_id}",
                )

            if job.status == "queued":
                if not job.cancel_requested:
                    job.cancel_requested = True
                    return StopPushJobResult(
                        stopped=True,
                        session_id=session_id,
                        job_id=job.job_id,
                        queued_count=state.queued_count,
                        message=f"已标记停止排队任务 {job.job_id}",
                    )
                return StopPushJobResult(
                    stopped=False,
                    session_id=session_id,
                    job_id=job.job_id,
                    queued_count=state.queued_count,
                    message=f"任务 {job.job_id} 已在停止中",
                )

            if job.status != "running":
                return StopPushJobResult(
                    stopped=False,
                    session_id=session_id,
                    job_id=job.job_id,
                    queued_count=state.queued_count,
                    message=f"任务 {job.job_id} 当前状态为 {job.status}，无法停止",
                )

            task = state.current_task
            if task is None or task.done():
                self._cleanup_state_if_idle(session_id, state)
                return StopPushJobResult(
                    stopped=False,
                    session_id=session_id,
                    job_id=job.job_id,
                    queued_count=state.queued_count,
                    message=f"任务 {job.job_id} 不在运行中",
                )
            job.cancel_requested = True
            task.cancel()
            return StopPushJobResult(
                stopped=True,
                session_id=session_id,
                job_id=job.job_id,
                queued_count=state.queued_count,
                message=f"已请求停止 RSS 推送任务 {job.job_id}",
            )

    def stop_by_feed_id(self, session_id: str, feed_id: int) -> StopPushJobResult:
        """Cancel the first matched job by feed_id."""
        with self._state_guard:
            state = self._states.get(session_id)
            if state is None:
                return StopPushJobResult(
                    stopped=False,
                    session_id=session_id,
                    message=f"当前会话没有任务: feed_id={feed_id}",
                )
            candidates = sorted(
                [job for job in state.jobs.values() if job.feed_id == feed_id],
                key=lambda job: (
                    0 if job.status == "running" else 1,
                    job.created_at,
                ),
            )
            if not candidates:
                return StopPushJobResult(
                    stopped=False,
                    session_id=session_id,
                    queued_count=state.queued_count,
                    message=f"未找到 feed_id={feed_id} 对应任务",
                )
            first = candidates[0]
        return self.stop_by_job_id(session_id, first.job_id)

    def stop_all_for_session(self, session_id: str) -> dict[str, int]:
        """Cancel running+queued jobs for a session."""
        with self._state_guard:
            state = self._states.get(session_id)
            if state is None:
                return {"stopped": 0, "running": 0, "queued": 0}

            stopped = 0
            running = 0
            queued = 0
            for job in state.jobs.values():
                if job.cancel_requested:
                    continue
                job.cancel_requested = True
                stopped += 1
                if job.status == "running":
                    running += 1
                elif job.status == "queued":
                    queued += 1
            if running and state.current_task and not state.current_task.done():
                state.current_task.cancel()
            return {"stopped": stopped, "running": running, "queued": queued}

    async def stop_all(self) -> None:
        """Cancel all active jobs, typically during plugin shutdown."""
        tasks = []
        with self._state_guard:
            states = list(self._states.values())
            for state in states:
                if state.current_job:
                    state.current_job.cancel_requested = True
                if state.current_task and not state.current_task.done():
                    state.current_task.cancel()
                    tasks.append(state.current_task)
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        with self._state_guard:
            for session_id, state in list(self._states.items()):
                self._cleanup_state_if_idle(session_id, state)
