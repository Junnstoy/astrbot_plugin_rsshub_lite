from __future__ import annotations

import asyncio

import pytest
from astrbot_plugin_rsshub_lite.src.application.services.session_push_queue import (
    SessionPushQueue,
)


@pytest.mark.asyncio
async def test_same_session_jobs_run_serially():
    queue = SessionPushQueue()
    events: list[str] = []
    release_first = asyncio.Event()

    async def first(job):
        events.append(f"start:{job.job_id}")
        await release_first.wait()
        events.append(f"end:{job.job_id}")
        return "first"

    async def second(job):
        events.append(f"start:{job.job_id}")
        events.append(f"end:{job.job_id}")
        return "second"

    first_task = asyncio.create_task(queue.enqueue("session-1", first))
    await asyncio.sleep(0)
    second_task = asyncio.create_task(queue.enqueue("session-1", second))
    await asyncio.sleep(0)

    assert queue.get_queued_count("session-1") == 1
    assert events == ["start:rss-000001"]

    release_first.set()
    first_result, second_result = await asyncio.gather(first_task, second_task)

    assert first_result.ok is True
    assert first_result.value == "first"
    assert second_result.ok is True
    assert second_result.value == "second"
    assert events == [
        "start:rss-000001",
        "end:rss-000001",
        "start:rss-000002",
        "end:rss-000002",
    ]
    assert queue._states == {}


@pytest.mark.asyncio
async def test_different_sessions_can_run_concurrently():
    queue = SessionPushQueue()
    both_started = asyncio.Event()
    started: set[str] = set()

    async def work(job):
        started.add(job.session_id)
        if started == {"session-1", "session-2"}:
            both_started.set()
        await both_started.wait()
        return job.session_id

    results = await asyncio.gather(
        queue.enqueue("session-1", work),
        queue.enqueue("session-2", work),
    )

    assert {result.value for result in results} == {"session-1", "session-2"}


@pytest.mark.asyncio
async def test_stop_current_cancels_running_job_and_releases_next_job():
    queue = SessionPushQueue()
    started = asyncio.Event()
    next_ran = asyncio.Event()

    async def long_running(_job):
        started.set()
        await asyncio.sleep(60)
        return "never"

    async def next_job(_job):
        next_ran.set()
        return "next"

    first_task = asyncio.create_task(queue.enqueue("session-1", long_running))
    await started.wait()
    second_task = asyncio.create_task(queue.enqueue("session-1", next_job))
    await asyncio.sleep(0)

    stop_result = queue.stop_current("session-1")

    assert stop_result.stopped is True
    assert stop_result.job_id == "rss-000001"
    assert stop_result.queued_count == 1

    first_result = await first_task
    second_result = await second_task

    assert first_result.cancelled is True
    assert second_result.ok is True
    assert second_result.value == "next"
    assert next_ran.is_set()
    assert queue._states == {}


def test_stop_current_without_running_job_reports_noop():
    queue = SessionPushQueue()

    result = queue.stop_current("unknown-session")

    assert result.stopped is False
    assert result.session_id == "unknown-session"
    assert "没有正在运行" in result.message
    assert queue._states == {}


@pytest.mark.asyncio
async def test_stop_all_cancels_running_jobs_across_sessions():
    queue = SessionPushQueue()
    started: set[str] = set()
    all_started = asyncio.Event()

    async def long_running(job):
        started.add(job.session_id)
        if started == {"session-1", "session-2"}:
            all_started.set()
        await asyncio.sleep(60)
        return "never"

    first_task = asyncio.create_task(queue.enqueue("session-1", long_running))
    second_task = asyncio.create_task(queue.enqueue("session-2", long_running))
    await all_started.wait()

    await queue.stop_all()
    first_result, second_result = await asyncio.gather(first_task, second_task)

    assert first_result.cancelled is True
    assert second_result.cancelled is True
    assert queue._states == {}


@pytest.mark.asyncio
async def test_get_jobs_and_stop_by_job_id_for_queued_job():
    queue = SessionPushQueue()
    running_started = asyncio.Event()
    release_running = asyncio.Event()

    async def long_running(_job):
        running_started.set()
        await release_running.wait()
        return "done"

    async def queued_job(_job):
        return "queued"

    running_task = asyncio.create_task(
        queue.enqueue(
            "session-1", long_running, feed_id=1, feed_title="Feed A", sub_id=11
        )
    )
    await running_started.wait()
    queued_task = asyncio.create_task(
        queue.enqueue(
            "session-1", queued_job, feed_id=2, feed_title="Feed B", sub_id=22
        )
    )
    await asyncio.sleep(0)

    jobs = queue.get_jobs("session-1")
    assert len(jobs) == 2
    assert jobs[0].status == "running"
    queued = [job for job in jobs if job.status == "queued"][0]
    assert queued.feed_id == 2
    assert queued.feed_title == "Feed B"

    stop_result = queue.stop_by_job_id("session-1", queued.job_id)
    assert stop_result.stopped is True
    assert "排队任务" in stop_result.message

    release_running.set()
    running_result, queued_result = await asyncio.gather(running_task, queued_task)
    assert running_result.ok is True
    assert queued_result.cancelled is True


@pytest.mark.asyncio
async def test_stop_all_for_session_cancels_running_and_queued():
    queue = SessionPushQueue()
    started = asyncio.Event()
    release = asyncio.Event()

    async def running(_job):
        started.set()
        await release.wait()
        return "running"

    async def queued(_job):
        return "queued"

    running_task = asyncio.create_task(queue.enqueue("session-1", running, feed_id=1))
    await started.wait()
    queued_task = asyncio.create_task(queue.enqueue("session-1", queued, feed_id=2))
    await asyncio.sleep(0)

    summary = queue.stop_all_for_session("session-1")
    assert summary["stopped"] == 2
    assert summary["running"] == 1
    assert summary["queued"] == 1

    release.set()
    running_result, queued_result = await asyncio.gather(running_task, queued_task)
    assert running_result.cancelled is True
    assert queued_result.cancelled is True
