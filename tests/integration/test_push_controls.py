"""Persistent push controls: parsing, ownership, session scope and queue stops."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from astrbot_plugin_rsshub_lite.src.application.commands.batch_activate_cmd import (
    BatchActivateCommand,
)
from astrbot_plugin_rsshub_lite.src.application.commands.batch_deactivate_cmd import (
    BatchDeactivateCommand,
)
from astrbot_plugin_rsshub_lite.src.application.commands.sub_state_cmd import (
    SubStateCommand,
)
from astrbot_plugin_rsshub_lite.src.application.ports import SendResult
from astrbot_plugin_rsshub_lite.src.application.services.notification_dispatcher import (
    NotificationDispatcher,
)
from astrbot_plugin_rsshub_lite.src.application.services.session_push_queue import (
    SessionPushQueue,
)
from astrbot_plugin_rsshub_lite.src.domain.entities.push_history import PushHistory
from astrbot_plugin_rsshub_lite.src.domain.entities.subscription import Subscription
from astrbot_plugin_rsshub_lite.src.infrastructure.persistence.database import (
    DatabaseManager,
)
from astrbot_plugin_rsshub_lite.src.infrastructure.persistence.models import FeedORM
from astrbot_plugin_rsshub_lite.src.infrastructure.persistence.subscription_repository_impl import (
    SubscriptionRepositoryImpl,
)
from astrbot_plugin_rsshub_lite.src.interfaces.handlers.batch import (
    handle_push,
    handle_unpush,
)

SESSION = "onebot:GroupMessage:100"
OTHER_SESSION = "onebot:GroupMessage:200"


def _event(user_id="u1", session=SESSION):
    event = MagicMock()
    event.get_sender_id.return_value = user_id
    event.unified_msg_origin = session
    # Being an AstrBot administrator never bypassed batch subscription ownership.
    event.is_admin.return_value = True
    return event


@pytest_asyncio.fixture
async def controls(tmp_path, monkeypatch):
    db = DatabaseManager()
    path = str(tmp_path / "push.db")
    await db.init(path)
    monkeypatch.setattr(
        "astrbot_plugin_rsshub_lite.src.infrastructure.persistence.subscription_repository_impl.get_database",
        lambda: db,
    )
    repo = SubscriptionRepositoryImpl()
    async with db.get_session() as session:
        session.add(FeedORM(id=1, link="https://example.com/rss", title="Feed"))
        await session.commit()
    for sub_id, user_id, target in (
        (1, "u1", SESSION),
        (2, "u1", OTHER_SESSION),
        (3, "u2", SESSION),
        (4, "u1", None),
        (5, "u1", SESSION),
    ):
        await repo.save(
            Subscription(
                id=sub_id,
                user_id=user_id,
                feed_id=1,
                target_session=target,
                title=f"Subscription {sub_id}",
                interval=30,
                notify=1,
                display_media=0,
            )
        )
    try:
        yield SimpleNamespace(
            db=db,
            path=path,
            repo=repo,
            deps={
                "batch_activate_cmd": BatchActivateCommand(repo),
                "batch_deactivate_cmd": BatchDeactivateCommand(repo),
            },
        )
    finally:
        await db.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("handler", [handle_push, handle_unpush])
@pytest.mark.parametrize("args", ["", " ", "1,wrong", "1,", "0", "-1", "1 2"])
async def test_push_controls_invalid_or_empty_input_never_changes_subscriptions(
    handler, args
):
    # No dependency lookup is allowed for malformed input, especially empty args.
    result = await handler(_event(), args, {})
    assert "用法: /" in result["plain"]
    assert "<订阅ID[,ID...]|all>" in result["plain"]


@pytest.mark.asyncio
@pytest.mark.parametrize("handler", [handle_push, handle_unpush])
@pytest.mark.parametrize("user_id,session", [("", SESSION), ("u1", "")])
async def test_push_controls_require_real_user_and_session(handler, user_id, session):
    result = await handler(_event(user_id, session), "all", {})
    assert "无法确认当前用户或会话" in result["plain"]


def test_legacy_batch_command_adapters_are_removed():
    from astrbot_plugin_rsshub_lite.src.interfaces import handlers
    from astrbot_plugin_rsshub_lite.src.interfaces.handlers import batch

    for module in (handlers, batch):
        assert not hasattr(module, "handle_batch_activate")
        assert not hasattr(module, "handle_batch_deactivate")
    assert callable(batch.handle_push)
    assert callable(batch.handle_unpush)


@pytest.mark.asyncio
async def test_multiple_push_targets_persist_across_database_reopen(controls):
    result = await handle_unpush(_event(), "1, 5,1", controls.deps)
    assert "成功禁用 2 个订阅" in result["plain"]
    assert "持续停止" in result["plain"]
    await controls.db.close()
    await controls.db.init(controls.path)

    assert {s.id for s in await controls.repo.get_active_by_feed_id(1)} == {2, 3, 4}
    paused = await controls.repo.get_by_id(1)
    assert paused is not None
    assert (paused.state, paused.title, paused.interval, paused.notify) == (
        0,
        "Subscription 1",
        30,
        1,
    )
    assert paused.display_media == 0
    assert paused.target_session == SESSION

    result = await handle_push(_event(), "1,5", controls.deps)
    assert "自动推送" in result["plain"]
    await controls.db.close()
    await controls.db.init(controls.path)
    assert {s.id for s in await controls.repo.get_active_by_feed_id(1)} == {
        1,
        2,
        3,
        4,
        5,
    }
    assert len(await controls.repo.get_by_user("u1")) == 4


@pytest.mark.asyncio
@pytest.mark.parametrize("enabled", [False, True])
async def test_explicit_ids_respect_owner_and_current_session(controls, enabled):
    initial_state = int(not enabled)
    for sub_id, user_id in ((1, "u1"), (2, "u1"), (3, "u2")):
        await controls.repo.update_options(sub_id, user_id, state=initial_state)
    handler = handle_push if enabled else handle_unpush
    result = await handler(_event(), "1,2,3,99", controls.deps)

    assert "部分成功" in result["plain"]
    assert "[2] 该订阅不属于当前会话" in result["plain"]
    assert "[3] 无权操作此订阅" in result["plain"]
    assert "[99] 订阅不存在" in result["plain"]
    assert (await controls.repo.get_by_id(1)).state == int(enabled)
    assert (await controls.repo.get_by_id(2)).state == initial_state
    assert (await controls.repo.get_by_id(3)).state == initial_state


@pytest.mark.asyncio
@pytest.mark.parametrize("enabled", [False, True])
async def test_explicit_all_only_changes_senders_current_session(controls, enabled):
    initial_state = int(not enabled)
    for sub_id, user_id in ((1, "u1"), (2, "u1"), (3, "u2"), (4, "u1"), (5, "u1")):
        await controls.repo.update_options(sub_id, user_id, state=initial_state)
    handler = handle_push if enabled else handle_unpush
    result = await handler(_event(), "all", controls.deps)

    assert "3 个订阅" in result["plain"]
    assert (await controls.repo.get_by_id(1)).state == int(enabled)
    assert (await controls.repo.get_by_id(4)).state == int(enabled)
    assert (await controls.repo.get_by_id(5)).state == int(enabled)
    assert (await controls.repo.get_by_id(2)).state == initial_state
    assert (await controls.repo.get_by_id(3)).state == initial_state


@pytest.mark.asyncio
async def test_unpush_cancels_only_matching_subscriptions_in_current_queue(controls):
    # Already-disabled entries must still cancel an outstanding job on repeated unpush.
    await controls.repo.update_options(1, "u1", state=0)
    queue = SessionPushQueue()
    current_started = asyncio.Event()
    other_started = asyncio.Event()
    release = asyncio.Event()
    executed = []

    async def running(job):
        (current_started if job.session_id == SESSION else other_started).set()
        await release.wait()

    async def queued(job):
        executed.append(job.sub_id)

    tasks = [
        asyncio.create_task(queue.enqueue(SESSION, running, feed_id=1, sub_id=1)),
        asyncio.create_task(queue.enqueue(OTHER_SESSION, running, feed_id=1, sub_id=1)),
    ]
    try:
        await asyncio.wait_for(current_started.wait(), timeout=2)
        await asyncio.wait_for(other_started.wait(), timeout=2)
        tasks.extend(
            [
                asyncio.create_task(
                    queue.enqueue(SESSION, queued, feed_id=1, sub_id=5)
                ),
                asyncio.create_task(
                    queue.enqueue(SESSION, queued, feed_id=1, sub_id=3)
                ),
            ]
        )
        await asyncio.sleep(0)
        result = await handle_unpush(_event(), "1,5,3", controls.deps, queue)
        assert "2 个运行中或排队任务" in result["plain"]
        assert (await controls.repo.get_by_id(5)).state == 0
        assert (await controls.repo.get_by_id(3)).state == 1
        assert not queue.get_current_job(OTHER_SESSION).cancel_requested
    finally:
        release.set()
        results = await asyncio.wait_for(asyncio.gather(*tasks), timeout=2)
    assert results[0].cancelled
    assert results[1].ok
    assert results[2].cancelled
    assert results[3].ok
    assert executed == [3]


@pytest.mark.asyncio
async def test_batch_application_keeps_existing_web_scope_when_session_omitted(
    controls,
):
    result = await controls.deps["batch_deactivate_cmd"].execute([2], user_id="u1")
    assert result.success
    assert (await controls.repo.get_by_id(2)).state == 0


@pytest.mark.asyncio
async def test_legacy_state_command_updates_existing_row(controls):
    command = SubStateCommand(controls.repo)
    assert (await command.execute(1, "u1", enable=False)).success
    assert (await controls.repo.get_by_id(1)).state == 0
    assert (await command.execute(1, "u1", enable=True)).success
    assert (await controls.repo.get_by_id(1)).state == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["poll", "retry", "manual_test", "manual_retry"])
async def test_unpush_blocks_late_automatic_jobs_but_preserves_manual_sends(
    controls, monkeypatch, kind
):
    queue = SessionPushQueue()
    sender = SimpleNamespace(send_to_user=AsyncMock(return_value=SendResult(ok=True)))
    provider = SimpleNamespace(get=MagicMock(return_value=sender))
    history = PushHistory(
        id=20,
        sub_id=1,
        user_id="u1",
        feed_id=1,
        target_session=SESSION,
        content="Entry",
        status="retrying",
    )
    history_repo = AsyncMock()
    history_repo.save.side_effect = lambda item: item
    history_repo.get_and_mark_retrying.return_value = [history]
    history_repo.get_by_id.return_value = history
    dispatcher = NotificationDispatcher(
        subscription_repo=controls.repo,
        push_history_repo=history_repo,
        sender_provider=provider,
        push_job_queue=queue,
    )
    prepared = asyncio.Event()
    release = asyncio.Event()
    original_send = dispatcher.send_to_session

    async def delayed_send(**kwargs):
        # A deterministic pause after active subscription lookup and before
        # registration in the queue reproduces a polling/unpush race.
        prepared.set()
        await release.wait()
        return await original_send(**kwargs)

    monkeypatch.setattr(dispatcher, "send_to_session", delayed_send)
    if kind == "retry":
        operation = dispatcher.dispatch_pending_retries()
    elif kind == "manual_retry":
        operation = dispatcher.retry_push_history_once(20)
    else:
        operation = dispatcher.dispatch_to_feed_subscribers(
            feed_id=1,
            content="Entry",
            entry_title="Entry",
            entry_link="https://example.com/entry",
            subscription_ids=[1],
            include_inactive_subscription_ids=kind == "manual_test",
        )
    task = asyncio.create_task(operation)
    try:
        await asyncio.wait_for(prepared.wait(), timeout=2)
        assert queue.get_jobs(SESSION) == []
        await handle_unpush(_event(), "1", controls.deps, queue)
        assert (await controls.repo.get_by_id(1)).state == 0
    finally:
        release.set()
        await asyncio.wait_for(task, timeout=2)

    final_history = history_repo.save.await_args.args[0]
    if kind.startswith("manual"):
        sender.send_to_user.assert_awaited_once()
        assert final_history.status == "success"
    else:
        sender.send_to_user.assert_not_awaited()
        assert final_history.status == "stopped"
        assert not final_history.can_retry()
